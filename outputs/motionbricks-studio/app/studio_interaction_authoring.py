"""Author Studio interaction clips exclusively from static reference geometry."""
import argparse,json,sys,hashlib
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from .studio_original_library import AdultPerformance,CATALOG,FPS,smooth
from .studio_original_build import static_assets,quality
from .studio_original_verify import skin
from .studio_data import write_document
from .studio_motion_data import serialize_track
from .studio_export import export_fbx

IDS=('walk','run','vault_050','vault_075_hand','vault_075_free','duck_walk','duck_jog','sit_down','seated_idle','stand_up')

class InteractionRig(AdultPerformance):
    def sit_pose(self,q,breath=0.):
        pose,feet,hands=super().sit_pose(q,breath)
        # A 40 cm seat is the Studio default; retain planted feet via leg IK.
        pose[0,2]-=.005*smooth((q-.15)/.70)
        return self.finish(pose,feet),feet,hands

def protect(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        p=str(args[0]).replace('\\','/').lower()
        if '/assets/motions/' in p or p.endswith(('.bvh','.csv','.onnx')):
            raise RuntimeError('Restricted animation/model inputs are not authoring inputs: '+p)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--only',nargs='*');args=parser.parse_args()
    folder=args.output;folder.mkdir(parents=True,exist_ok=True);sys.addaudithook(protect)
    assets=static_assets();rig=InteractionRig(assets);np.savez_compressed(folder/'static-rig.npz',**assets)
    skeleton=SimpleNamespace(joint_names=rig.names,_np_parent_indices=rig.parents,num_joints=len(rig.names))
    reports=[];clips={}
    if args.only and (folder/'interactions.json').exists():
        clips=json.loads((folder/'interactions.json').read_text(encoding='utf-8'))['clips']
        reports=[r for r in json.loads((folder/'quality-report.json').read_text(encoding='utf-8')) if r['id'] not in args.only]
    for spec in CATALOG:
        if spec.id not in IDS:continue
        if args.only and spec.id not in args.only:continue
        poses,contacts,targets,hands=rig.build_performance(spec)
        if spec.kind in ('duck','duck_jog'):
            # Center the fully crouched passage on the obstacle, not the start.
            offset=poses[len(poses)//2,0,:2].copy();poses[:,0,:2]-=offset
            for target in targets:
                for side in target:target[side][:2]-=offset
        report=quality(rig,spec,poses,contacts,targets,hands);report.update(id=spec.id,name=spec.name,kind=spec.kind,loop=spec.loop)
        assert report['finite'] and report['max_ground_contact_error_m']<1e-4
        assert report['max_ankle_target_error_m']<.001 and report['max_hand_contact_error_m']<.002
        report['body_obstacle_penetrating_vertices']=0
        if spec.kind.startswith('vault'):
            height=.5 if spec.kind=='vault_low' else .75;depth=.6 if spec.kind=='vault_low' else .3
            for pose in poses:
                for k in range(int(assets['mesh_count'])):
                    prefix=f'mesh_{k}_';p=skin(rig,pose,assets[prefix+'points'],assets[prefix+'joints'],assets[prefix+'weights'])
                    report['body_obstacle_penetrating_vertices']+=int(((np.abs(p[:,0])<.495)&(np.abs(p[:,1])<depth/2-.005)&(p[:,2]>.0)&(p[:,2]<height-.005)).sum())
            assert not report['body_obstacle_penetrating_vertices'],(spec.id,report)
        floor=np.array([[rig.floor_height(p,s) for s in ('Left','Right')] for p in poses]).min(axis=1)
        track=dict(last_frame=len(poses)-1,sample_frame=0,origin='reference',seed_source='',
                   authoring_method='Independent static-reference analytic interaction; no sample clips or inference',
                   performance_id=spec.id,keys=[dict(frame=i,pose=p) for i,p in enumerate(poses)])
        entry=dict(name='自作・障害物用 / '+spec.name,source='authored-reference',window=poses[:4].tolist(),placement=[0,0,0,0,0,0,1],num_poses=4,min_tokens=8,max_tokens=14,motion_track=serialize_track(track))
        filename='Ti_Interaction_Adult_'+spec.id+'.motion.json';write_document(folder/filename,'motion',skeleton,[entry])
        export_fbx(dict(assets,poses=poses),folder/filename.replace('.motion.json','.fbx'),include_mesh=False)
        np.savez_compressed(folder/(spec.id+'.npz'),poses=poses,contacts=contacts)
        clips[spec.id]=dict(file=filename,minimum_sole_z=floor.tolist(),kind=spec.kind,reference_height=.4 if spec.kind in ('sit_down','stand_up','seated_idle') else .5 if spec.kind=='vault_low' else .75 if spec.kind.startswith('vault') else None)
        reports.append(report);print(spec.id,len(poses),report['body_obstacle_penetrating_vertices'],flush=True)
    manifest=dict(schema='motionbricks-ti-independent-interactions',version=1,clips=clips,
                  actions={'jump_0_5m':['vault_050'],'jump_0_75m':['vault_075_hand','vault_075_free'],'avoidance':['duck_walk','duck_jog'],'sit':['sit_down','seated_idle','stand_up']})
    (folder/'interactions.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    reports.sort(key=lambda r:next(i for i,s in enumerate(CATALOG) if s.id==r['id']))
    (folder/'quality-report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    paths=[Path(__file__),Path(__file__).with_name('studio_original_library.py'),Path(__file__).with_name('studio_walk_authoring.py')]
    (folder/'provenance.json').write_text(json.dumps(dict(inputs='Static SOMA skeleton/mesh only',excluded='Bundled BVH/CSV, sampled poses, ONNX and inference',sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}),indent=2),encoding='utf-8')

if __name__=='__main__':main()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
