"""Rest-calibrated VRM humanoid mocap -> SOMA, preserving captured rotations.

Offline asset preparation. It does not infer a new performance or clamp dance
joint ranges. Hair, clothing and facial shapes are outside the SOMA skeleton.
Units: meters, Z up, XYZW rotations. FBX decoding is performed separately.
"""
import numpy as np
from scipy.spatial.transform import Rotation


def vrm_mapping(target_names,source_names):
    available=set(source_names)
    mapping={'Hips':'J_Bip_C_Hips','Spine1':'J_Bip_C_Spine','Spine2':'J_Bip_C_Chest','Chest':'J_Bip_C_UpperChest','Neck1':'J_Bip_C_Neck','Head':'J_Bip_C_Head'}
    for side,short in (('Left','L'),('Right','R')):
        for target,source in [('Shoulder','Shoulder'),('Arm','UpperArm'),('ForeArm','LowerArm'),('Hand','Hand'),('Leg','UpperLeg'),('Shin','LowerLeg'),('Foot','Foot'),('ToeBase','ToeBase')]:mapping[side+target]=f'J_Bip_{short}_{source}'
        for finger,source in [('Index','Index'),('Middle','Middle'),('Ring','Ring'),('Pinky','Little')]:
            # SOMA has an explicit metacarpal before the three finger joints.
            mapping[side+'Hand'+finger+'1']=f'J_Bip_{short}_Hand'
            for segment in (1,2,3):mapping[side+'Hand'+finger+str(segment+1)]=f'J_Bip_{short}_{source}{segment}'
        for segment in (1,2,3):mapping[side+'HandThumb'+str(segment)]=f'J_Bip_{short}_Thumb{segment}'
    required=['Hips','Chest','Head']+[side+n for side in ('Left','Right') for n in ('Arm','ForeArm','Hand','Leg','Shin','Foot')]
    for name in required:
        if mapping[name] not in available:raise ValueError('Missing source bone: '+mapping[name])
    return {name:source for name,source in mapping.items() if name in target_names and source in available}


def forward(poses,parents):
    poses=np.asarray(poses);p=poses[:,:,:3].astype(float).copy()
    r=Rotation.from_quat(poses[:,:,3:].reshape(-1,4)).as_matrix().reshape(*poses.shape[:2],3,3)
    for j,parent in enumerate(parents):
        if parent>=0:p[:,j]=p[:,parent]+np.einsum('fij,fj->fi',r[:,parent],p[:,j]);r[:,j]=r[:,parent]@r[:,j]
    return p,r


def local_from_world(world_r,root_position,reference,parents):
    frames=len(world_r);local=world_r.copy()
    for j,parent in enumerate(parents):
        if parent>=0:local[:,j]=world_r[:,parent].swapaxes(-1,-2)@world_r[:,j]
    result=np.broadcast_to(reference,(frames,*reference.shape)).copy();result[:,0,:3]=root_position
    result[:,:,3:]=Rotation.from_matrix(local.reshape(-1,3,3)).as_quat().reshape(frames,-1,4)
    return result


def retarget_rotations(source_world,source_rest,source_names,assets):
    names=list(assets['joint_names']);parents=assets['parents'];reference=assets['reference'];frames=len(source_world)
    src={n:i for i,n in enumerate(source_names)};mapping=vrm_mapping(names,source_names)
    _,rest_r=forward(reference[None],parents);rest_r=rest_r[0]
    source_r=Rotation.from_quat(source_world[:,:,3:].reshape(-1,4)).as_matrix().reshape(frames,-1,3,3)
    bind_r=Rotation.from_quat(source_rest[:,3:]).as_matrix();delta=source_r@bind_r[None].swapaxes(-1,-2)
    local_ref_r=Rotation.from_quat(reference[:,3:]).as_matrix();world=np.empty((frames,len(names),3,3))
    for j,name in enumerate(names):
        if name in mapping:world[:,j]=delta[:,src[mapping[name]]]@rest_r[j]
        elif name=='Neck2' and 'J_Bip_C_Neck' in src:
            a=delta[:,src['J_Bip_C_Neck']];b=delta[:,src['J_Bip_C_Head']]
            half=Rotation.from_matrix(a.swapaxes(-1,-2)@b).as_rotvec()*.5
            world[:,j]=a@Rotation.from_rotvec(half).as_matrix()@rest_r[j]
        else:world[:,j]=world[:,parents[j]]@local_ref_r[j] if parents[j]>=0 else local_ref_r[j]
    leg_target=sum(np.linalg.norm(reference[names.index('Left'+n),:3]) for n in ('Shin','Foot'))
    leg_source=sum(np.linalg.norm(source_rest[src['J_Bip_L_'+b],:3]-source_rest[src['J_Bip_L_'+a],:3]) for a,b in [('UpperLeg','LowerLeg'),('LowerLeg','Foot')])
    scale=leg_target/leg_source;hip=src['J_Bip_C_Hips'];root=reference[0,:3]+scale*(source_world[:,hip,:3]-source_rest[hip,:3]);root[:,:2]-=root[0,:2].copy()
    poses=local_from_world(world,root,reference,parents)
    return poses,dict(mapping=mapping,translation_scale=float(scale),source_root_initial_xy_m=source_world[0,hip,:2].tolist())


