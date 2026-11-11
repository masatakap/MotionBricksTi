"""Original analytical walk, authored from reference geometry, never from motion clips.

This is an artist-designed adult walk, not a recording or a biomechanical simulation.
The generator deliberately accepts only static skeleton/skin data. No model inference
or example animation is used to construct the authored joint trajectories.
"""
import numpy as np
from scipy.spatial.transform import Rotation
from .studio_export import transforms


def smooth(t):
    t=float(np.clip(t,0,1))
    return t*t*t*(10+t*(-15+6*t))


def axis(axis,angle):
    return Rotation.from_rotvec(np.asarray(axis)*angle).as_matrix()


def curve(t,knots):
    for (a,x),(b,y) in zip(knots,knots[1:]):
        if t<=b:return x+(y-x)*smooth((t-a)/(b-a))
    return knots[-1][1]


def align(a,b):
    a=a/np.linalg.norm(a);b=b/np.linalg.norm(b)
    cross=np.cross(a,b);length=np.linalg.norm(cross);dot=np.clip(a@b,-1,1)
    if length<1e-9:
        if dot>0:return np.eye(3)
        perpendicular=np.cross(a,[0,1,0])
        if np.linalg.norm(perpendicular)<1e-6:perpendicular=np.cross(a,[1,0,0])
        return axis(perpendicular/np.linalg.norm(perpendicular),np.pi)
    return axis(cross/length,np.arctan2(length,dot))


