"""Offline whole-sequence fitting to a user-authorized fixed-camera video.

Image reprojection, temporal coherence, face orientation and body separation
are optimized together. Depth remains an estimate, not measured mocap.
"""
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix
from scipy.spatial.transform import Rotation,Slerp


def face_orientation(normalized,face_path=None,pitch_offset_degrees=0.):
    """Studio X right / Y away / Z up. Preserve turns also in detection gaps."""
    n=np.asarray(normalized);ears=(n[:,7]+n[:,8])/2
    width=np.maximum(np.abs(n[:,7,0]-n[:,8,0]),.018)
    yaw=np.arctan2((n[:,0,0]-ears[:,0])*1.5,width)
    roll=np.arctan2(n[:,2,1]-n[:,5,1],(n[:,2,0]-n[:,5,0])*(9/16))
    fallback=np.stack((np.clip(yaw,-1.2,1.2),np.clip(roll,-.6,.6),np.zeros(len(n))),axis=-1)
    angles=fallback.copy();observed=np.zeros(len(n),bool)
    if face_path is not None and Path(face_path).exists():
        matrices=np.load(face_path)['matrices'];observed=np.isfinite(matrices).all(axis=(1,2))
        ids=np.flatnonzero(observed)
        if len(ids)>2:
            convert=np.array([[1.,0,0],[0,0,-1.],[0,1.,0]])
            # Remove the uniform scale returned with the face transform.
            u,_,v=np.linalg.svd(matrices[ids,:3,:3]);rotation=convert@(u@v)@convert.T
            measured=Rotation.from_matrix(rotation).as_euler('zyx')
            # Cartoon eyes/occlusion occasionally produce an inverted facial
            # frame. Reject it against image nose/ear direction instead of
            # unwrapping it into a fictitious full head revolution.
            for j,limit in enumerate((1.3,.7,.6)):
                measured[:,j]=np.clip(measured[:,j],-limit,limit)
                if j<2:
                    invalid=np.abs(measured[:,j]-fallback[ids,j])>.75
                    measured[invalid,j]=fallback[ids[invalid],j]
                angles[:,j]=np.interp(np.arange(len(n)),ids,measured[:,j])
            # Landmark nose/ear displacement remains available when an anime
            # profile is missed by the face detector. Never hold the first
            # detected frontal face over an earlier profile section.
            angles[:,0]=np.where(observed,.65*angles[:,0]+.35*fallback[:,0],fallback[:,0])
            angles[:,1]=np.where(observed,.7*angles[:,1]+.3*fallback[:,1],fallback[:,1])
            # Stylized face proportions can introduce a constant pitch bias.
            # The offset is a reviewed per-reference calibration, not a claim
            # that the detector measures an absolute head angle accurately.
            angles[:,2]-=np.deg2rad(pitch_offset_degrees)
            # Interpolate internal tracking gaps rather than inserting a nod
            # toward zero every time the face detector loses the profile.
            outside=(np.arange(len(n))<ids[0])|(np.arange(len(n))>ids[-1])
            angles[outside,2]=0.
    angles=gaussian_filter1d(angles,1.5,axis=0,mode='nearest')
    return Rotation.from_euler('zyx',angles).as_matrix(),observed


def segment_distance(a,b,c,d):
    """Closest distance between finite segments, including parallel cases."""
    u=b-a;v=d-c;w=a-c
    aa=np.sum(u*u,axis=-1);bb=np.sum(u*v,axis=-1);cc=np.sum(v*v,axis=-1)
    dd=np.sum(u*w,axis=-1);ee=np.sum(v*w,axis=-1)
    det=aa*cc-bb*bb
    s=np.clip((bb*ee-cc*dd)/np.maximum(det,1e-12),0,1)
    t=np.clip((bb*s+ee)/np.maximum(cc,1e-12),0,1)
    s=np.clip((bb*t-dd)/np.maximum(aa,1e-12),0,1)
    return np.linalg.norm(a+s[...,None]*u-c-t[...,None]*v,axis=-1)