class SkinFootHeights:
    """Exact LBS z values of all foot-dominant skin samples, batched over time."""
    def __init__(self,samples):
        self.samples=[]
        for ids,weights,local in samples:
            bones=np.unique(ids[weights>1e-8]);coefficient=np.zeros((len(ids),len(bones),4))
            for b,joint in enumerate(bones):
                w=weights*(ids==joint);coefficient[:,b,:3]=np.sum(local*w[:,:,None],axis=1);coefficient[:,b,3]=np.sum(w,axis=1)
            self.samples.append((bones,coefficient.reshape(len(ids),-1).T))
    def evaluate(self,position,rotation):
        heights=[]
        for bones,coefficient in self.samples:
            feature=np.concatenate((rotation[:,bones,2,:],position[:,bones,2,None]),axis=-1).reshape(len(position),-1)
            heights.append(np.min(feature@coefficient,axis=1))
        return np.stack(heights,axis=1)
    @classmethod
    def soma(cls,assets):
        names=list(assets['joint_names']);bind=assets['bind_world'];inverse=Rotation.from_quat(bind[:,3:]).as_matrix().swapaxes(-1,-2);samples=[]
        for side in ('Left','Right'):
            allids=[];allweights=[];alllocal=[]
            for mesh in range(int(assets['mesh_count'])):
                prefix=f'mesh_{mesh}_';ids=assets[prefix+'joints'];weights=assets[prefix+'weights'];points=assets[prefix+'points'];dominant=ids[np.arange(len(ids)),weights.argmax(axis=1)]
                mask=np.isin(dominant,[names.index(side+n) for n in ('Foot','ToeBase','ToeEnd')]);ids=ids[mask];weights=weights[mask];points=points[mask]
                local=np.einsum('vkij,vkj->vki',inverse[ids],points[:,None]-bind[ids,:3]);allids.append(ids);allweights.append(weights);alllocal.append(local)
            samples.append((np.concatenate(allids),np.concatenate(allweights),np.concatenate(alllocal)))
        return cls(samples)


def align_batch(a,b):
    a=a/np.maximum(np.linalg.norm(a,axis=-1,keepdims=True),1e-12);b=b/np.maximum(np.linalg.norm(b,axis=-1,keepdims=True),1e-12)
    cross=np.cross(a,b);length=np.linalg.norm(cross,axis=-1);dot=np.clip(np.sum(a*b,axis=-1),-1,1)
    axis=cross/np.maximum(length[:,None],1e-12)
    opposite=(length<1e-8)&(dot<0)
    if np.any(opposite):
        fallback=np.cross(a[opposite],np.array([0.,1,0]));bad=np.linalg.norm(fallback,axis=1)<1e-6
        fallback[bad]=np.cross(a[opposite][bad],np.array([1.,0,0]));axis[opposite]=fallback/np.linalg.norm(fallback,axis=1,keepdims=True)
    return Rotation.from_rotvec(axis*np.arctan2(length,dot)[:,None]).as_matrix()


