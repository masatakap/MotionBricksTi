"""Independent adult performance authoring from static SOMA geometry only.

No BVH/CSV samples, sampled targets, trained generators or external animation
curves are inputs. Units: meters, Z up, facing -Y, quaternion XYZW, 30 Hz.
The result is artist-designed animation, not measured human motion or a
validated dynamics simulation. Stylized performances are labelled explicitly.
"""
from dataclasses import dataclass
import math
import numpy as np
from scipy.spatial.transform import Rotation
from .studio_walk_authoring import OriginalAdultWalk,align,axis,smooth

FPS=30

def aim_rotation(reference,direction,normal):
    """Aim with an explicit bend-plane normal, avoiding shortest-arc twist flips."""
    a=reference/np.linalg.norm(reference);b=direction/np.linalg.norm(direction)
    n=np.cross(a,[0.,-1.,0.]);n/=np.linalg.norm(n)
    m=normal-b*(normal@b);m/=max(np.linalg.norm(m),1e-9)
    return np.column_stack((b,m,np.cross(b,m)))@np.column_stack((a,n,np.cross(a,n))).T

@dataclass(frozen=True)
class Performance:
    id:str
    name:str
    kind:str
    seconds:float=4.8
    speed:float=0.
    period:int=32
    turn:float=0.
    direction:float=0.
    loop:bool=True

CATALOG=(
    Performance('walk','通常歩行','walk',128/30,1.2),
    Performance('jog','ジョギング','jog',4.,2.,24),
    Performance('run','走行','run',4.,2.5,24),
    Performance('jog_turn_left','ジョグ・左へ曲がる','jog',4.,1.8,24,90.,loop=False),
    Performance('jog_turn_right','ジョグ・右へ曲がる','jog',4.,1.8,24,-90.,loop=False),
    Performance('jog_circle','ジョグ・一周','jog',4.8,1.65,24,360.),
    Performance('crouch_walk','しゃがみ前進','crouch',4.8,.52,36),
    Performance('crouch_left','しゃがみ左移動','crouch',4.8,.40,36,direction=90.),
    Performance('crouch_right','しゃがみ右移動','crouch',4.8,.40,36,direction=-90.),
    Performance('crouch_turn','しゃがみ旋回・一周','crouch',4.8,.35,36,360.),
    Performance('duck_walk','歩きながらかがんで通過','duck',5.6,.85,32,loop=False),
    Performance('duck_jog','ジョグからかがんで通過','duck_jog',4.8,1.35,26,loop=False),
    Performance('vault_050','0.5m障害物を跳び越える','vault_low',3.6,loop=False),
    Performance('vault_075_hand','0.75m障害物を片手で乗り越える','vault_hand',3.8,loop=False),
    Performance('vault_075_free','0.75m障害物を手を使わず跳び越える','vault_high',3.8,loop=False),
    Performance('idle','自然な立ち待機','idle',6.4),
    Performance('crouch_idle','しゃがみ待機','crouch_idle',6.4),
    Performance('legs_relax','立ったまま脚をほぐす','legs_relax',6.4),
    Performance('look_around','周囲を見回す','look_around',6.4),
    Performance('neck_warmup','首をゆっくりほぐす','neck_warmup',8.),
    Performance('sit_down','椅子に座る','sit_down',4.,loop=False),
    Performance('seated_idle','椅子に座った待機','seated_idle',6.4),
    Performance('stand_up','椅子から立ち上がる','stand_up',4.,loop=False),
    Performance('combat_step','構えて前後にステップ','combat',4.8,.45,24),
    Performance('combat_left','強い構えで左にステップ','combat_left',4.8,.55,24,direction=90.),
    Performance('combat_right','強い構えで右にステップ','combat_right',4.8,.55,24,direction=-90.),
    Performance('combat_turn','構えたまま一周','combat_turn',4.8,.35,24,360.),
    Performance('armed_walk','両手で道具を構えて歩く','armed',4.8,.85,36),
    Performance('dance_vogue','ヴォーグ風のポージング','dance',8.),
    Performance('dance_protect_leg','左脚をかばう身振りダンス','dance_protect',8.),
    Performance('limp_left','左脚をかばって歩く','limp',5.6,.48,42),
    Performance('hold_torso','腹部を押さえて歩く','torso',4.8,.62,36),
    Performance('skip','スキップ','skip',4.8,1.25,36),
    Performance('zombie_walk','ゾンビ風の歩行演技','zombie',6.4,.42,48),
)


