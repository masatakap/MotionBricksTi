"""Independent geometric checks on the delivered animation files."""
import argparse,json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from .studio_original_library import AdultPerformance,CATALOG
from .studio_data import read_document

def skin(rig,pose,points,indices,weights):
    matrices=rig.world(pose)@rig.inverse_bind;result=np.zeros_like(points,dtype=float)
    for k in range(indices.shape[1]):
        m=matrices[indices[:,k]]
        result+=(np.einsum('nij,nj->ni',m[:,:3,:3],points)+m[:,:3,3])*weights[:,k,None]
    return result

def flexion(world,a,b,c):
    u=world[:,b,:3,3]-world[:,a,:3,3];v=world[:,c,:3,3]-world[:,b,:3,3]
    return np.rad2deg(np.arccos(np.clip(np.sum(u*v,axis=-1)/(np.linalg.norm(u,axis=-1)*np.linalg.norm(v,axis=-1)),-1,1)))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path);parser.add_argument('--only',nargs='*');args=parser.parse_args();folder=args.folder
    assets=np.load(folder/'static-rig.npz');rig=AdultPerformance(assets)
    skeleton=SimpleNamespace(joint_names=rig.names,_np_parent_indices=rig.parents,num_joints=len(rig.names))
    results=[];failures=[]
    for spec in CATALOG:
        if args.only and spec.id not in args.only:continue
        data=np.load(folder/(spec.id+'.npz'));poses=data['poses'];contacts=data['contacts']
        entry=read_document(folder/('Ti_Original_Adult_'+spec.id+'.motion.json'),skeleton,'motion')[0]
        assert entry['motion_track']['origin']=='reference' and entry['motion_track']['seed_source']==''
        assert len(entry['motion_track']['keys'])==len(poses)
        assert np.isfinite(poses).all()
        assert np.max(np.abs(poses[:,1:,:3]-rig.ref[None,1:,:3]))<1e-6
        world=np.stack([rig.world(p) for p in poses]);knees=[];elbows=[]
        for side in ('Left','Right'):
            knees.extend(flexion(world,*[rig.index[side+n] for n in ('Leg','Shin','Foot')]))
            elbows.extend(flexion(world,*[rig.index[side+n] for n in ('Arm','ForeArm','Hand')]))
        r=dict(id=spec.id,max_knee_flexion_degrees=float(max(knees)),max_elbow_flexion_degrees=float(max(elbows)))
        if max(knees)>155:failures.append(spec.id+': knee flexion exceeds 155 degrees')
        if max(elbows)>160:failures.append(spec.id+': elbow flexion exceeds 160 degrees')
        if spec.kind.startswith('vault'):
            height=.5 if spec.kind=='vault_low' else .75;clearances=[]
            for pose in poses:
                for side in ('Left','Right'):
                    for points,indices,weights in rig.feet[side]:
                        p=skin(rig,pose,points,indices,weights)
                        mask=(np.abs(p[:,0])<=.5)&(np.abs(p[:,1])<=.125)
                        if mask.any():clearances.extend(p[mask,2]-height)
            r['minimum_foot_clearance_above_obstacle_m']=float(min(clearances)) if clearances else None
            if clearances and min(clearances)<-.002:failures.append(spec.id+': foot intersects obstacle')
            penetration=0.;penetrating=0
            for pose in poses:
                for k in range(int(assets['mesh_count'])):
                    prefix=f'mesh_{k}_'
                    p=skin(rig,pose,assets[prefix+'points'],assets[prefix+'joints'],assets[prefix+'weights'])
                    inside=(np.abs(p[:,0])<.495)&(np.abs(p[:,1])<.12)&(p[:,2]>0)&(p[:,2]<height-.005)
                    if inside.any():
                        penetrating+=int(inside.sum());penetration=max(penetration,float((height-p[inside,2]).max()))
            r['body_penetrating_vertices_total']=penetrating;r['body_penetration_depth_m']=penetration
            if penetrating:failures.append(spec.id+': body intersects obstacle')
        results.append(r)
        print(spec.id,round(max(knees),1),round(max(elbows),1),r.get('minimum_foot_clearance_above_obstacle_m',''),flush=True)
    report=dict(performances=results,failures=failures,passed=not failures)
    (folder/'geometric-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if failures:raise SystemExit('\n'.join(failures))
    print(str(len(results))+' independently authored files: geometric verification passed')

if __name__=='__main__':main()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
