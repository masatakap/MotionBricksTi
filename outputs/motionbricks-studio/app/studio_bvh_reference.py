"""Offline, neutral-calibrated BVH reference transfer (not runtime inference).

Keep measured world rotations, including axial twist. Use a neutral interval
or declared calibration T pose for the body, bent action frames for knee
hinges, and quiet stance frames from the same take for feet and dimensions.
Never infer a neutral body pose from an arbitrary first action frame.
Reference-derived output must retain the input license and attribution.
"""
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
from scipy.ndimage import gaussian_filter1d,maximum_filter1d
from .studio_reference_retarget import read_bvh,axis,body_frame,unit
from .studio_mocap_retarget import forward,local_from_world,align_batch,SkinFootHeights


def capture(path):
    names,p,r,fps=read_bvh(path)
    if 'Z_UP_WORLD_ORIGIN' in names:p*=100.
    else:
        c=axis([1,0,0],np.pi/2);p=np.einsum('ij,fnj->fni',c,p);r=c@r
    return dict(names=names,p=p,r=r,fps=fps)


def mapping(names):
    available=set(names)
    def find(*options):
        return next((n for n in options if n in available),None)
    m={'Hips':'Hips','Spine1':find('Chest','Spine'),'Spine2':find('Chest3','Spine2','Spine1'),
       'Chest':find('Chest4','Spine3','Spine1'),'Neck1':'Neck','Neck2':find('Neck1','Neck'),'Head':'Head'}
    for side in ('Left','Right'):
        for target,options in [('Shoulder',('Collar','Shoulder')),('Arm',('Arm','Shoulder')),
                               ('ForeArm',('ForeArm','Elbow')),('Hand',('Hand','Wrist')),
                               ('Leg',('UpLeg','Hip')),('Shin',('Leg','Knee')),
                               ('Foot',('Foot','Ankle')),('ToeBase',('ToeBase','Toe'))]:
            m[side+target]=find(*(side+n for n in options))
    if any(n not in available for n in m.values()):raise ValueError('Incomplete BVH humanoid mapping')
    return m


def resample(data,start,end=None,fps=30.):
    duration=(len(data['p'])-1)/data['fps'];end=duration if end is None else min(end,duration)
    if not 0<=start<end:raise ValueError('Invalid source interval')
    source=np.arange(len(data['p']))/data['fps']
    times=np.minimum(start+np.arange(int(np.ceil((end-start)*fps-1e-7))+1)/fps,end)
    p=np.stack([np.interp(times,source,a) for a in data['p'].reshape(len(source),-1).T],axis=1).reshape(len(times),-1,3)
    r=np.stack([Slerp(source,Rotation.from_matrix(data['r'][:,j]))(times).as_matrix() for j in range(len(data['names']))],axis=1)
    return dict(names=data['names'],p=p,r=r,fps=fps,source_times=times)


def straight_interval(data,start,end,seconds=3.,side=0,min_speed=.15):
    """Select measured locomotion without including the room-end turn."""
    m=mapping(data['names']);idx={n:i for i,n in enumerate(data['names'])};fps=data['fps']
    x=data['p'][:,idx[m['LeftLeg']]]-data['p'][:,idx[m['RightLeg']]]
    yaw=np.unwrap(np.arctan2(x[:,1],x[:,0]));root=data['p'][:,idx['Hips'],:2]
    count=round(seconds*fps);best=None
    for a in range(round(start*fps),min(len(root)-count,round(end*fps)-count)+1,max(1,round(fps/10))):
        b=a+count;heading=yaw[a:b];displacement=root[b]-root[a]
        direction=np.array([np.cos(yaw[a]),np.sin(yaw[a])]);lateral=displacement@direction
        if side and lateral*side<.05:continue
        distance=np.linalg.norm(displacement);path=np.linalg.norm(np.diff(root[a:b+1],axis=0),axis=1).sum()
        if distance/seconds<min_speed:continue
        score=float(np.std(heading)+2*(1-distance/max(path,1e-9)))
        if best is None or score<best[0]:best=(score,a/fps,b/fps)
    if best is None:raise ValueError('No interval with the requested movement direction')
    return best[1:]