def ellipsoid_front_y(points,center,rotation,radii):
    """Camera-facing ellipsoid surface along +Y rays through image X/Z."""
    metric=(rotation/np.asarray(radii)[None,None,:]**2)@rotation.swapaxes(-1,-2)
    dx=points[:,:,0]-center[:,0,None];dz=points[:,:,2]-center[:,2,None]
    a=metric[:,1,1,None]
    b=2*(metric[:,1,0,None]*dx+metric[:,1,2,None]*dz)
    c=metric[:,0,0,None]*dx*dx+2*metric[:,0,2,None]*dx*dz+metric[:,2,2,None]*dz*dz-1.
    discriminant=b*b-4*a*c
    front=center[:,1,None]+(-b-np.sqrt(np.maximum(0.,discriminant)))/(2*a)
    return front,discriminant>=0.


def smooth_world_motion(poses,parents,sigma=1.2,max_step_degrees=12.):
    """Two-sided world-space filtering; preserve bone offsets and cap steps.

World limits prevent several individually small spine rotations accumulating
into a torso twitch. Reconstruction keeps local bone lengths unchanged.
"""
    poses=np.asarray(poses);frames,joints=poses.shape[:2]
    world=Rotation.from_quat(poses[:,:,3:].reshape(-1,4)).as_matrix().reshape(frames,joints,3,3)
    for j,parent in enumerate(parents):
        if parent>=0:world[:,j]=world[:,parent]@world[:,j]
    q=Rotation.from_matrix(world.reshape(-1,3,3)).as_quat().reshape(frames,joints,4)
    for f in range(1,frames):q[f,np.sum(q[f-1]*q[f],axis=-1)<0]*=-1
    q=gaussian_filter1d(q,sigma,axis=0,mode='nearest');q/=np.linalg.norm(q,axis=-1,keepdims=True)
    world=Rotation.from_quat(q.reshape(-1,4)).as_matrix().reshape(frames,joints,3,3)
    limit=np.deg2rad(max_step_degrees)
    for order in (range(1,frames),range(frames-2,-1,-1)):
        forward=isinstance(order,range) and order.step>0
        for f in order:
            neighbor=f-1 if forward else f+1
            delta=Rotation.from_matrix(world[neighbor].swapaxes(-1,-2)@world[f]).as_rotvec()
            angle=np.linalg.norm(delta,axis=-1);delta*=np.minimum(1.,limit/np.maximum(angle,1e-10))[:,None]
            world[f]=world[neighbor]@Rotation.from_rotvec(delta).as_matrix()
    local=world.copy()
    for j,parent in enumerate(parents):
        if parent>=0:local[:,j]=world[:,parent].swapaxes(-1,-2)@world[:,j]
    out=poses.copy();out[:,:,3:]=Rotation.from_matrix(local.reshape(-1,3,3)).as_quat().reshape(frames,joints,4)
    out[:,0,:3]=gaussian_filter1d(out[:,0,:3],sigma*.6,axis=0,mode='nearest')
    for f in range(1,frames):out[f,np.sum(out[f-1,:,3:]*out[f,:,3:],axis=-1)<0,3:]*=-1
    return out


def restore_limb_targets(rig,smoothed,originals):
    """Keep fitted hands/feet after filtering the torso's composed rotations.

Independent world rotation filtering shifts endpoints through the FK tree.
Restore them with two-bone IK and swing-only orientation corrections, retaining
the filtered axial twist instead of introducing a new bend-plane flip.
"""
    from .studio_original_library import align
    out=smoothed.copy();out[:,0,:3]=originals[:,0,:3]
    for f,pose in enumerate(out):
        original=rig.world(originals[f])
        for side in ('Left','Right'):
            for chain in (('Leg','Shin','Foot'),('Arm','ForeArm','Hand')):
                a,b,c=[rig.index[side+j] for j in chain];world=rig.world(pose)
                origin=world[a,:3,3];goal=original[c,:3,3].copy()
                u=np.linalg.norm(rig.ref[b,:3]);v=np.linalg.norm(rig.ref[c,:3])
                delta=goal-origin;distance=np.linalg.norm(delta);direction=delta/max(distance,1e-9)
                d=float(np.clip(distance,abs(u-v)+1e-6,u+v-1e-6));goal=origin+direction*d
                pole=original[b,:3,3]-origin;pole-=direction*(pole@direction)
                if np.linalg.norm(pole)<1e-5:pole=world[b,:3,3]-origin;pole-=direction*(pole@direction)
                pole/=max(np.linalg.norm(pole),1e-9);along=(u*u-v*v+d*d)/(2*d)
                middle=origin+direction*along+pole*np.sqrt(max(0.,u*u-along*along))
                upper=align(world[b,:3,3]-origin,middle-origin)@world[a,:3,:3]
                lower=align(world[c,:3,3]-world[b,:3,3],goal-middle)@world[b,:3,:3]
                rig.set_world_rotation(pose,side+chain[0],upper)
                rig.set_world_rotation(pose,side+chain[1],lower)
                rig.set_world_rotation(pose,side+chain[2],original[c,:3,:3])
                if chain[2]=='Foot':rig.set_world_rotation(pose,side+'ToeBase',original[rig.index[side+'ToeBase'],:3,:3])
    return out


