"""Retarget permitted reference motion using anatomical frames and planted feet.

Reference-derived files retain their actual source and license; they must never
be labelled as independently authored or as originating from a static pose.
"""
import math
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
from scipy.ndimage import gaussian_filter1d,minimum_filter1d
from .studio_original_library import AdultPerformance,aim_rotation,axis,align

def unit(v):
    return v/max(np.linalg.norm(v),1e-9)

def body_frame(left,right,up):
    x=unit(left-right);y=unit(np.cross(up,x));z=unit(np.cross(x,y))
    return np.column_stack((x,y,z))

def clean_directions(vectors,maximum=20.):
    vectors=np.asarray(vectors,dtype=float)
    if vectors.ndim!=2 or vectors.shape[1]!=3 or not len(vectors) or not np.isfinite(vectors).all():
        raise ValueError('Expected finite direction vectors [frames, 3]')
    lengths=np.linalg.norm(vectors,axis=-1);good=lengths>np.median(lengths)*.55
    if not good.any():raise ValueError('No usable tracked limb directions')
    ids=np.flatnonzero(good);out=[]
    for i,v in enumerate(vectors):
        if not good[i]:
            left=ids[max(0,np.searchsorted(ids,i)-1)];right=ids[min(len(ids)-1,np.searchsorted(ids,i))]
            if left==right:v=vectors[left]
            else:
                a=unit(vectors[left]);b=unit(vectors[right]);delta=Rotation.from_matrix(align(a,b)).as_rotvec()
                v=Rotation.from_rotvec(delta*(i-left)/(right-left)).apply(a)
        desired=unit(v)
        if out:
            rotation=Rotation.from_matrix(align(out[-1],desired));angle=rotation.magnitude()
            if angle>math.radians(maximum):desired=Rotation.from_rotvec(rotation.as_rotvec()*math.radians(maximum)/angle).apply(out[-1])
        out.append(desired)
    return np.array(out)

def read_bvh(path):
    import warp as wp
    from motionbricks.io.bvh import _read_bvh
    with wp.ScopedDevice('cpu'):skeleton,samples,channels,fps=_read_bvh(path,True)
    names=list(skeleton.joint_names);parents=skeleton._np_parent_indices
    positions=np.broadcast_to(skeleton.reference_local_transforms.numpy()[None,:,:3],(len(samples),len(names),3)).copy()
    rotations=np.broadcast_to(np.eye(3),(len(samples),len(names),3,3)).copy();column=0
    for j,labels in enumerate(channels):
        order=[];values=[]
        for label in labels:
            if label.endswith('position'):positions[:,j,'XYZ'.index(label[0])]=samples[:,column]*.01
            else:order.append(label[0]);values.append(samples[:,column])
            column+=1
        if order:rotations[:,j]=Rotation.from_euler(''.join(order),np.stack(values,axis=-1),degrees=True).as_matrix()
    for j,parent in enumerate(parents):
        if parent>=0:
            positions[:,j]=np.einsum('fij,fj->fi',rotations[:,parent],positions[:,j])+positions[:,parent]
            rotations[:,j]=rotations[:,parent]@rotations[:,j]
    return names,positions,rotations,float(fps)

def bvh_landmarks(path):
    names,p,r,fps=read_bvh(path)
    def find(*options):return next(names.index(n) for n in options if n in names)
    mapping=dict(root=find('Hips'),spine=find('Spine','Chest'),chest=find('Spine1','Chest4','Spine2'),neck=find('Neck'),head=find('Head'))
    for side,short in [('Left','L'),('Right','R')]:
        for key,opts in [('hip',('UpLeg','Hip')),('knee',('Leg','Knee')),('ankle',('Foot','Ankle')),('toe',('ToeBase','Toe')),('collar',('Collar','Shoulder')),('shoulder',('Arm','Shoulder')),('elbow',('ForeArm','Elbow')),('wrist',('Hand','Wrist'))]:
            mapping[short+key]=find(*[side+o for o in opts])
    # BVH source families in this pipeline are Y-up. Normalize the initial
    # anatomical heading only; preserve all subsequent turns and root travel.
    if 'Z_UP_WORLD_ORIGIN' in names:p*=100.
    else:
        convert=axis([1,0,0],math.pi/2);p=np.einsum('ij,fnj->fni',convert,p);r=convert@r
    x=np.mean(p[:5,mapping['Lhip']]-p[:5,mapping['Rhip']],axis=0);yaw=math.atan2(x[1],x[0])
    convert=axis([0,0,1],-yaw);p=np.einsum('ij,fnj->fni',convert,p);r=convert@r
    p={key:p[:,index] for key,index in mapping.items()};rot={'root':r[:,mapping['root']],'head':r[:,mapping['head']],'Lfoot':r[:,mapping['Lankle']],'Rfoot':r[:,mapping['Rankle']]}
    return p,rot,fps