class AdultPerformance(OriginalAdultWalk):
    def __init__(self,assets):
        super().__init__(assets)
        self.floor_samples=[]
        self.support_z=.001

    def solve_leg(self,pose,side,target):
        # Keep the knee pole in the character's facing frame during turns.
        hip,knee,ankle=[self.index[side+n] for n in ('Leg','Shin','Foot')]
        world=self.world(pose);h=world[hip,:3,3];a=target['ankle']
        upper=np.linalg.norm(self.ref[knee,:3]);lower=np.linalg.norm(self.ref[ankle,:3])
        delta=a-h;distance=np.linalg.norm(delta);direction=delta/max(distance,1e-9)
        d=np.clip(distance,abs(upper-lower)+1e-6,upper+lower-1e-6)
        along=(upper*upper-lower*lower+d*d)/(2*d)
        rotation=world[0,:3,:3]@self.rest[0,:3,:3].T
        pole=rotation@np.array(target.get('knee_pole',[.06 if side=='Left' else -.06,-1.,0.]))
        pole-=direction*(pole@direction);pole/=max(np.linalg.norm(pole),1e-9)
        k=h+direction*along+pole*np.sqrt(max(0,upper*upper-along*along))
        normal=np.cross(direction,pole);normal/=np.linalg.norm(normal)
        self.set_world_rotation(pose,side+'Leg',aim_rotation(self.rest[knee,:3,3]-self.rest[hip,:3,3],k-h,normal)@self.rest[hip,:3,:3])
        self.set_world_rotation(pose,side+'Shin',aim_rotation(self.rest[ankle,:3,3]-self.rest[knee,:3,3],a-k,normal)@self.rest[knee,:3,:3])
        self.set_world_rotation(pose,side+'Foot',target['foot_rotation'])
        self.set_world_rotation(pose,side+'ToeBase',target['toe_rotation'])

    def body(self,root=(0,0,.99),yaw=0.,lean=2.,roll=0.,twist=0.):
        pose=self.ref.copy();pose[0,:3]=root
        yaw=math.radians(yaw);lean=math.radians(lean);roll=math.radians(roll)
        heading=axis([0,0,1],yaw)
        pose[0,3:]=Rotation.from_matrix(heading@axis([0,1,0],roll)@self.rest[0,:3,:3]).as_quat()
        for name,factor in [('Spine1',.35),('Spine2',.65),('Chest',1.),('Neck1',.75),('Neck2',.55),('Head',.30)]:
            rotation=heading@axis([0,0,1],math.radians(twist)*factor)@axis([1,0,0],lean*factor)@axis([0,1,0],roll*.35)
            self.set_world_rotation(pose,name,rotation@self.rest[self.index[name],:3,:3])
        for side in ('Left','Right'):self.arm(pose,side,yaw,0.,12.,8.)
        self.fingers(pose,.25)
        return pose

    def fingers(self,pose,grip):
        for side in ('Left','Right'):
            for finger,gain in [('Index',.8),('Middle',.95),('Ring',1.05),('Pinky',1.12)]:
                for segment,maximum in [(2,65),(3,80),(4,55)]:
                    name=f'{side}Hand{finger}{segment}'
                    if name in self.index:
                        i=self.index[name]
                        pose[i,3:]=(Rotation.from_quat(self.ref[i,3:])*Rotation.from_rotvec([0,-math.radians(maximum)*grip*gain,0])).as_quat()

    def arm(self,pose,side,yaw,flex,elbow,spread=8.):
        sign=1 if side=='Left' else -1
        heading=axis([0,0,1],yaw)
        for joint,child,angle in [('Arm','ForeArm',flex),('ForeArm','Hand',flex+elbow)]:
            angle=math.radians(angle);abduct=math.radians(spread)
            direction=heading@np.array([sign*math.sin(abduct),-math.sin(angle)*math.cos(abduct),-math.cos(angle)*math.cos(abduct)])
            a,b=self.index[side+joint],self.index[side+child]
            self.set_world_rotation(pose,side+joint,aim_rotation(self.rest[b,:3,3]-self.rest[a,:3,3],direction,heading@np.array([-1.,0.,0.]))@self.rest[a,:3,:3])

    def hand(self,pose,side,target,pole=None):
        a,b,c=[self.index[side+n] for n in ('Arm','ForeArm','Hand')]
        world=self.world(pose);origin=world[a,:3,3];target=np.asarray(target,dtype=float)
        u=np.linalg.norm(self.ref[b,:3]);v=np.linalg.norm(self.ref[c,:3]);delta=target-origin
        distance=np.linalg.norm(delta);d=np.clip(distance,abs(u-v)+1e-5,u+v-.020);direction=delta/max(distance,1e-8)
        pole=np.array(pole if pole is not None else ([.7,-.4,-.2] if side=='Left' else [-.7,-.4,-.2]),dtype=float)
        pole-=direction*(pole@direction);pole/=max(np.linalg.norm(pole),1e-8)
        along=(u*u-v*v+d*d)/(2*d);bend=origin+direction*along+pole*np.sqrt(max(0,u*u-along*along))
        normal=np.cross(direction,pole);normal/=max(np.linalg.norm(normal),1e-9)
        self.set_world_rotation(pose,side+'Arm',aim_rotation(self.rest[b,:3,3]-self.rest[a,:3,3],bend-origin,normal)@self.rest[a,:3,:3])
        self.set_world_rotation(pose,side+'ForeArm',aim_rotation(self.rest[c,:3,3]-self.rest[b,:3,3],target-bend,normal)@self.rest[b,:3,:3])
        return float(np.linalg.norm(self.world(pose)[c,:3,3]-target))

    def flat_foot(self,side,xy,yaw=0.,pitch=0.):
        heading=axis([0,0,1],yaw);rotation=heading@axis([1,0,0],pitch)
        return dict(ankle=np.r_[xy,self.rest[self.index[side+'Foot'],2,3]+self.support_z],
                    foot_rotation=rotation@self.rest[self.index[side+'Foot'],:3,:3],
                    toe_rotation=rotation@self.rest[self.index[side+'ToeBase'],:3,:3],phase=0.,support=True)

    def finish(self,pose,targets,*,limit=True):
        supports={s:t for s,t in targets.items() if t.get('support')}
        if limit and supports:self.limit_pelvis_height(pose,supports)
        if limit:self.limit_pelvis_height(pose,targets)
        for _ in range(4):
            for side,target in targets.items():self.solve_leg(pose,side,target)
            for side,target in targets.items():
                floor=self.floor_height(pose,side)
                if target.get('support'):target['ankle'][2]+=self.support_z-floor
                elif floor<.004:target['ankle'][2]+=.004-floor
        for side,target in targets.items():self.solve_leg(pose,side,target)
        return pose.astype(np.float32)

    def path(self,t,spec):
        omega=math.radians(spec.turn)/spec.seconds
        if spec.kind=='combat':return np.array([0.,-.18*math.sin(2*math.pi*t/2.4)]),0.
        if abs(omega)>1e-8:
            p=np.array([(1-math.cos(omega*t))*spec.speed/omega,-math.sin(omega*t)*spec.speed/omega]);yaw=omega*t
        else:
            a=math.radians(spec.direction);p=np.array([math.sin(a),-math.cos(a)])*spec.speed*t;yaw=0.
        return p,yaw

    def gait_frame(self,t,spec):
        period=spec.period/FPS;cycle=t/period
        if abs(cycle-round(cycle))<1e-9:cycle=float(round(cycle))
        phase=cycle%1;angle=2*math.pi*cycle
        center,yaw=self.path(t,spec)
        crouched=spec.kind=='crouch';running=spec.kind in ('jog','run','duck_jog','skip')
        duty=.40 if running else .62
        low=1. if crouched else 0.
        if spec.kind in ('duck','duck_jog'):
            q=t/spec.seconds;low=smooth((q-.10)/.20)*(1-smooth((q-.70)/.20))
        combat=spec.kind.startswith('combat')
        root_z=(.90 if spec.kind=='run' else .92 if running else .96)-.32*low-(.09 if combat else 0.)
        root_z+=(.030*math.cos(4*math.pi*(cycle-.44)) if running else -.012*math.cos(2*angle))
        if spec.kind=='skip':root_z+=.055*math.sin(2*angle)**2
        lean=3+18*low+(8 if running else 0)+(16 if spec.kind=='torso' else 0)
        if spec.kind=='zombie':lean+=12
        lateral=.014*math.sin(angle)-(.035 if spec.kind=='limp' else 0.)
        right=np.array([math.cos(yaw),math.sin(yaw)])
        root=np.r_[center+right*lateral,root_z]
        pose=self.body(root,math.degrees(yaw),lean,1.5*math.sin(angle),-3*math.cos(angle))
        for side,offset in [('Left',0.),('Right',math.pi)]:
            flex=-18*math.cos(angle+offset)
            elbow=15+4*math.cos(angle+offset)
            if running:flex=-32*math.cos(angle+offset);elbow=75+8*math.sin(angle+offset)
            if low:flex*=1-.6*low;elbow+=15*low
            if combat:flex=25+10*math.cos(angle+offset);elbow=75;self.fingers(pose,.8)
            if spec.kind=='zombie':flex=65+6*math.sin(angle+offset);elbow=18
            self.arm(pose,side,yaw,flex,elbow,10 if not combat else 15)
        targets={}
        for side,offset,sign in [('Left',0.,1),('Right',.5,-1)]:
            n=math.floor(cycle+offset);p=cycle+offset-n
            stance=duty
            if spec.kind=='limp':stance=.46 if side=='Left' else .73
            touchdown=(n-offset)*period
            placement_fraction=.50
            foot_center,foot_yaw=self.path(touchdown+stance*period*placement_fraction,spec)
            step_right=np.array([math.cos(foot_yaw),math.sin(foot_yaw)])
            base=foot_center+step_right*sign*(.105 if combat or crouched else .085)
            turn=axis([0,0,1],foot_yaw+sign*math.radians(4))
            ankle_z=self.rest[self.index[side+'Foot'],2,3]
            heel=np.array([0,.045,-ankle_z]);ball=np.array([0,-.13,-ankle_z])
            flat=np.r_[base,self.support_z+ankle_z]
            heel_pivot=flat+turn@heel;ball_pivot=flat+turn@ball
            toe_angle=math.radians(35 if running or crouched else 48)
            heel_angle=math.radians(-4 if running or crouched else -9)
            if p<=stance:
                u=p/stance
                pitch=heel_angle*(1-smooth(u/.20)) if u<.2 else toe_angle*smooth((u-.55)/.45)
                pivot=heel_pivot if u<.2 else ball_pivot
                local_pivot=heel if u<.2 else ball
                ankle=pivot-turn@axis([1,0,0],pitch)@local_pivot
                toe_pitch=pitch if u<.55 else 0.
            else:
                u=(p-stance)/(1-stance)
                start=ball_pivot-turn@axis([1,0,0],toe_angle)@ball
                next_center,next_yaw=self.path(touchdown+period+stance*period*placement_fraction,spec)
                next_right=np.array([math.cos(next_yaw),math.sin(next_yaw)])
                next_turn=axis([0,0,1],next_yaw+sign*math.radians(4))
                next_flat=np.r_[next_center+next_right*sign*(.105 if combat or crouched else .085),ankle_z+self.support_z]
                end=next_flat+next_turn@heel-next_turn@axis([1,0,0],heel_angle)@heel
                progress=3*u*u-2*u*u*u+.4*(u*u*u-2*u*u+u) if running else smooth(u)
                ankle=start+(end-start)*progress
                ankle[2]+=(.19 if spec.kind=='run' else .14 if running else .055)*math.sin(math.pi*u)**1.3
                pitch=toe_angle*(1-smooth(u/.55))+heel_angle*smooth((u-.65)/.35);toe_pitch=pitch*smooth(u/.55)
                turn=axis([0,0,1],foot_yaw+(next_yaw-foot_yaw)*smooth(u)+sign*math.radians(4))
            targets[side]=dict(ankle=ankle,foot_rotation=turn@axis([1,0,0],pitch)@self.rest[self.index[side+'Foot'],:3,:3],
                               toe_rotation=turn@axis([1,0,0],toe_pitch)@self.rest[self.index[side+'ToeBase'],:3,:3],phase=p,support=p<=stance)
            if spec.kind=='skip' and .10<p<.27:
                hop=math.sin(math.pi*(p-.10)/.17)**2
                targets[side]['ankle'][2]+=.10*hop
                targets[side]['support']=False
        pose=self.finish(pose,targets)
        if spec.kind in ('armed','torso','limp'):
            h=pose[0,:3];heading=axis([0,0,1],yaw)
            if spec.kind=='armed':
                self.hand(pose,'Right',h+heading@np.array([-.12,-.29,.22]))
                self.hand(pose,'Left',h+heading@np.array([.08,-.47,.23]));self.fingers(pose,.72)
            if spec.kind=='torso':self.hand(pose,'Left',h+heading@np.array([.015,-.16,.17]))
            if spec.kind=='limp':self.hand(pose,'Left',h+heading@np.array([.16,-.08,-.23]))
        return pose,targets,{}

    def sit_pose(self,q,breath=0.):
        s=smooth((q-.15)/.70);anticipation=math.sin(math.pi*s)
        pose=self.body([0,-.47*(1-s),.99-(.99-.585)*s],lean=3+28*anticipation+7*s)
        targets={side:self.flat_foot(side,[sign*.105,-.47]) for side,sign in [('Left',1),('Right',-1)]}
        pose=self.finish(pose,targets)
        for side,sign in [('Left',1),('Right',-1)]:
            self.arm(pose,side,0,25*anticipation,15+35*s,8)
            blend=smooth((s-.60)/.40)
            if blend>0:
                before=pose.copy();self.hand(pose,side,[sign*.16,-.25,.54])
                self.blend_rotations(pose,before,blend)
        if breath:
            i=self.index['Chest'];pose[i,3:]=(Rotation.from_quat(pose[i,3:])*Rotation.from_rotvec([breath,0,0])).as_quat()
        return pose,targets,{}

    @staticmethod
    def blend_rotations(pose,before,weight):
        a=before[:,3:];b=pose[:,3:];b=b*np.where(np.sum(a*b,axis=-1,keepdims=True)<0,-1,1)
        q=(1-weight)*a+weight*b;pose[:,3:]=q/np.linalg.norm(q,axis=-1,keepdims=True)

    def stationary_frame(self,t,spec):
        q=t/spec.seconds;angle=2*math.pi*q
        if spec.kind in ('sit_down','stand_up','seated_idle'):
            amount=q if spec.kind=='sit_down' else 1-q if spec.kind=='stand_up' else 1.
            return self.sit_pose(amount,.004*math.sin(2*angle) if spec.kind=='seated_idle' else 0.)
        crouch=spec.kind=='crouch_idle'
        pose=self.body([.012*math.sin(angle),0,.65 if crouch else .99],lean=17 if crouch else 2.,twist=1.5*math.sin(angle))
        targets={side:self.flat_foot(side,[sign*.105,0.]) for side,sign in [('Left',1),('Right',-1)]}
        if spec.kind=='legs_relax':
            left=q<.5;u=(q% .5)*2;side='Left' if left else 'Right';sign=1 if left else -1
            lift=math.sin(math.pi*u)**4;targets[side]['ankle']+=np.array([sign*.11*lift,-.03*lift,.055*lift]);targets[side]['support']=lift<.01
            pose[0,0]=-.055*sign*math.sin(math.pi*u)**2
        if spec.kind in ('look_around','neck_warmup'):
            if spec.kind=='look_around':yaw=38*math.sin(angle);pitch=3*math.sin(2*angle);roll=0.
            else:yaw=22*math.sin(angle);pitch=10*math.sin(2*angle);roll=9*math.sin(angle)
            for name,factor in [('Neck1',.35),('Neck2',.65),('Head',1.)]:
                r=Rotation.from_euler('zxy',[yaw*factor,pitch*factor,roll*factor],degrees=True).as_matrix()
                self.set_world_rotation(pose,name,r@self.rest[self.index[name],:3,:3])
        if spec.kind in ('idle','crouch_idle'):
            i=self.index['Chest'];pose[i,3:]=(Rotation.from_quat(pose[i,3:])*Rotation.from_rotvec([.005*math.sin(2*angle),0,0])).as_quat()
        if spec.kind in ('dance','dance_protect'):
            pose[0,0]+=.045*math.sin(4*angle);pose[0,2]-=.025*(1-math.cos(8*angle))
            pose[0,3:]=Rotation.from_matrix(axis([0,0,1],.12*math.sin(4*angle))@self.rest[0,:3,:3]).as_quat()
            for side,sign in [('Left',1),('Right',-1)]:
                beat=2*math.pi*t/2.+(0 if side=='Left' else math.pi/2)
                self.arm(pose,side,0,70+55*math.sin(beat),50+35*math.sin(beat+1),35+25*math.cos(beat))
                hand=self.index[side+'Hand'];pose[hand,3:]=(Rotation.from_quat(pose[hand,3:])*Rotation.from_rotvec([.35*math.sin(beat),.3*math.cos(beat),0])).as_quat()
            self.fingers(pose,.05)
            if spec.kind=='dance_protect':
                pose[0,0]=-.055;targets['Left']['ankle']+=np.array([.035,-.05,.035*math.sin(2*angle)**2]);targets['Left']['support']=False
        return self.finish(pose,targets),targets,{}

    def vault_frame(self,t,spec):
        hand=spec.kind=='vault_hand';high=spec.kind!='vault_low';height=.75 if high else .5
        takeoff=1.05;flight=.82 if hand else .76 if high else .72
        u=np.clip((t-takeoff)/flight,0,1);before=t<takeoff;after=t>takeoff+flight
        hand_errors={}
        if before:
            q=t/takeoff;anticipation=math.sin(math.pi*smooth(q))**2
            root=[0,.95,.99-.15*anticipation];lean=5+15*anticipation
        elif after:
            q=np.clip((t-takeoff-flight)/.75,0,1);loading=(1-smooth(q))*math.sin(math.pi*min(q*2,1))
            root=[0,-.95,.99-.14*loading];lean=5+13*loading
        else:
            root=[.08*math.sin(math.pi*u) if hand else 0.,.95-1.90*(smooth(u) if hand else u),
                  .99+.015*math.sin(math.pi*u) if hand else 1.0+.5*9.81*flight*flight*u*(1-u)]
            lean=5+77*smooth(u/.26)*(1-smooth((u-.48)/.52)) if hand else 5+17*math.sin(math.pi*u)
        pose=self.body(root,lean=lean,roll=8*math.sin(math.pi*u) if hand else 0.)
        targets={}
        for side,sign in [('Left',1),('Right',-1)]:
            if before or after:
                target=self.flat_foot(side,[sign*.105,.95 if before else -.95])
            else:
                target=self.flat_foot(side,[sign*(.105+.08*math.sin(math.pi*u)),root[1]+(-.40*math.sin(math.pi*u) if hand else sign*.06*math.sin(math.pi*u))])
                tuck=smooth(u/.32)*(1-smooth((u-.65)/.35)) if hand else math.sin(math.pi*u)**.65
                target['ankle'][2]=(.078+(.76 if hand else root[2]-.99+.26)*tuck)
                target['support']=False
            targets[side]=target
            self.arm(pose,side,0,25+(15 if hand and side=='Left' else 100)*math.sin(math.pi*u),25,15)
        pose=self.finish(pose,targets,limit=before or after)
        if hand and not after:
            weight=smooth((t-(takeoff-.35))/(.35+.28*flight))*(1-smooth((u-.44)/.44))
            if weight>0:
                before_pose=pose.copy();point=np.array([.16,0.,height+.06])
                self.hand(pose,'Left',point,pole=[1,-.3,.2])
                self.set_world_rotation(pose,'LeftHand',axis([0,0,1],-math.pi/2)@self.rest[self.index['LeftHand'],:3,:3])
                self.fingers(pose,0.)
                self.blend_rotations(pose,before_pose,weight)
                if not before and .28<=u<=.44:
                    error=float(np.linalg.norm(self.world(pose)[self.index['LeftHand'],:3,3]-point))
                    hand_errors['Left']=dict(target=point.tolist(),error=error)
        return pose,targets,hand_errors

    def build_performance(self,spec):
        count=round(spec.seconds*FPS)+1;poses=[];contacts=[];targets=[];hands=[]
        for frame in range(count):
            t=frame/FPS
            if spec.kind.startswith('vault'):pose,feet,hand=self.vault_frame(t,spec)
            elif spec.speed or spec.kind in ('duck','duck_jog'):pose,feet,hand=self.gait_frame(t,spec)
            else:pose,feet,hand=self.stationary_frame(t,spec)
            poses.append(pose);targets.append({s:f['ankle'].copy() for s,f in feet.items()})
            contacts.append([bool(feet[s]['support']) for s in ('Left','Right')]);hands.append(hand)
        poses=np.asarray(poses,dtype=np.float32)
        for frame in range(1,count):
            negative=np.sum(poses[frame-1,:,3:]*poses[frame,:,3:],axis=-1)<0
            poses[frame,negative,3:]*=-1
        return poses,np.array(contacts),targets,hands

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