def remove_rotation_outlier_frames(poses,parents,limit_degrees=23.):
    """Replace brief tracking spikes as complete poses, preserving correlations."""
    out=np.asarray(poses).copy();discarded=set()
    for iteration in range(4):
        matrices=Rotation.from_quat(out[:,:,3:].reshape(-1,4)).as_matrix().reshape(len(out),out.shape[1],3,3)
        local_step=Rotation.from_matrix((matrices[:-1].swapaxes(-1,-2)@matrices[1:]).reshape(-1,3,3)).magnitude().reshape(len(out)-1,-1)
        for j,parent in enumerate(parents):
            if parent>=0:matrices[:,j]=matrices[:,parent]@matrices[:,j]
        step=Rotation.from_matrix((matrices[:-1].swapaxes(-1,-2)@matrices[1:]).reshape(-1,3,3)).magnitude().reshape(len(out)-1,-1)
        bad=np.flatnonzero(np.rad2deg(np.maximum(step,local_step)).max(axis=1)>limit_degrees)
        if not len(bad):break
        discarded.update(int(f) for i in bad for f in range(max(1,i-1),min(len(out)-1,i+3)))
        valid=np.array([f for f in range(len(out)) if f not in discarded])
        if len(valid)<2:raise ValueError('Reference contains too many rotational tracking failures')
        for f in sorted(discarded):
            k=np.searchsorted(valid,f);lo,hi=valid[k-1],valid[k];t=(f-lo)/(hi-lo)
            a,b=out[lo],out[hi];qa=a[:,3:];qb=b[:,3:].copy();dot=np.sum(qa*qb,axis=-1)
            qb[dot<0]*=-1;dot=np.clip(np.abs(dot),0,1);theta=np.arccos(dot);sine=np.sin(theta)
            alpha=np.full(len(qa),1-t);beta=np.full(len(qa),t);mask=sine>1e-6
            alpha[mask]=np.sin((1-t)*theta[mask])/sine[mask];beta[mask]=np.sin(t*theta[mask])/sine[mask]
            out[f]=a*(1-t)+b*t;q=qa*alpha[:,None]+qb*beta[:,None];out[f,:,3:]=q/np.linalg.norm(q,axis=-1,keepdims=True)
    return out,sorted(discarded)


