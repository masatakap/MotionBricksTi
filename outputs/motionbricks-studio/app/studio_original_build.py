"""Build and audit the independently authored adult library without sample clips."""
import argparse,hashlib,json,math,sys,shutil,time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import warp as wp
from scipy.spatial.transform import Rotation
from .studio_original_library import CATALOG,AdultPerformance,FPS
from .studio_data import root_transform,write_document,read_document
from .studio_motion_data import conditioning_window,serialize_track,validate_track
from .studio_export import export_fbx

ROOT=Path(__file__).resolve().parents[1]

def guard_no_animation_inputs(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        path=str(args[0]).replace('\\','/').lower()
        if '/assets/motions/' in path or path.endswith(('.bvh','.onnx')):
            raise RuntimeError('Independent authoring forbids sample/model inputs: '+path)

def static_assets():
    """Read the reference mesh/rig directly; never instantiate the Studio demo."""
    from motionbricks.io.utils import get_soma_human_model
    from .runtime.common.rig import model_to_runtime
    from motionbricks.model.contract import ModelRig
    wp.init()
    with wp.ScopedDevice('cpu'):
        model=get_soma_human_model();conversion=np.asarray(model_to_runtime(ModelRig.SOMA))
        rotation=Rotation.from_quat(conversion[3:]);inv=model.inverse_bind_transforms.numpy()
        inverse_rotation=Rotation.from_quat(inv[:,3:]).inv()
        bind=np.empty_like(inv);bind[:,:3]=rotation.apply(-inverse_rotation.apply(inv[:,:3]))+conversion[:3]
        bind[:,3:]=(rotation*inverse_rotation).as_quat()
        result=dict(joint_names=np.array(model.skeleton.joint_names),parents=model.skeleton._np_parent_indices.copy(),
                    reference=root_transform(model.skeleton.reference_local_transforms.numpy(),conversion),bind_world=bind,
                    fps=np.array(FPS),mesh_count=np.array(len(model.skinned_meshes)))
        for i,mesh in enumerate(model.skinned_meshes):
            prefix=f'mesh_{i}_'
            result[prefix+'points']=rotation.apply(mesh.points.numpy())+conversion[:3]
            result[prefix+'triangles']=mesh.indices.numpy().reshape(-1,3)
            result[prefix+'joints']=mesh.joint_indices.numpy().reshape(-1,mesh.num_influences)
            result[prefix+'weights']=mesh.joint_weights.numpy().reshape(-1,mesh.num_influences)
        return result

def quality(rig,spec,poses,contacts,targets,hands):
    heights=np.array([[rig.floor_height(p,side) for side in ('Left','Right')] for p in poses])
    world=np.stack([rig.world(p) for p in poses]);ankle_ids=[rig.index[s+'Foot'] for s in ('Left','Right')]
    desired=np.array([[target[s] for s in ('Left','Right')] for target in targets])
    errors=np.linalg.norm(world[:,:, :3,3][:,ankle_ids]-desired,axis=-1)
    dot=np.clip(np.abs(np.sum(poses[:-1,:,3:]*poses[1:,:,3:],axis=-1)),0,1)
    angles=np.rad2deg(2*np.arccos(dot))
    hand_errors=[v['error'] for h in hands for v in h.values()]
    return dict(frames=len(poses),fps=FPS,seconds=(len(poses)-1)/FPS,finite=bool(np.isfinite(poses).all()),
                minimum_sole_z_m=float(heights.min()),max_ground_contact_error_m=float(np.max(np.abs(heights[contacts]-.001))) if contacts.any() else 0.,
                max_ankle_target_error_m=float(errors.max()),max_hand_contact_error_m=max(hand_errors,default=0.),
                local_bone_offset_error_m=float(np.max(np.abs(poses[:,1:,:3]-rig.ref[None,1:,:3]))),
                quaternion_norm_error=float(np.max(np.abs(np.linalg.norm(poses[:,:,3:],axis=-1)-1))),
                max_joint_step_degrees=float(angles.max()),max_joint_step_location=[int(x) for x in np.unravel_index(np.argmax(angles),angles.shape)],
                root_displacement_m=(poses[-1,0,:3]-poses[0,0,:3]).tolist(),
                loop_joint_angle_degrees=float(np.rad2deg(2*np.arccos(np.clip(np.abs(np.sum(poses[0,1:,3:]*poses[-1,1:,3:],axis=-1)),0,1))).max()) if spec.loop else None,
                contact_frames_left=int(contacts[:,0].sum()),contact_frames_right=int(contacts[:,1].sum()))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--only',nargs='*');parser.add_argument('--install',action='store_true');parser.add_argument('--fbx',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    sys.addaudithook(guard_no_animation_inputs)
    assets=static_assets();rig=AdultPerformance(assets)
    skeleton=SimpleNamespace(joint_names=rig.names,_np_parent_indices=rig.parents,num_joints=len(rig.names))
    np.savez_compressed(args.output/'static-rig.npz',**assets)
    reports=[]
    report_path=args.output/'quality-report.json'
    if args.only and report_path.exists():
        reports=[r for r in json.loads(report_path.read_text(encoding='utf-8')) if r['id'] not in args.only]
    for spec in CATALOG:
        if args.only and spec.id not in args.only:continue
        started=time.perf_counter();poses,contacts,targets,hands=rig.build_performance(spec)
        report=quality(rig,spec,poses,contacts,targets,hands);report.update(id=spec.id,name=spec.name,kind=spec.kind,loop=spec.loop)
        assert report['finite'] and report['local_bone_offset_error_m']<1e-6
        assert report['quaternion_norm_error']<1e-6 and report['max_ground_contact_error_m']<1e-4
        assert report['max_ankle_target_error_m']<.001 and report['max_hand_contact_error_m']<.002
        assert report['max_joint_step_degrees']<50
        if spec.loop:assert report['loop_joint_angle_degrees']<.1
        sample=42 if spec.kind.startswith('vault') else len(poses)//2 if spec.kind in ('sit_down','stand_up','duck','duck_jog') else 8
        track=dict(last_frame=len(poses)-1,sample_frame=min(sample,len(poses)-4),origin='reference',seed_source='',
                   authoring_method='Independent analytical adult performance from static SOMA reference geometry; no source clips, samples or model inference',
                   performance_id=spec.id,loop=spec.loop,
                   keys=[dict(frame=i,pose=pose) for i,pose in enumerate(poses)])
        validate_track(track,len(rig.names))
        entry=dict(name='自作・成人男性 / '+spec.name,source='authored-reference',window=conditioning_window(track,0).tolist(),
                   placement=[0,0,0,0,0,0,1],num_poses=4,min_tokens=8,max_tokens=14,hold_frames=0,duration_seconds=0.,motion_track=serialize_track(track))
        name='Ti_Original_Adult_'+spec.id;path=args.output/(name+'.motion.json')
        write_document(path,'motion',skeleton,[entry],extras={'provenance':dict(method=track['authoring_method'],fps=FPS,performance_id=spec.id)})
        restored=read_document(path,skeleton,'motion')[0]['motion_track']
        # The reader normalizes float32 quaternion roundoff during validation.
        roundtrip=np.stack([k['pose'] for k in restored['keys']])
        report['readback_max_component_error']=float(np.max(np.abs(roundtrip-poses)))
        assert np.allclose(roundtrip,poses,atol=2e-7,rtol=0)
        np.savez_compressed(args.output/(spec.id+'.npz'),poses=poses,contacts=contacts)
        if args.fbx:
            export_fbx(dict(assets,poses=poses),args.output/(name+'.fbx'),include_mesh=False)
        if args.install:
            target=ROOT/'user_data/poses'/path.name;target.parent.mkdir(exist_ok=True);shutil.copy2(path,target)
        reports.append(report)
        reports.sort(key=lambda r:next(i for i,s in enumerate(CATALOG) if s.id==r['id']))
        (args.output/'quality-report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
        print(spec.id,len(poses),'floor',round(report['minimum_sole_z_m'],4),'ankle',round(report['max_ankle_target_error_m'],4),'hand',round(report['max_hand_contact_error_m'],4),'step',round(report['max_joint_step_degrees'],1),'s',round(time.perf_counter()-started,1),flush=True)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'app/studio_original_library.py',ROOT/'app/studio_walk_authoring.py',ROOT/'motionbricks/assets/human/soma_base_skel_minimal_no_root.usd']}
    (args.output/'provenance.json').write_text(json.dumps(dict(inputs='Static reference skeleton, mesh, skin weights and bind transforms only',excluded='Bundled BVH/CSV, sampled poses, ONNX models and inference',hashes=hashes,performances=[r['id'] for r in reports]),indent=2),encoding='utf-8')

if __name__=='__main__':main()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