def preserve_foot_paths(poses,source_world,source_rest,source_names,assets,source_sole,source_bind_floor,scale,iterations=5):
    names=list(assets['joint_names']);parents=assets['parents'];reference=assets['reference'];src={n:i for i,n in enumerate(source_names)}
    foot_skin=SkinFootHeights.soma(assets);positions,rotations=forward(poses,parents);original_r=rotations.copy();rest_p,rest_r=forward(reference[None],parents)
    root=poses[:,0,:3].copy();desired=np.maximum(.0005,(source_sole-source_bind_floor)*scale)
    actual=foot_skin.evaluate(positions,rotations);goals=[]
    hip=src['J_Bip_C_Hips'];root_shift=source_world[0,hip,:2]-source_rest[hip,:2]
    for k,(side,short) in enumerate((('Left','L'),('Right','R'))):
        j=names.index(side+'Foot');sj=src[f'J_Bip_{short}_Foot'];goal=positions[:,j].copy()
        goal[:,:2]=rest_p[0,j,:2]+scale*(source_world[:,sj,:2]-source_rest[sj,:2]-root_shift)
        goal[:,2]+=desired[:,k]-actual[:,k];goals.append(goal)
    for iteration in range(iterations):
        positions,rotations=forward(local_from_world(original_r,root,reference,parents),parents)
        # Lower pelvis only when source foot paths exceed the target leg's reach.
        root_before=root[:,2].copy()
        for k,side in enumerate(('Left','Right')):
            a,b,c=[names.index(side+n) for n in ('Leg','Shin','Foot')];u=np.linalg.norm(reference[b,:3]);v=np.linalg.norm(reference[c,:3]);h=positions[:,a];goal=goals[k]
            cap=goal[:,2]+np.sqrt(np.maximum(1e-5,(u+v-1e-5)**2-np.sum((goal[:,:2]-h[:,:2])**2,axis=1)))-(h[:,2]-root_before);root[:,2]=np.minimum(root[:,2],cap)
        positions,rotations=forward(local_from_world(original_r,root,reference,parents),parents)
        for k,side in enumerate(('Left','Right')):
            a,b,c=[names.index(side+n) for n in ('Leg','Shin','Foot')];u=np.linalg.norm(reference[b,:3]);v=np.linalg.norm(reference[c,:3]);h=positions[:,a];goal=goals[k]
            direction=goal-h;distance=np.linalg.norm(direction,axis=1);direction/=np.maximum(distance[:,None],1e-9);d=np.clip(distance,abs(u-v)+1e-6,u+v-1e-6)
            # A knee's positional pole is undefined when the captured leg is
            # almost straight. Use its measured thigh frame, which retains the
            # anatomical bend plane through extension without a sign switch.
            bend_reference=rest_r[0,a].T@np.array([0.,-1.,0.])
            pole=np.einsum('fij,j->fi',original_r[:,a],bend_reference);pole-=direction*np.sum(pole*direction,axis=1,keepdims=True)
            bad=np.linalg.norm(pole,axis=1)<.001
            fallback=np.tile([0.,-1.,0.],(len(poses),1));fallback-=direction*np.sum(fallback*direction,axis=1,keepdims=True);pole[bad]=fallback[bad];pole/=np.maximum(np.linalg.norm(pole,axis=1,keepdims=True),1e-9)
            along=(u*u-v*v+d*d)/(2*d);middle=h+direction*along[:,None]+pole*np.sqrt(np.maximum(0,u*u-along*along))[:,None]
            rotations[:,a]=align_batch(positions[:,b]-h,middle-h)@original_r[:,a]
            rotations[:,b]=align_batch(positions[:,c]-positions[:,b],h+direction*d[:,None]-middle)@original_r[:,b]
        result=local_from_world(rotations,root,reference,parents);positions,rotations=forward(result,parents);actual=foot_skin.evaluate(positions,rotations)
        for k in range(2):goals[k][:,2]+=desired[:,k]-actual[:,k]
    # No smoothing or finger/shoulder reconstruction is applied to the captured rotations.
    return result,dict(desired_sole_m=desired,actual_sole_m=actual,root_height_correction_m=root[:,2]-poses[:,0,2],max_sole_error_m=float(np.abs(actual-desired).max()))

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