class VideoSequenceFitter:
    def __init__(self,assets,poses,landmarks,face=None):
        self.names=list(assets['joint_names']);self.index={n:i for i,n in enumerate(self.names)}
        self.parents=assets['parents'];self.reference=assets['reference'];self.base=np.asarray(poses,dtype=float)
        self.frames=len(poses);self.head_face=face
        selected=['Hips','Spine1','Spine2','Chest','Neck1','Neck2','Head']
        selected += [s+j for s in ('Left','Right') for j in ('Shoulder','Arm','ForeArm','Hand','Leg','Shin','Foot','ToeBase')]
        self.selected=np.array([self.index[n] for n in selected]);self.dim=3+len(self.selected)*3
        needed=set(self.selected.tolist())
        for side in ('Left','Right'):
            needed.update(self.index[side+'HandMiddle'+n] for n in ('1','2','3','4','End'))
            needed.add(self.index[side+'ToeEnd'])
        for j in list(needed):
            while self.parents[j]>=0:j=int(self.parents[j]);needed.add(j)
        self.active=sorted(needed)
        self.base_rotation=Rotation.from_quat(self.base[:,:,3:].reshape(-1,4)).as_matrix().reshape(self.frames,-1,3,3)
        self.local_position=self.base[:,:,:3].copy()
        self.rest_position,self.rest_rotation=self.forward(self.reference[None,:,:3],Rotation.from_quat(self.reference[:,3:]).as_matrix()[None])
        p,r=self.forward(self.base[:,:,:3],self.base_rotation);self.initial_position=p
        self.image_joints=[];self.image_targets=[];self.image_weight=[]
        n=landmarks['normalized'];aspect=float(landmarks['aspect']) if 'aspect' in landmarks else 9/16
        floor=np.percentile(n[:,[29,30,31,32],1],97)
        body=np.percentile(np.max(n[:,[27,28],1],axis=1)-n[:,0,1],85)+.10;meters=1.77/body
        origin=np.mean(n[0,[23,24],0]);self.source_scale=meters
        visibility=landmarks['visibility'] if 'visibility' in landmarks else np.ones(n.shape[:2])
        mapping=[('LeftLeg',23,.8),('RightLeg',24,.8),('LeftShin',25,1.),('RightShin',26,1.),('LeftFoot',27,1.5),('RightFoot',28,1.5),('LeftToeEnd',31,.65),('RightToeEnd',32,.65),('LeftArm',11,1.),('RightArm',12,1.),('LeftForeArm',13,1.2),('RightForeArm',14,1.2),('LeftHand',15,1.5),('RightHand',16,1.5),('LeftHandMiddleEnd',(17,19),.35),('RightHandMiddleEnd',(18,20),.35),('Head',(7,8),.7)]
        for name,source,weight in mapping:
            self.image_joints.append(self.index[name])
            observed=np.mean(n[:,source],axis=1) if isinstance(source,tuple) else n[:,source]
            confidence=np.mean(visibility[:,source],axis=1) if isinstance(source,tuple) else visibility[:,source]
            target=np.column_stack(((observed[:,0]-origin)*meters*aspect,(floor-observed[:,1])*meters))
            if name=='Head':target[:,1]-=.035
            self.image_targets.append(target)
            self.image_weight.append(weight*np.clip(confidence,.15,1.))
        self.image_joints=np.array(self.image_joints);self.image_targets=np.stack(self.image_targets,axis=1);self.image_weight=np.stack(self.image_weight,axis=1)
        self.foot_indices=[self.index[s+'Foot'] for s in ('Left','Right')]
        self.support=np.stack([np.exp(-np.maximum(0.,(floor-n[:,j,1])*meters-.02)/.045) for j in (31,32)],axis=1)
        self.contact_velocity=np.minimum(self.support[:-1],self.support[1:])
        self.front_masks=[]
        for elbow,wrist in ((13,15),(14,16)):
            sample=np.linspace(.25,1.,4)
            q=n[:,elbow,None,:2]+(n[:,wrist,None,:2]-n[:,elbow,None,:2])*sample[None,:,None]
            top=np.mean(n[:,[11,12],1],axis=1);bottom=np.mean(n[:,[23,24],1],axis=1)
            t=np.clip((q[:,:,1]-top[:,None])/np.maximum((bottom-top)[:,None],.01),0,1)
            left=n[:,11,0,None]*(1-t)+n[:,23,0,None]*t
            right=n[:,12,0,None]*(1-t)+n[:,24,0,None]*t
            inside=(q[:,:,1]>top[:,None])&(q[:,:,1]<bottom[:,None])&(q[:,:,0]>np.minimum(left,right))&(q[:,:,0]<np.maximum(left,right))
            confidence=np.minimum(visibility[:,elbow],visibility[:,wrist])[:,None]
            self.front_masks.append(gaussian_filter1d(inside.astype(float)*np.clip((confidence-.35)/.35,0,1),.8,axis=0))
        head=self.index['Head'];self.head_rest=self.rest_rotation[0,head]
        self.collision_names=[s+j for s in ('Left','Right') for j in ('Arm','ForeArm','Hand')]
        self.sole_samples=[]
        bind=np.asarray(assets['bind_world']);inverse=Rotation.from_quat(bind[:,3:]).as_matrix().swapaxes(-1,-2)
        for side in ('Left','Right'):
            foot=[self.index[side+n] for n in ('Foot','ToeBase','ToeEnd')];samples=[]
            for mesh in range(int(assets['mesh_count'])):
                prefix=f'mesh_{mesh}_';joints=assets[prefix+'joints'];weights=assets[prefix+'weights']
                mask=np.isin(joints[np.arange(len(joints)),weights.argmax(axis=1)],foot)
                points=assets[prefix+'points'][mask];ids=joints[mask];w=weights[mask]
                # Full foot-dominant skin vertices, not just a bone-height proxy.
                local=np.einsum('vkij,vkj->vki',inverse[ids],points[:,None]-bind[ids,:3])
                samples.append((ids,w,local))
                needed.update(ids[w>1e-5].tolist())
            self.sole_samples.append(samples)
        for j in list(needed):
            while self.parents[j]>=0:j=int(self.parents[j]);needed.add(j)
        self.active=sorted(needed)
        # Skin z is linear in each influencing bone's world z row/translation.
        # Collapse influences to keep the full-mesh floor test inexpensive.
        self.sole_linear=[]
        for samples in self.sole_samples:
            ids=np.concatenate([s[0] for s in samples]);weights=np.concatenate([s[1] for s in samples]);local=np.concatenate([s[2] for s in samples])
            bones=np.unique(ids[weights>1e-8]);coefficients=np.zeros((len(ids),len(bones),4))
            for b,joint in enumerate(bones):
                w=weights*(ids==joint)
                coefficients[:,b,:3]=np.sum(local*w[:,:,None],axis=1)
                coefficients[:,b,3]=np.sum(w,axis=1)
            self.sole_linear.append((bones,coefficients.reshape(len(ids),-1).T.copy()))

    def forward(self,position,rotation):
        p=position.copy();r=rotation.copy()
        for i in self.active:
            parent=self.parents[i]
            if parent>=0:
                p[:,i]=np.einsum('fij,fj->fi',r[:,parent],p[:,i])+p[:,parent]
                r[:,i]=r[:,parent]@r[:,i]
        return p,r

    def sole_height(self,p,r):
        floors=[]
        for bones,coefficients in self.sole_linear:
            feature=np.concatenate((r[:,bones,2,:],p[:,bones,2,None]),axis=-1).reshape(len(p),-1)
            floors.append(np.min(feature@coefficients,axis=1))
        return np.stack(floors,axis=1)

    def decode(self,parameters):
        x=parameters.reshape(self.frames,self.dim);p=self.local_position.copy();p[:,0]+=x[:,:3]
        r=self.base_rotation.copy();delta=Rotation.from_rotvec(x[:,3:].reshape(-1,3)).as_matrix().reshape(self.frames,-1,3,3)
        r[:,self.selected]=r[:,self.selected]@delta
        return p,r

    def collisions(self,p,r):
        values=[]
        # Inflated ellipsoids approximate torso surface plus arm/palm radius.
        # These are explicit geometric proxies, not a triangle intersection test.
        for side in ('Left','Right'):
            for segment in (('Arm','ForeArm',.45),('ForeArm','Hand',0.),('Hand','HandMiddleEnd',0.)):
                a=p[:,self.index[side+segment[0]]];b=p[:,self.index[side+segment[1]]]
                samples=np.linspace(segment[2],1.,7)
                q=a[:,None]+(b-a)[:,None]*samples[None,:,None]
                for bone,offset,radii in [('Hips',[0,0,-.015],[.19,.15,.18]),('Chest',[0,-.005,.075],[.205,.16,.205]),('Spine2',[0,0,.035],[.175,.15,.18]),('Head',[0,-.005,.055],[.125,.14,.155])]:
                    j=self.index[bone];rot=r[:,j]@self.rest_rotation[0,j].T
                    center=p[:,j]+np.einsum('fij,j->fi',rot,np.array(offset))
                    local=np.einsum('fji,fsj->fsi',rot,q-center[:,None])
                    distance=np.sqrt(np.sum((local/np.array(radii))**2,axis=-1)+1e-12)
                    values.append(np.maximum(0.,1-distance)*.15)
        for a,b,clearance in [('ForeArm','Hand',.075),('Leg','Shin',.105),('Shin','Foot',.075)]:
            d=segment_distance(p[:,self.index['Left'+a]],p[:,self.index['Left'+b]],p[:,self.index['Right'+a]],p[:,self.index['Right'+b]])
            values.append(np.maximum(0.,clearance-d)[:,None])
        return np.concatenate(values,axis=1)

    def balance(self,p):
        # Segment masses are approximate. Use a permissive support envelope;
        # this is a balance regularizer, not a dynamics/stability certificate.
        com=.142*p[:,self.index['Hips']]+.43*(p[:,self.index['Hips']]+p[:,self.index['Neck1']])/2+.081*p[:,self.index['Head']];mass=.653
        for side in ('Left','Right'):
            for a,b,w in [('Arm','ForeArm',.028),('ForeArm','Hand',.016),('Leg','Shin',.10),('Shin','Foot',.0465)]:
                com+=w*(p[:,self.index[side+a]]+p[:,self.index[side+b]])/2;mass+=w
        com=com[:,:2]/mass;feet=p[:,self.foot_indices,:2];a=feet[:,0];b=feet[:,1]
        # When one foot is visibly lifted, collapse toward the supporting foot.
        weights=self.support/np.maximum(self.support.sum(axis=1,keepdims=True),1e-8)
        single=np.abs(weights[:,0]-.5)>.35
        center=np.sum(feet*weights[:,:,None],axis=1)
        a=np.where(single[:,None],center,a);b=np.where(single[:,None],center,b)
        delta=b-a;t=np.clip(np.sum((com-a)*delta,axis=-1)/np.maximum(np.sum(delta*delta,axis=-1),1e-8),0,1)
        error=com-(a+t[:,None]*delta)
        return np.sign(error)*np.maximum(0.,np.abs(error)-np.array([.085,.14]))

    def front_order(self,p,r):
        # A visible limb crossing the image of the torso belongs in front of
        # its surface. An intersection penalty alone also permits the wrong
        # solution behind the back, despite an excellent 2D fit.
        values=[];sample=np.linspace(.25,1.,4)
        for k,side in enumerate(('Left','Right')):
            elbow=p[:,self.index[side+'ForeArm']];wrist=p[:,self.index[side+'Hand']]
            q=elbow[:,None]+(wrist-elbow)[:,None]*sample[None,:,None]
            violation=np.zeros(q.shape[:2])
            for bone,offset,radii in [('Hips',[0,0,-.015],[.19,.15,.18]),('Chest',[0,-.005,.075],[.205,.16,.205]),('Spine2',[0,0,.035],[.175,.15,.18])]:
                j=self.index[bone];rot=r[:,j]@self.rest_rotation[0,j].T
                center=p[:,j]+np.einsum('fij,j->fi',rot,np.asarray(offset))
                front,valid=ellipsoid_front_y(q,center,rot,radii)
                violation=np.maximum(violation,np.where(valid,np.maximum(0.,q[:,:,1]-front),0.))
            values.append(violation*self.front_masks[k])
        return np.concatenate(values,axis=1)

    def residual(self,parameters,details=False):
        local,rot=self.decode(parameters);p,r=self.forward(local,rot);x=parameters.reshape(self.frames,self.dim)
        image=(p[:,self.image_joints][:,:,[0,2]]-self.image_targets)
        values=[(image*self.image_weight[:,:,None]).reshape(self.frames,-1)]
        # Depth prior is deliberately weak; image geometry/contact wins over a
        # monocular network's uncertain depth ordering.
        values.append((p[:,self.image_joints,1]-p[:,0,None,1]-(self.initial_position[:,self.image_joints,1]-self.initial_position[:,0,None,1]))*.10)
        values.append(x*.008)
        selected=rot[:,self.selected];rel=np.swapaxes(selected[:-1],-1,-2)@selected[1:]
        velocity=Rotation.from_matrix(rel.reshape(-1,3,3)).as_rotvec().reshape(self.frames-1,-1)
        values.append(np.pad(velocity,((1,0),(0,0)))*.018)
        values.append(np.pad(np.diff(velocity,axis=0),((1,1),(0,0)))*.35)
        speed=velocity.reshape(self.frames-1,-1,3)
        speed_norm=np.linalg.norm(speed,axis=-1,keepdims=True)
        speed_limit=speed*np.maximum(0.,1-.25/np.maximum(speed_norm,1e-9))
        values.append(np.pad(speed_limit.reshape(self.frames-1,-1),((1,0),(0,0)))*1.2)
        # Local limits alone allow the root and several spine joints to rotate
        # together into a large world-space twitch while individually passing.
        # Regularize the composed rotations as well as the local joints.
        world_rotation=r[:,self.selected]
        world_relative=world_rotation[:-1].swapaxes(-1,-2)@world_rotation[1:]
        world_velocity=Rotation.from_matrix(world_relative.reshape(-1,3,3)).as_rotvec().reshape(self.frames-1,-1,3)
        world_speed=np.linalg.norm(world_velocity,axis=-1,keepdims=True)
        world_limit=world_velocity*np.maximum(0.,1-.25/np.maximum(world_speed,1e-9))
        values.append(np.pad(world_velocity.reshape(self.frames-1,-1),((1,0),(0,0)))*.015)
        values.append(np.pad(np.diff(world_velocity,axis=0).reshape(self.frames-2,-1),((1,1),(0,0)))*.25)
        values.append(np.pad(world_limit.reshape(self.frames-1,-1),((1,0),(0,0)))*1.2)
        values.append(np.pad(np.diff(local[:,0],n=2,axis=0),((1,1),(0,0)))*2.)
        foot_velocity=np.diff(p[:,self.foot_indices],axis=0)*self.contact_velocity[:,:,None]
        values.append(np.pad(foot_velocity.reshape(self.frames-1,-1),((1,0),(0,0)))*.6)
        collision=self.collisions(p,r);balance=self.balance(p)
        values.append(collision*12.);values.append(balance*np.array([1.5,4.]))
        front=self.front_order(p,r);values.append(front*6.)
        # Sole proxy: ankle and toe heights cannot pass below a floor; exact
        # skin-aware contact is checked separately before packaging.
        sole=self.sole_height(p,r)
        values.append(np.maximum(0.,.001-sole)*12.)
        values.append((sole-.001)*self.support*1.0)
        if self.head_face is not None:
            actual=r[:,self.index['Head']]@self.head_rest.T
            head_error=Rotation.from_matrix(np.swapaxes(self.head_face,-1,-2)@actual).as_rotvec()
            values.append(head_error*.2)
        result=np.concatenate(values,axis=1)
        if details:return dict(image_rmse_m=float(np.sqrt(np.mean(image**2))),image_p95_m=float(np.percentile(np.linalg.norm(image,axis=-1),95)),collision_proxy_max_m=float(collision.max()),front_order_violation_max_m=float(front.max()),balance_envelope_max_m=float(np.linalg.norm(balance,axis=-1).max()),angular_acceleration_p95=float(np.percentile(np.linalg.norm(np.diff(velocity,axis=0).reshape(-1,3),axis=-1),95)),cost=float(np.sum(result**2)))
        return result.ravel()

    def fit(self,max_iterations=35):
        initial=np.zeros(self.frames*self.dim);rows=len(self.residual(initial))//self.frames
        sparsity=lil_matrix((self.frames*rows,self.frames*self.dim),dtype=np.int8)
        for i in range(self.frames):sparsity[i*rows:(i+1)*rows,max(0,i-1)*self.dim:min(self.frames,i+2)*self.dim]=1
        before=self.residual(initial,details=True)
        print('Initial fit:',before,flush=True)
        solution=least_squares(self.residual,initial,jac_sparsity=sparsity.tocsr(),max_nfev=max_iterations,ftol=2e-4,xtol=2e-4,gtol=2e-4,verbose=2,tr_options=dict(atol=1e-3,btol=1e-3))
        p,r=self.decode(solution.x);poses=self.base.copy();poses[:,:,:3]=p;poses[:,:,3:]=Rotation.from_matrix(r.reshape(-1,3,3)).as_quat().reshape(self.frames,-1,4)
        for i in range(1,len(poses)):
            neg=np.sum(poses[i-1,:,3:]*poses[i,:,3:],axis=-1)<0;poses[i,neg,3:]*=-1
        return poses.astype(np.float32),dict(before=before,after=self.residual(solution.x,details=True),iterations=solution.nfev,converged=bool(solution.success),message=solution.message)

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