class OriginalAdultWalk:
    def __init__(self,assets):
        self.names=list(assets['joint_names']);self.parents=np.asarray(assets['parents'])
        self.ref=np.asarray(assets['reference'],dtype=np.float64).copy()
        self.rest=self.world(self.ref)
        self.index={n:i for i,n in enumerate(self.names)}
        self.inverse_bind=np.linalg.inv(transforms(assets['bind_world']))
        self.feet={}
        # Only foot-dominant vertices are needed for support-height calibration.
        for side in ('Left','Right'):
            selected=[]
            foot_ids=[self.index[side+n] for n in ('Foot','ToeBase','ToeEnd')]
            for k in range(int(assets['mesh_count'])):
                prefix=f'mesh_{k}_';indices=assets[prefix+'joints'];weights=assets[prefix+'weights']
                dominant=indices[np.arange(len(indices)),weights.argmax(axis=1)]
                mask=np.isin(dominant,foot_ids)
                selected.append((assets[prefix+'points'][mask],indices[mask],weights[mask]))
            self.feet[side]=selected
        self.period_frames=32;self.speed=1.2;self.stride=self.speed*self.period_frames/30
        self.stance=.60

    def world(self,pose):
        result=transforms(pose)
        for i,parent in enumerate(self.parents):
            if parent>=0:result[i]=result[parent]@result[i]
        return result

    def set_world_rotation(self,pose,name,rotation):
        i=self.index[name];parent=self.parents[i]
        parent_rotation=np.eye(3) if parent<0 else self.world(pose)[parent,:3,:3]
        pose[i,3:]=Rotation.from_matrix(parent_rotation.T@rotation).as_quat()

    def foot_state(self,side,cycle):
        phase_offset=0 if side=='Left' else .5
        n=np.floor(cycle+phase_offset);phase=(cycle+phase_offset)-n
        touchdown=(n-phase_offset)*self.stride
        sign=1 if side=='Left' else -1
        yaw=axis([0,0,1],np.deg2rad(sign*6))
        foot=self.rest[self.index[side+'Foot'],:3,3]
        # Sole pivots are design geometry, expressed relative to the ankle in meters.
        heel=np.array([0,.054,-foot[2]])
        ball=np.array([0,-.132,-foot[2]])
        base=np.array([sign*.065,-(touchdown+.26)-.0224,0.])
        heel_pivot=base+yaw@heel;heel_pivot[2]=.001
        ball_pivot=base+yaw@ball;ball_pivot[2]=.001
        heel_angle=np.deg2rad(-10);toe_angle=np.deg2rad(55)
        if phase<.12:
            pitch=heel_angle*(1-smooth(phase/.12))
            ankle=heel_pivot-yaw@axis([1,0,0],pitch)@heel
            compensate=0.
        elif phase<.35:
            pitch=0.;ankle=base.copy();ankle[2]=foot[2]+.001;compensate=0.
        elif phase<=self.stance:
            pitch=toe_angle*smooth((phase-.35)/(self.stance-.35))
            ankle=ball_pivot-yaw@axis([1,0,0],pitch)@ball
            compensate=1.
        else:
            s=(phase-self.stance)/(1-self.stance)
            start=ball_pivot-yaw@axis([1,0,0],toe_angle)@ball
            next_base=base+np.array([0,-self.stride,0])
            next_heel=next_base+yaw@heel;next_heel[2]=.001
            end=next_heel-yaw@axis([1,0,0],heel_angle)@heel
            progress=(-2*s**3+3*s*s)+.7*(s**3-2*s*s+s)
            ankle=start+(end-start)*progress
            ankle[2]+=.070*np.sin(np.pi*s)**1.1
            pitch=np.deg2rad(curve(s,[(0,55),(.25,20),(.55,0),(1,-10)]))
            compensate=1-smooth(s/.2)
        foot_rotation=yaw@axis([1,0,0],pitch)@self.rest[self.index[side+'Foot'],:3,:3]
        toe_rotation=yaw@axis([1,0,0],pitch*(1-compensate))@self.rest[self.index[side+'ToeBase'],:3,:3]
        state=dict(phase=phase,ankle=ankle,foot_rotation=foot_rotation,toe_rotation=toe_rotation,clearance_correction=0.)
        if phase>self.stance:state.update(swing=s,start_height=start[2],end_height=end[2])
        return state

    def solve_leg(self,pose,side,target):
        hip,knee,ankle=[self.index[side+n] for n in ('Leg','Shin','Foot')]
        world=self.world(pose);h=world[hip,:3,3];a=target['ankle']
        upper=np.linalg.norm(self.ref[knee,:3]);lower=np.linalg.norm(self.ref[ankle,:3])
        delta=a-h;distance=np.linalg.norm(delta);direction=delta/distance
        d=np.clip(distance,abs(upper-lower)+1e-6,upper+lower-1e-6)
        along=(upper*upper-lower*lower+d*d)/(2*d)
        height=np.sqrt(max(0,upper*upper-along*along))
        pole=np.array([.06 if side=='Left' else -.06,-1,0.])
        pole-=direction*(pole@direction);pole/=np.linalg.norm(pole)
        k=h+direction*along+pole*height
        r=align(self.rest[knee,:3,3]-self.rest[hip,:3,3],k-h)@self.rest[hip,:3,:3]
        self.set_world_rotation(pose,side+'Leg',r)
        r=align(self.rest[ankle,:3,3]-self.rest[knee,:3,3],a-k)@self.rest[knee,:3,:3]
        self.set_world_rotation(pose,side+'Shin',r)
        self.set_world_rotation(pose,side+'Foot',target['foot_rotation'])
        self.set_world_rotation(pose,side+'ToeBase',target['toe_rotation'])

    def floor_height(self,pose,side):
        skin=self.world(pose)@self.inverse_bind
        heights=[]
        for points,indices,weights in self.feet[side]:
            positions=np.zeros_like(points,dtype=np.float64)
            for influence in range(indices.shape[1]):
                matrix=skin[indices[:,influence]]
                positions+=(np.einsum('nij,nj->ni',matrix[:,:3,:3],points)+matrix[:,:3,3])*weights[:,influence,None]
            heights.append(positions[:,2].min())
        return min(heights)

    def limit_pelvis_height(self,pose,targets):
        world=self.world(pose)
        root_z=pose[0,2]
        for side,target in targets.items():
            h=self.index[side+'Leg'];k=self.index[side+'Shin'];a=self.index[side+'Foot']
            hip=world[h,:3,3];ankle=target['ankle']
            reach=np.linalg.norm(self.ref[k,:3])+np.linalg.norm(self.ref[a,:3])-.001
            horizontal=np.linalg.norm((ankle-hip)[:2])
            max_hip_z=ankle[2]+np.sqrt(max(.001,reach*reach-horizontal*horizontal))
            pose[0,2]=min(pose[0,2],max_hip_z-(hip[2]-root_z))

    def shape_support_and_swing(self,pose,targets):
        # Match the support knee's designed loading/extension curve instead of
        # imposing an unrelated sine-wave pelvis height on the fixed foot.
        primary=min(targets,key=lambda side:targets[side]['phase'])
        world=self.world(pose);target=targets[primary]
        h,k,a=[self.index[primary+n] for n in ('Leg','Shin','Foot')]
        hip=world[h,:3,3];ankle=target['ankle'];u=np.linalg.norm(self.ref[k,:3]);v=np.linalg.norm(self.ref[a,:3])
        flex=np.deg2rad(curve(target['phase'],[(0,6),(.12,18),(.30,6),(.40,10),(.50,30)]))
        distance2=u*u+v*v+2*u*v*np.cos(flex)
        horizontal2=np.sum((ankle[:2]-hip[:2])**2)
        pose[0,2]=ankle[2]+np.sqrt(max(.001,distance2-horizontal2))-(hip[2]-pose[0,2])
        world=self.world(pose)
        for side,target in targets.items():
            if 'swing' not in target:continue
            s=target['swing'];h,k,a=[self.index[side+n] for n in ('Leg','Shin','Foot')]
            hip=world[h,:3,3];u=np.linalg.norm(self.ref[k,:3]);v=np.linalg.norm(self.ref[a,:3])
            flex=np.deg2rad(curve(s,[(0,35),(.25,60),(.55,25),(1,6)]))
            distance2=u*u+v*v+2*u*v*np.cos(flex)
            horizontal2=np.sum((target['ankle'][:2]-hip[:2])**2)
            desired=hip[2]-np.sqrt(max(.001,distance2-horizontal2))
            # Join the geometric toe-off and heel-strike heights continuously.
            desired=target['start_height']+(desired-target['start_height'])*smooth(s/.12)
            blend=smooth((s-.86)/.14)
            target['ankle'][2]=desired*(1-blend)+target['end_height']*blend+target['clearance_correction']

    def frame(self,frame):
        cycle=frame/self.period_frames;p=cycle%1.;angle=2*np.pi*p
        pose=self.ref.copy()
        pose[0,0]=.017*np.sin(angle);pose[0,1]=-cycle*self.stride
        response=np.exp(-(((p%.5)-.10)/.055)**2)
        pose[0,2]=.950+.057*np.sin(angle)**2-.008*response
        pelvis_yaw=np.deg2rad(-3)*np.cos(angle)
        pelvis=axis([0,0,1],pelvis_yaw)@axis([0,-1,0],np.deg2rad(2)*np.sin(angle))@axis([1,0,0],np.deg2rad(1.2))
        pose[0,3:]=Rotation.from_matrix(pelvis@self.rest[0,:3,:3]).as_quat()
        # Counter-rotation increases toward the chest, keeping the head steady.
        for name,factor in [('Spine1',.6),('Spine2',.2),('Chest',-.7),('Neck1',-.35),('Neck2',-.12),('Head',0)]:
            yaw=axis([0,0,1],pelvis_yaw*factor)
            lean=axis([1,0,0],np.deg2rad(.35 if name=='Head' else 1.7)+np.deg2rad(.25)*np.sin(2*angle))
            self.set_world_rotation(pose,name,yaw@lean@self.rest[self.index[name],:3,:3])
        for side,sign,offset in [('Left',1,0),('Right',-1,np.pi)]:
            swing=-np.deg2rad(16)*np.cos(angle+offset-.10)
            elbow=np.deg2rad(15+4*np.cos(angle+offset-.2))
            for joint,child,theta in [('Arm','ForeArm',swing),('ForeArm','Hand',swing+elbow)]:
                direction=np.array([sign*.085,-np.sin(theta),-np.cos(theta)])
                a,b=self.index[side+joint],self.index[side+child]
                rotation=align(self.rest[b,:3,3]-self.rest[a,:3,3],direction)@self.rest[a,:3,:3]
                self.set_world_rotation(pose,side+joint,rotation)
            for finger,angles in [('Index',(12,18,10)),('Middle',(14,20,12)),('Ring',(16,25,15)),('Pinky',(18,28,18))]:
                for segment,bend in zip((2,3,4),angles):
                    name=f'{side}Hand{finger}{segment}'
                    if name in self.index:
                        i=self.index[name]
                        pose[i,3:]=(Rotation.from_quat(self.ref[i,3:])*Rotation.from_rotvec([0,-np.deg2rad(bend),0])).as_quat()
        targets={side:self.foot_state(side,cycle) for side in ('Left','Right')}
        for iteration in range(3):
            self.shape_support_and_swing(pose,targets)
            self.limit_pelvis_height(pose,targets)
            for side,target in targets.items():self.solve_leg(pose,side,target)
            if iteration<2:
                for side,target in targets.items():
                    height=self.floor_height(pose,side)
                    if target['phase']<=self.stance:target['ankle'][2]+=.001-height
                    elif height<.006:target['clearance_correction']+=.006-height
        return pose.astype(np.float32),targets

    def build(self,cycles=4):
        poses=[];targets=[]
        for frame in range(cycles*self.period_frames+1):
            pose,target=self.frame(frame);poses.append(pose);targets.append(target)
        poses=np.stack(poses)
        # Smooth small support-height transitions periodically, then solve the
        # legs again against the original planted feet. Never smooth foot tracks.
        height=poses[:-1,0,2].astype(np.float64)
        filtered=sum(weight*np.roll(height,offset) for offset,weight in [(-2,1),(-1,4),(0,6),(1,4),(2,1)])/16
        filtered=np.r_[filtered,filtered[0]]
        for f,pose in enumerate(poses):
            delta=filtered[f]-pose[0,2];pose[0,2]=filtered[f]
            for target in targets[f].values():
                if 'swing' in target:target['ankle'][2]+=delta
            for iteration in range(2):
                self.limit_pelvis_height(pose,targets[f])
                for side,target in targets[f].items():self.solve_leg(pose,side,target)
                if iteration==0:
                    for side,target in targets[f].items():
                        floor=self.floor_height(pose,side)
                        if target['phase']<=self.stance:target['ankle'][2]+=.001-floor
                        elif floor<.006:target['ankle'][2]+=.006-floor
        # Keep quaternion signs continuous as well as physical orientations.
        for f in range(1,len(poses)):
            negative=np.sum(poses[f-1,:,3:]*poses[f,:,3:],axis=-1)<0
            poses[f,negative,3:]*=-1
        return poses,targets

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