def resample_landmarks(points,rotations,fps,start=0.,end=None):
    length=len(next(iter(points.values())));end=(length-1)/fps if end is None else min(end,(length-1)/fps)
    ts=np.arange(round((end-start)*30)+1)/30+start;source=np.arange(length)/fps;ts=np.minimum(ts,source[-1])
    result={key:np.stack([np.interp(ts,source,p[:,i]) for i in range(3)],axis=-1) for key,p in points.items()}
    result_rot={key:(Slerp(source,Rotation.from_matrix(r))(ts).as_matrix() if r.ndim==3 else np.interp(ts,source,r)) for key,r in rotations.items()}
    return result,result_rot

def video_landmarks(path):
    data=np.load(path);w=data['world'];n=data['normalized'];fps=float(data['fps']);aspect=float(data['aspect']) if 'aspect' in data else 9/16
    for a in (w,n):
        for j in range(a.shape[1]):
            for k in range(3):
                good=np.isfinite(a[:,j,k])
                if not good.any():raise ValueError(f'Landmark {j} has no usable observations')
                a[:,j,k]=np.interp(np.arange(len(a)),np.flatnonzero(good),a[good,j,k])
    w=w[:,:,[0,2,1]].copy();w[:,:,2]*=-1
    leg=np.mean([np.median(np.linalg.norm(w[:,h]-w[:,k],axis=-1)+np.linalg.norm(w[:,k]-w[:,a],axis=-1)) for h,k,a in [(23,25,27),(24,26,28)]])
    w*=.857/leg
    # The camera is fixed in the supplied portrait videos. Use screen-space
    # translation/foot height, retaining estimated depth only within the body.
    hip=(n[:,23]+n[:,24])/2
    floor=np.percentile(n[:,[29,30,31,32],1],97)
    body=np.percentile(np.max(n[:,[27,28],1],axis=1)-n[:,0,1],85)+.10
    meters=1.77/body
    root=np.column_stack(((hip[:,0]-hip[0,0])*meters*aspect,np.zeros(len(w)),(floor-hip[:,1])*meters))
    w+=root[:,None,:]
    flex={}
    for side,h,k,a in [('L',23,25,27),('R',24,26,28)]:
        u=w[:,k]-w[:,h];v=w[:,a]-w[:,k]
        flex[side+'knee_angle']=gaussian_filter1d(np.arccos(np.clip(np.sum(u*v,axis=-1)/(np.linalg.norm(u,axis=-1)*np.linalg.norm(v,axis=-1)),-1,1)),1.5)
    # Monocular world estimates occasionally collapse an occluded forearm to a
    # few centimeters. Lift the reliable image-space direction to a fixed
    # anatomical length; depth sign uses the estimate with temporal hysteresis.
    for shoulder,elbow,wrist,index,pinky in [(11,13,15,19,17),(12,14,16,20,18)]:
        old_wrist=w[:,wrist].copy()
        for a,b,length in [(shoulder,elbow,.29),(elbow,wrist,.27)]:
            dx=(n[:,b,0]-n[:,a,0])*meters*aspect;dz=-(n[:,b,1]-n[:,a,1])*meters
            projection=np.hypot(dx,dz);factor=np.minimum(1.,length*.995/np.maximum(projection,1e-8));dx*=factor;dz*=factor
            depth=np.sqrt(np.maximum(0.,length*length-dx*dx-dz*dz));estimated=w[:,b,1]-w[:,a,1]
            sign=-1.;values=[]
            for i in range(len(w)):
                if depth[i]<.09 and abs(estimated[i])>.025:sign=1. if estimated[i]>0 else -1.
                values.append(sign*depth[i])
            dy=gaussian_filter1d(np.array(values),2.,mode='nearest')
            w[:,b]=w[:,a]+np.stack((dx,dy,dz),axis=-1)
        shift=w[:,wrist]-old_wrist
        for j in (index,pinky):w[:,j]+=shift
    points=dict(root=root,spine=(root+(w[:,11]+w[:,12])/2)/2,chest=(w[:,11]+w[:,12])/2,neck=(w[:,11]+w[:,12])/2,head=(w[:,2]+w[:,5])/2,Leye=w[:,2],Reye=w[:,5])
    for side,hip_i,knee,ankle,toe,shoulder,elbow,wrist,index,pinky in [('L',23,25,27,31,11,13,15,19,17),('R',24,26,28,32,12,14,16,20,18)]:
        for key,j in [('hip',hip_i),('knee',knee),('ankle',ankle),('toe',toe),('shoulder',shoulder),('elbow',elbow),('wrist',wrist),('index',index),('pinky',pinky)]:points[side+key]=w[:,j].copy()
        points[side+'collar']=points['neck']+.35*(w[:,shoulder]-points['neck'])
        points[side+'palm']=(w[:,index]+w[:,pinky])/2
        for key,j in [('ankle',ankle),('toe',toe)]:
            points[side+key][:,0]=(n[:,j,0]-hip[0,0])*meters*aspect
            points[side+key][:,2]=(floor-n[:,j,1])*meters
        points[side+'toe'][:,1]=points[side+'ankle'][:,1]-.12
    eyes=w[:,2]-w[:,5];face_up=(w[:,2]+w[:,5]-w[:,9]-w[:,10])/2
    yaw=np.clip(np.unwrap(np.arctan2(eyes[:,1],eyes[:,0])),-1.05,1.05)
    roll=np.clip(np.arctan2(n[:,2,1]-n[:,5,1],(n[:,2,0]-n[:,5,0])*aspect),-.45,.45)
    pitch=np.arctan2(-face_up[:,1],face_up[:,2]);pitch=np.clip((pitch-np.median(pitch[:12]))*.5,-.35,.35)
    angles=gaussian_filter1d(np.stack([yaw,roll,pitch],axis=-1),1.5,axis=0,mode='nearest')
    head=Rotation.from_euler('zyx',angles).as_matrix()
    return points,dict(head=head,**flex),fps