def concatenate(parts,blend_frames=8):
    """Join measured takes with explicit heading/translation and a short overlap."""
    result=dict(parts[0]);result['p']=parts[0]['p'].copy();result['r']=parts[0]['r'].copy()
    m=mapping(result['names']);ids={n:i for i,n in enumerate(result['names'])};hip=ids['Hips']
    for part in parts[1:]:
        if part['names']!=result['names'] or part['fps']!=result['fps']:raise ValueError('Incompatible captures')
        a=result['p'][-1,ids[m['LeftLeg']]]-result['p'][-1,ids[m['RightLeg']]]
        b=part['p'][0,ids[m['LeftLeg']]]-part['p'][0,ids[m['RightLeg']]]
        c=axis([0,0,1],np.arctan2(a[1],a[0])-np.arctan2(b[1],b[0]))
        p=np.einsum('ij,fnj->fni',c,part['p']-part['p'][0,hip])+result['p'][-1,hip]
        r=c@part['r'];n=min(blend_frames,len(p)//3,len(result['p'])//3)
        # Align the second root at the start of the overlap, not after it.
        p+=result['p'][-n,hip]-result['p'][-1,hip]
        w=np.linspace(0,1,n);w=w*w*(3-2*w)
        positions=result['p'][-n:]*(1-w[:,None,None])+p[:n]*w[:,None,None]
        rotations=[]
        for f in range(n):
            delta=result['r'][-n+f].swapaxes(-1,-2)@r[f]
            rotations.append(result['r'][-n+f]@Rotation.from_rotvec(Rotation.from_matrix(delta).as_rotvec()*w[f]).as_matrix())
        result['p']=np.concatenate((result['p'][:-n],positions,p[n:]));result['r']=np.concatenate((result['r'][:-n],rotations,r[n:]))
    result['source_times']=np.arange(len(result['p']))/result['fps']
    return result


def fit_hanging_arms(poses,assets,minimum_degrees=20.,side_weights=None,down_threshold=.55):
    """Adapt hanging arms to SOMA torso width without changing elbow/finger FK.

    Rotate the entire arm chain as a unit. Preserve intentional forward/high
    arm poses; a thinner source performer's arms must not enter the SOMA torso.
    """
    names=list(assets['joint_names']);parents=assets['parents'];ref=assets['reference'];idx={n:i for i,n in enumerate(names)}
    p,r=forward(poses,parents);_,rest=forward(ref[None],parents);body=r[:,idx['Chest']]@rest[0,idx['Chest']].T
    changes={}
    for side,sign in (('Left',1),('Right',-1)):
        a,b=idx[side+'Arm'],idx[side+'ForeArm'];v=p[:,b]-p[:,a];v/=np.linalg.norm(v,axis=1,keepdims=True)
        local=np.einsum('fji,fj->fi',body,v);lateral=sign*local[:,0];down=-local[:,2]
        weight=np.clip((down-down_threshold)/.20,0,1);weight=weight*weight*(3-2*weight)
        if side_weights is not None:weight*=side_weights.get(side,np.ones(len(poses)))
        desired=np.maximum(lateral,np.sin(np.deg2rad(minimum_degrees))*np.sqrt(np.maximum(0.,1-local[:,1]**2)))
        new=local.copy();new[:,0]=sign*(lateral+(desired-lateral)*weight)
        new[:,1:]*=np.sqrt(np.maximum(0.,1-new[:,0]**2)/np.maximum(1-local[:,0]**2,1e-8))[:,None]
        target=np.einsum('fij,fj->fi',body,new);correction=align_batch(v,target)
        mask=[j for j,n in enumerate(names) if n==side+'Arm' or n==side+'ForeArm' or n.startswith(side+'Hand')]
        r[:,mask]=correction[:,None]@r[:,mask]
        changes[side]=float(np.rad2deg(Rotation.from_matrix(correction).magnitude()).max())
    result=local_from_world(r,poses[:,0,:3],ref,parents).astype(np.float32)
    final,_=forward(result,parents);changes['maximum_wrist_path_adjustment_m']=max(float(np.linalg.norm(final[:,idx[s+'Hand']]-p[:,idx[s+'Hand']],axis=1).max()) for s in ('Left','Right'))
    return result,changes


def canonicalize(data,neutral):
    """One heading transform for the entire take; preserve its turns/travel."""
    d=dict(data);n=dict(neutral)
    for obj in (d,n):
        om=mapping(obj['names']);oi={n:i for i,n in enumerate(obj['names'])}
        first=obj['p'][:min(5,len(obj['p']))]
        x=np.mean(first[:,oi[om['LeftLeg']]]-first[:,oi[om['RightLeg']]],axis=0)
        c=axis([0,0,1],-np.arctan2(x[1],x[0]))
        obj['p']=np.einsum('ij,fnj->fni',c,obj['p']);obj['r']=c@obj['r']
    return d,n


def transfer(data,neutral,assets,neutral_target,*,allow_flight=False,stance_width_extra_m=0.,reference_samples=None):
    """Calibrate swing and twist, then solve the source foot paths on SOMA."""
    data,neutral=canonicalize(data,neutral)
    names=list(assets['joint_names']);parents=assets['parents'];ref=assets['reference'];idx={n:i for i,n in enumerate(names)}
    src={n:i for i,n in enumerate(data['names'])};nsrc={n:i for i,n in enumerate(neutral['names'])};m=mapping(data['names']);nm=mapping(neutral['names'])
    # The neutral input is a reviewed interval of an idle capture.
    nf=len(neutral['p'])//2;np0=neutral['p'][nf];nr=neutral['r'][nf]
    tp,tr=forward(neutral_target[None],parents);tp=tp[0];tr=tr[0]
    _,reference_r=forward(ref[None],parents);reference_r=reference_r[0]
    reference_samples=data if reference_samples is None else reference_samples
    ri={n:i for i,n in enumerate(reference_samples['names'])};rm=mapping(reference_samples['names']);foot_frames={};ankle_references=[]
    for side in ('Left','Right'):
        f=ri[rm[side+'Foot']];h=ri[rm[side+'Leg']];k=ri[rm[side+'Shin']];rp=reference_samples['p'];rr=reference_samples['r'];fps=reference_samples['fps'];speed=np.linalg.norm(np.gradient(rp[:,f,:2],axis=0)*fps,axis=1);angular=np.r_[0.,np.linalg.norm(Rotation.from_matrix(rr[:-1,f].swapaxes(-1,-2)@rr[1:,f]).as_rotvec(),axis=1)*fps]
        length=np.linalg.norm(rp[:,k]-rp[:,h],axis=1)+np.linalg.norm(rp[:,f]-rp[:,k],axis=1);score=speed/np.maximum(length,1e-8)+.04*angular
        if len(score)>1:score[0]=np.inf
        selected=np.argsort(score)[:max(1,min(len(score)-1,max(4,len(score)//20)))];foot_frames[side]=selected;ankle_references.append(float(np.median(rp[selected,f,2])))
    nframes=len(data['p']);world=np.empty((nframes,len(names),3,3));localref=Rotation.from_quat(neutral_target[:,3:]).as_matrix()
    children={}
    for side in ('Left','Right'):
        children.update({side+'Shoulder':side+'Arm',side+'Arm':side+'ForeArm',side+'ForeArm':side+'Hand',
                         side+'Leg':side+'Shin',side+'Shin':side+'Foot',side+'Foot':side+'ToeBase'})
    calibrated={}
    for j,name in enumerate(names):
        if name in m:
            s=src[m[name]];sn=nsrc[nm[name]];target=tr[j]
            if name in children:
                child=children[name];direction=np0[nsrc[nm[child]]]-np0[sn]
                target=align_batch((tp[idx[child]]-tp[j])[None],direction[None])[0]@target
            elif name.endswith('Hand'):
                parent=idx[name.replace('Hand','ForeArm')]
                target=calibrated[parent]@tr[parent].T@tr[j]
            elif name.endswith('ToeBase'):
                parent=idx[name.replace('ToeBase','Foot')]
                target=calibrated[parent]@tr[parent].T@tr[j]
            correction=nr[sn].T@target
            if name.endswith('Foot'):
                side='Left' if name.startswith('Left') else 'Right';ids=foot_frames[side];rf=ri[rm[side+'Foot']];rt=ri[rm[side+'ToeBase']];rr=reference_samples['r'][ids,rf];forward_world=reference_samples['p'][ids,rt]-reference_samples['p'][ids,rf];forward_world[:,2]=0;forward_world/=np.maximum(np.linalg.norm(forward_world,axis=1,keepdims=True),1e-9)
                source_forward=unit(np.median(np.einsum('fji,fj->fi',rr,forward_world),axis=0));source_up=unit(np.median(np.einsum('fji,j->fi',rr,[0.,0.,1.]),axis=0));source_up=unit(source_up-source_forward*(source_up@source_forward))
                ref_forward=tp[idx[side+'ToeBase']]-tp[idx[side+'Foot']];ref_forward[2]=0;ref_forward=unit(ref_forward);target_forward=reference_r[j].T@ref_forward;target_up=reference_r[j].T@np.array([0.,0.,1.]);correction=np.column_stack((source_forward,source_up,np.cross(source_forward,source_up)))@np.column_stack((target_forward,target_up,np.cross(target_forward,target_up))).T;target=nr[sn]@correction
            if name.endswith(('Leg','Shin')):
                side='Left' if name.startswith('Left') else 'Right';h,k,a=[src[m[side+n]] for n in ('Leg','Shin','Foot')]
                u=data['p'][:,k]-data['p'][:,h];v=data['p'][:,a]-data['p'][:,k];plane=np.cross(u+v,u);strength=np.linalg.norm(plane,axis=1)/(np.linalg.norm(u,axis=1)*np.linalg.norm(v,axis=1));valid=strength>.20
                if valid.sum()>=4:
                    plane/=np.maximum(np.linalg.norm(plane,axis=1,keepdims=True),1e-9);local=np.einsum('fji,fj->fi',data['r'][:,s],plane);normal=np.median(local[valid],axis=0)
                    child=children[name];direction=data['p'][:,src[m[child]]]-data['p'][:,s];localdir=np.einsum('fji,fj->fi',data['r'][:,s],direction);localdir/=np.linalg.norm(localdir,axis=1,keepdims=True);source_dir=unit(np.median(localdir,axis=0));normal=unit(normal-source_dir*(normal@source_dir))
                    target_dir=unit(ref[idx[child],:3]);normal_world=np.array([-1.,0.,0.]);target_normal=reference_r[j].T@normal_world;target_normal=unit(target_normal-target_dir*(target_normal@target_dir))
                    correction=np.column_stack((source_dir,normal,np.cross(source_dir,normal)))@np.column_stack((target_dir,target_normal,np.cross(target_dir,target_normal))).T
                    target=nr[sn]@correction
            calibrated[j]=target
            world[:,j]=data['r'][:,s]@correction
        elif parents[j]>=0:world[:,j]=world[:,parents[j]]@localref[j]
        else:world[:,j]=localref[j]
    leg_source=float(np.median(np.linalg.norm(data['p'][:,src[m['LeftLeg']]]-data['p'][:,src[m['LeftShin']]],axis=1)+np.linalg.norm(data['p'][:,src[m['LeftShin']]]-data['p'][:,src[m['LeftFoot']]],axis=1)))
    leg_target=sum(np.linalg.norm(ref[idx['Left'+n],:3]) for n in ('Shin','Foot'));scale=leg_target/leg_source
    hip=src['Hips'];hip_mid=(data['p'][:,src[m['LeftLeg']]]+data['p'][:,src[m['RightLeg']]])*.5;model_hip_local=np.mean([ref[idx[s+'Leg'],:3] for s in ('Left','Right')],axis=0);model_hip_offset=np.einsum('fij,j->fi',world[:,0],model_hip_local);root=np.zeros((nframes,3));root[:,:2]=(hip_mid[:,:2]-hip_mid[0,:2])*scale-model_hip_offset[:,:2]+model_hip_offset[0,:2]
    target_ankle=float(np.mean([tp[idx[s+'Foot'],2] for s in ('Left','Right')]));root[:,2]=(hip_mid[:,2]-np.mean(ankle_references))*scale+target_ankle-model_hip_offset[:,2]
    original=local_from_world(world,root,ref,parents)
    # Distal toe channels are noisy in optical/inertial BVHs. Filter only these
    # local rotations (25ms sigma); re-fit the actual skinned soles afterwards.
    for side in ('Left','Right'):
        j=idx[side+'ToeBase'];q=original[:,j,3:].copy()
        for f in range(1,len(q)):
            if q[f]@q[f-1]<0:q[f]*=-1
        q=gaussian_filter1d(q,.75,axis=0,mode='nearest');q/=np.linalg.norm(q,axis=1,keepdims=True)
        original[:,j,3:]=q
    positions,rotations=forward(original,parents);skin=SkinFootHeights.soma(assets)
    actual=skin.evaluate(positions,rotations);goals=[];heights=[];supports=[]
    for k,side in enumerate(('Left','Right')):
        foot=src[m[side+'Foot']];toe=src[m[side+'ToeBase']]
        # BVH has no skin. This is explicitly an ankle/toe height proxy.
        z=np.minimum(data['p'][:,foot,2],data['p'][:,toe,2]);floor=np.percentile(z,3)
        h=np.maximum(.0005,(z-floor)*scale);heights.append(h)
        v=np.linalg.norm(np.gradient(data['p'][:,toe,:2],axis=0)*data['fps'],axis=1)*scale
        support=(h<.018)&(v<.28);supports.append(support)
        goal=positions[:,idx[side+'Foot']].copy()
        # Preserve measured planted foot travel while adapting different hip widths.
        delta=data['p'][:,foot,:2]-data['p'][:,src[m[side+'Leg']],:2]
        goal[:,:2]=positions[:,idx[side+'Leg'],:2]+delta*scale
        if stance_width_extra_m:
            lateral=np.einsum('fij,j->fi',world[:,0],tr[0].T@np.array([1.,0.,0.]))
            lateral=lateral[:,:2];lateral/=np.maximum(np.linalg.norm(lateral,axis=1,keepdims=True),1e-8)
            goal[:,:2]+=lateral*stance_width_extra_m*(1 if side=='Left' else -1)
        goal[:,2]+=h-actual[:,k];goals.append(goal)
    desired=np.stack(heights,axis=1)
    if not allow_flight:
        # Walking/standing/seat actions always have a supporting foot. A BVH
        # ankle/toe proxy must not turn measured foot roll into whole-body float.
        grounded=desired-np.min(desired,axis=1,keepdims=True)+.0005
        for k in range(2):goals[k][:,2]+=grounded[:,k]-desired[:,k]
        desired=grounded
        supports=[desired[:,k]<.018 for k in range(2)]
    original_r=rotations.copy();root=original[:,0,:3].copy()
    for iteration in range(6):
        p,r=forward(local_from_world(original_r,root,ref,parents),parents)
        for k,side in enumerate(('Left','Right')):
            a,b,c=[idx[side+n] for n in ('Leg','Shin','Foot')];u=np.linalg.norm(ref[b,:3]);v=np.linalg.norm(ref[c,:3])
            cap=goals[k][:,2]+np.sqrt(np.maximum(1e-5,(u+v-1e-5)**2-np.sum((goals[k][:,:2]-p[:,a,:2])**2,axis=1)))-(p[:,a,2]-root[:,2])
            root[:,2]=np.minimum(root[:,2],cap)
        lowering=np.maximum(0.,original[:,0,2]-root[:,2])
        lowering=np.maximum(lowering,gaussian_filter1d(maximum_filter1d(lowering,size=5,mode='nearest'),1.,mode='nearest'))
        root[:,2]=original[:,0,2]-lowering
        p,r=forward(local_from_world(original_r,root,ref,parents),parents)
        for k,side in enumerate(('Left','Right')):
            a,b,c=[idx[side+n] for n in ('Leg','Shin','Foot')];u=np.linalg.norm(ref[b,:3]);v=np.linalg.norm(ref[c,:3]);h=p[:,a];goal=goals[k]
            direction=goal-h;distance=np.linalg.norm(direction,axis=1);direction/=np.maximum(distance[:,None],1e-9);d=np.clip(distance,abs(u-v)+1e-6,u+v-1e-6)
            # Transport the knee HINGE NORMAL, not a forward pole vector.
            # Projecting a forward vector flips the knee when a high foot
            # target crosses the pelvis plane during a vault.
            normal=reference_r[a].T@np.array([-1.,0.,0.]);normal=np.einsum('fij,j->fi',original_r[:,a],normal)
            pole=np.cross(normal,direction);pole/=np.maximum(np.linalg.norm(pole,axis=1,keepdims=True),1e-9)
            along=(u*u-v*v+d*d)/(2*d);middle=h+direction*along[:,None]+pole*np.sqrt(np.maximum(0,u*u-along*along))[:,None]
            r[:,a]=align_batch(p[:,b]-h,middle-h)@original_r[:,a]
            r[:,b]=align_batch(p[:,c]-p[:,b],h+direction*d[:,None]-middle)@original_r[:,b]
        result=local_from_world(r,root,ref,parents);p,r=forward(result,parents);actual=skin.evaluate(p,r)
        for k in range(2):goals[k][:,2]+=desired[:,k]-actual[:,k]
    for f in range(1,len(result)):
        negative=np.sum(result[f-1,:,3:]*result[f,:,3:],axis=1)<0;result[f,negative,3:]*=-1
    return result.astype(np.float32),dict(scale=float(scale),mapping=m,neutral_frame=nf,desired_sole=desired,actual_sole=actual,
        support=np.stack(supports,axis=1),before=original.astype(np.float32),source_positions=data['p'],source_names=data['names'],
        largest_pelvis_lowering_m=float((root[:,2]-original[:,0,2]).min()))

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