class ReferenceRetargeter(AdultPerformance):
    def stable_aim(self,key,reference,direction,normal):
        a=unit(reference);b=unit(direction);refnormal=unit(np.cross(a,[0.,-1,0]))
        previous=self._previous_orientation.get(key)
        if previous is None:return aim_rotation(reference,direction,normal)
        transported=align(previous@a,b)@previous
        current=unit(transported@refnormal);desired=normal-b*(normal@b)
        if np.linalg.norm(desired)<.1:return transported
        desired=unit(desired);angle=math.atan2(b@np.cross(current,desired),np.clip(current@desired,-1,1))
        return axis(b,float(np.clip(angle,-math.radians(10),math.radians(10))))@transported

    def solve_leg(self,pose,side,target):
        super().solve_leg(pose,side,target)
        for name,child in [('Leg','Shin'),('Shin','Foot')]:
            a=self.index[side+name];b=self.index[side+child];world=self.world(pose)
            reference=self.rest[b,:3,3]-self.rest[a,:3,3];direction=world[b,:3,3]-world[a,:3,3]
            delta=world[a,:3,:3]@self.rest[a,:3,:3].T;normal=delta@unit(np.cross(unit(reference),[0.,-1,0]))
            rotation=self.stable_aim(side+name,reference,direction,normal)
            self.set_world_rotation(pose,side+name,rotation@self.rest[a,:3,:3])
        self.set_world_rotation(pose,side+'Foot',target['foot_rotation'])
        self.set_world_rotation(pose,side+'ToeBase',target['toe_rotation'])

    def retarget(self,points,rotations=None,video=False):
        self._previous_orientation={}
        rotations=rotations or {};points={k:gaussian_filter1d(np.asarray(v,dtype=float),.8 if video else .45,axis=0,mode='nearest') for k,v in points.items()}
        lengths=[]
        for side in ('L','R'):
            lengths.append(np.median(np.linalg.norm(points[side+'hip']-points[side+'knee'],axis=-1)+np.linalg.norm(points[side+'knee']-points[side+'ankle'],axis=-1)))
        target_length=sum(np.linalg.norm(self.ref[self.index['Left'+n],:3]) for n in ('Shin','Foot'))
        scale=1. if video else target_length/np.mean(lengths)
        hip_mid=(points['Lhip']+points['Rhip'])/2
        ankle_low=min(np.percentile(points[s+'ankle'][:,2],5) for s in ('L','R'))
        offset=np.r_[-hip_mid[0,:2]*scale,.073-ankle_low*scale]
        points={k:p*scale+offset for k,p in points.items()};hip_mid=(points['Lhip']+points['Rhip'])/2
        video_lifts={}
        if video:
            # Image ankle heights and estimated toe angles are inconsistent in
            # shoes/occlusion. A binary ground snap produces an ankle jump when
            # its support flag changes. Use a continuous sole-height target
            # throughout lift-off and landing; retain image-space foot lifts.
            for side,s in [('Left','L'),('Right','R')]:
                z=points[s+'toe'][:,2];height=np.maximum(0.,z-np.percentile(z,5)-.012)
                lift=gaussian_filter1d(height*height/(height+.025),1.,mode='nearest')
                video_lifts[s]=lift
                points[s+'ankle'][:,2]=self.rest[self.index[side+'Foot'],2,3]+self.support_z+lift
        root_rotation=[];chest_rotation=[]
        for i in range(len(hip_mid)):
            root_rotation.append(body_frame(points['Lhip'][i],points['Rhip'][i],points['spine'][i]-hip_mid[i]))
            chest_rotation.append(body_frame(points['Lshoulder'][i],points['Rshoulder'][i],points['neck'][i]-points['spine'][i]))
        root_rotation=np.array(root_rotation);chest_rotation=np.array(chest_rotation)
        if 'root' in rotations:
            # Preserve the measured pelvis rotation independently of the spine.
            root_rotation=rotations['root']@rotations['root'][0].T@root_rotation[0]
        head_rotation=(rotations['head'] if video else rotations['head']@rotations['head'][0].T) if 'head' in rotations else chest_rotation.copy()
        source_toe_low={s:np.percentile(points[s+'toe'][:,2],5) for s in ('L','R')}
        baseline={};contact={};foot_calibration={};leg_normals={}
        for s in ('L','R'):
            direction=points[s+'toe']-points[s+'ankle'];angles=np.arctan2(-direction[:,2],np.linalg.norm(direction[:,:2],axis=-1))
            low=points[s+'toe'][:,2]<source_toe_low[s]+.03
            baseline[s]=np.median(angles[low]) if low.any() else np.median(angles)
            velocity=np.linalg.norm(np.gradient(points[s+'toe'][:,:2],axis=0)*30,axis=-1)
            contact[s]=(video_lifts[s]<.001) if video else low&(velocity<.65)
            if s+'foot' in rotations:
                idx=int(np.argmin(np.abs(angles-baseline[s])+velocity*.025))
                yaw=math.atan2(direction[idx,0],-direction[idx,1])
                foot_calibration[s]=(rotations[s+'foot'][idx].T,axis([0,0,1],yaw))
            normals=[]
            for i in range(len(hip_mid)):
                forward=direction[i].copy();forward[2]=0
                fallback=-root_rotation[i,:,0]
                a=unit(points[s+'ankle'][i]-points[s+'hip'][i]);b=unit(points[s+'knee'][i]-points[s+'hip'][i]);normal=np.cross(a,b)
                if video or np.linalg.norm(normal)<.10:normal=fallback
                else:
                    normal=unit(normal)
                    if normal@fallback<0:normal=-normal
                    normal=unit(.8*normal+.2*fallback)
                normals.append(normal)
            leg_normals[s]=gaussian_filter1d(np.array(normals),1.,axis=0,mode='nearest')
        arm_normals={};arm_directions={}
        for s in ('L','R'):
            raw_upper=points[s+'elbow']-points[s+'shoulder'];raw_lower=points[s+'wrist']-points[s+'elbow']
            arm_directions[s+'upper']=clean_directions(raw_upper) if video else np.array([unit(v) for v in raw_upper])
            arm_directions[s+'lower']=clean_directions(raw_lower) if video else np.array([unit(v) for v in raw_lower])
            normals=[]
            for i in range(len(hip_mid)):
                upper=unit(points[s+'elbow'][i]-points[s+'shoulder'][i]);lower=unit(points[s+'wrist'][i]-points[s+'elbow'][i]);normal=np.cross(upper,lower)
                if np.linalg.norm(normal)<.20:normal=normals[-1] if normals else -chest_rotation[i,:,0]
                else:
                    normal=unit(normal)
                    if normals and normal@normals[-1]<0:normal=-normal
                if normals:
                    angle=math.acos(np.clip(normal@unit(normals[-1]),-1,1))
                    if angle>math.radians(15):normal=unit(normals[-1]*(1-math.radians(15)/angle)+normal*(math.radians(15)/angle))
                normals.append(normal)
            arm_normals[s]=gaussian_filter1d(np.array(normals),1.2,axis=0,mode='nearest')
        video_root_z=None
        hip_reference=np.mean([self.rest[self.index[s+'Leg'],:3,3]-self.rest[0,:3,3] for s in ('Left','Right')],axis=0)
        if video:
            values=[]
            for i in range(len(hip_mid)):
                root=hip_mid[i]-root_rotation[i]@hip_reference;goals=[];weights=[];limits=[]
                for side,s in [('Left','L'),('Right','R')]:
                    hip=root+root_rotation[i]@(self.rest[self.index[side+'Leg'],:3,3]-self.rest[0,:3,3]);ankle=points[s+'ankle'][i]
                    u=np.linalg.norm(self.ref[self.index[side+'Shin'],:3]);v=np.linalg.norm(self.ref[self.index[side+'Foot'],:3]);theta=float(np.clip(rotations[s+'knee_angle'][i],.08,2.1));horizontal2=np.sum((ankle[:2]-hip[:2])**2)
                    goals.append(ankle[2]+math.sqrt(max(.005,u*u+v*v+2*u*v*math.cos(theta)-horizontal2))-(hip[2]-root[2]))
                    limits.append(ankle[2]+math.sqrt(max(.005,(u+v-.008)**2-horizontal2))-(hip[2]-root[2]))
                    weights.append(math.exp(-max(0.,ankle[2]-.073)/.045))
                values.append(min(float(np.average(goals,weights=weights)),min(limits)))
            video_root_z=gaussian_filter1d(minimum_filter1d(np.array(values),size=3,mode='nearest'),1.5,mode='nearest')
        poses=[];contacts=[];target_feet=[]
        for frame in range(len(hip_mid)):
            h=root_rotation[frame];c=chest_rotation[frame];pose=self.ref.copy()
            pose[0,:3]=hip_mid[frame]-h@hip_reference;pose[0,3:]=Rotation.from_matrix(h@self.rest[0,:3,:3]).as_quat()
            if video_root_z is not None:pose[0,2]=video_root_z[frame]
            delta=Rotation.from_matrix(h.T@c).as_rotvec()
            for name,f in [('Spine1',.35),('Spine2',.7),('Chest',1.)]:self.set_world_rotation(pose,name,h@Rotation.from_rotvec(delta*f).as_matrix()@self.rest[self.index[name],:3,:3])
            head=head_rotation[frame];delta=Rotation.from_matrix(c.T@head).as_rotvec()
            for name,f in [('Neck1',.35),('Neck2',.7),('Head',1.)]:self.set_world_rotation(pose,name,c@Rotation.from_rotvec(delta*f).as_matrix()@self.rest[self.index[name],:3,:3])
            for side,s in [('Left','L'),('Right','R')]:
                upper=arm_directions[s+'upper'][frame];lower=arm_directions[s+'lower'][frame]
                normal=arm_normals[s][frame]
                # Preserve collar lift before orienting each upper/lower arm.
                refdir=self.rest[self.index[side+'Arm'],:3,3]-self.rest[self.index[side+'Shoulder'],:3,3]
                direction=points[s+'shoulder'][frame]-points[s+'collar'][frame]
                if np.linalg.norm(direction)>1e-5:self.set_world_rotation(pose,side+'Shoulder',align(c@refdir,direction)@c@self.rest[self.index[side+'Shoulder'],:3,:3])
                for name,child,direction in [('Arm','ForeArm',upper),('ForeArm','Hand',lower)]:
                    refdir=self.rest[self.index[side+child],:3,3]-self.rest[self.index[side+name],:3,3]
                    self.set_world_rotation(pose,side+name,self.stable_aim(side+name,refdir,direction,normal)@self.rest[self.index[side+name],:3,:3])
                if s+'palm' in points:
                    forward=unit(points[s+'palm'][frame]-points[s+'wrist'][frame])
                    world=self.world(pose);current=world[self.index[side+'Hand'],:3,:3]
                    local= self.rest[self.index[side+'Hand'],:3,:3].T@(self.rest[self.index[side+'HandMiddle2'],:3,3]-self.rest[self.index[side+'Hand'],:3,3])
                    reference=unit(current@local);angle=math.acos(np.clip(reference@forward,-1,1))
                    if angle>1.05:forward=unit(reference*(1-1.05/angle)+forward*(1.05/angle))
                    self.set_world_rotation(pose,side+'Hand',align(reference,forward)@current)
                    if video and poses:
                        i=self.index[side+'Hand'];previous=Rotation.from_quat(poses[-1][i,3:]);current=Rotation.from_quat(pose[i,3:]);delta=previous.inv()*current;angle=delta.magnitude()
                        if angle>math.radians(12):pose[i,3:]=(previous*Rotation.from_rotvec(delta.as_rotvec()*math.radians(12)/angle)).as_quat()
            self.fingers(pose,.18)
            feet={}
            for side,s in [('Left','L'),('Right','R')]:
                forward=points[s+'toe'][frame]-points[s+'ankle'][frame];yaw=math.atan2(forward[0],-forward[1]);pitch=math.atan2(-forward[2],np.linalg.norm(forward[:2]))-baseline[s]
                pitch=0. if video else float(np.clip(pitch,-.65,1.15));turn=axis([0,0,1],yaw);r=turn@axis([1,0,0],pitch)
                if s in foot_calibration:r=rotations[s+'foot'][frame]@foot_calibration[s][0]@foot_calibration[s][1]
                direction=unit(points[s+'ankle'][frame]-points[s+'hip'][frame]);pole=h.T@unit(np.cross(leg_normals[s][frame],direction))
                proximity=float(np.clip((source_toe_low[s]+.07-points[s+'toe'][frame,2])/.07,0,1))
                compensate=proximity*float(np.clip((pitch-.05)/.4,0,1))
                toe=r@axis([1,0,0],-pitch*compensate)
                feet[side]=dict(ankle=points[s+'ankle'][frame].copy(),foot_rotation=r@self.rest[self.index[side+'Foot'],:3,:3],toe_rotation=toe@self.rest[self.index[side+'ToeBase'],:3,:3],support=bool(contact[s][frame]),knee_pole=pole)
            pose=self.finish(pose,feet)
            world=self.world(pose)
            self._previous_orientation={side+name:world[self.index[side+name],:3,:3]@self.rest[self.index[side+name],:3,:3].T for side in ('Left','Right') for name in ('Leg','Shin','Arm','ForeArm')}
            poses.append(pose);contacts.append([feet[s]['support'] for s in ('Left','Right')]);target_feet.append({s:t['ankle'].copy() for s,t in feet.items()})
        poses=np.array(poses,dtype=np.float32)
        for i in range(1,len(poses)):
            neg=np.sum(poses[i-1,:,3:]*poses[i,:,3:],axis=-1)<0;poses[i,neg,3:]*=-1
        return poses,np.array(contacts),target_feet

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
