"""Replacement motion roles, rigid placement, seat transitions and mesh previews."""
from pathlib import Path
import copy,json,hashlib,math
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
from .studio_data import read_document,root_transform
from .studio_motion_data import sample_track
from .studio_mocap_retarget import forward,local_from_world,align_batch

ROOT=Path(__file__).resolve().parents[1]
ROLE_MAP={'walk':'walk_forward','run':'run_forward','vault_050':'vault_050','vault_075_hand':'vault_075','vault_075_free':'vault_075_no_hand','duck_walk':'duck_walk','duck_jog':'duck_jog','sit_down':'sit_down','seated_idle':'seated_idle','stand_up':'stand_up'}
class InteractionFitError(ValueError):pass


def load_role(app,ident):
    manifest=json.loads((ROOT/'assets/ti_original/kimodo_roles.json').read_text(encoding='utf8'))
    role=next((item for item in manifest['clips'] if item['role_id']==ROLE_MAP[ident]),None)
    if role is None:raise ValueError('Missing Kimodo replacement role: '+ROLE_MAP[ident])
    path=(ROOT/role['file']).resolve()
    if not path.is_relative_to((ROOT/'user_data/poses').resolve()):raise ValueError('Replacement path escapes the library')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=role['file_sha256']:raise ValueError('Replacement motion was edited. Register its new review before using it in an interaction / 動作が編集されています。再検査して割り当て直してください。')
    track=read_document(path,app.skeleton,'motion')[0]['motion_track']
    if track['origin']!='generated' or track.get('provenance',{}).get('source_sha256')!=role['source_sha256']:raise ValueError('Replacement motion provenance does not match the role')
    poses=np.stack([sample_track(track,i) for i in range(track['last_frame']+1)]) if len(track['keys'])!=track['last_frame']+1 else np.stack([k['pose'] for k in track['keys']])
    names=list(app.skeleton.joint_names);position,_=forward(poses,app.skeleton._np_parent_indices);travel=poses[-1,0,:2]-poses[0,0,:2]
    if np.linalg.norm(travel)>.5:heading=math.atan2(travel[0],-travel[1])
    else:
        across=position[0,names.index('LeftLeg'),:2]-position[0,names.index('RightLeg'),:2];heading=math.atan2(across[1],across[0])
    if ident.startswith('vault'):anchor=int(np.argmax(np.minimum(position[:,names.index('LeftFoot'),2],position[:,names.index('RightFoot'),2])))
    elif ident.startswith('duck'):anchor=int(np.argmin(position[:,names.index('Head'),2]))
    elif ident=='sit_down':anchor=len(poses)-1
    else:anchor=0
    q=Rotation.from_euler('z',-heading);offset=-q.apply(np.r_[poses[anchor,0,:2],0.]);poses=root_transform(poses,np.r_[offset,q.as_quat()])
    provenance=copy.deepcopy(track['provenance']);provenance.update(kind='kimodo_generated',role_id=role['role_id'],source_motion_sha256=role['file_sha256'],placement_anchor_frame=anchor,placement_yaw_degrees=-math.degrees(heading),quality_status='review_candidate')
    from .studio_interval import default_range
    meta=dict(kind='kimodo-role',role_id=role['role_id'],reference_height=.5 if ident=='vault_050' else .75 if ident.startswith('vault') else .4,rigid_only=True,provenance=provenance,usage_range=default_range(track))
    return poses.astype(np.float32),meta,path


def bridge(a,b,count=12):
    """Append a transition; never replace either source clip's frames."""
    w=np.arange(1,count+1)/(count+1);w=w*w*(3-2*w)
    p=(1-w[:,None,None])*a[None,:,:3]+w[:,None,None]*b[None,:,:3]
    r=np.stack([Slerp([0,1],Rotation.from_quat([qa,qb]))(w).as_quat() for qa,qb in zip(a[:,3:],b[:,3:])],axis=1)
    return np.concatenate((p,r),axis=-1).astype(np.float32)


def seat_sequence(app,box):
    if not hasattr(app,'_interaction_skin'):
        from .studio_original_build import static_assets
        app._interaction_skin=SkinPoints(static_assets())
    down,_,_=load_role(app,'sit_down');initial,_=forward(down[-1:],app.skeleton._np_parent_indices)
    feet=[app.skeleton.joint_names.index(side+'Foot') for side in ('Left','Right')];anchors=initial[0,feet,:2]+[0.,-.3]
    parts=[];provenance=[];sources=[]
    for ident in ('sit_down','seated_idle','stand_up'):
        p,meta,path=load_role(app,ident);sources.append(str(path));provenance.append(meta['provenance'])
        if ident!='seated_idle':
            lo,hi=meta['usage_range'];p=p[lo:hi+1].copy();provenance[-1]['used_source_frames']=[lo,hi]
        p,adaptation=adapt_seat(app._interaction_skin,p,ident,box['position'][2]+box['size'][2]/2,anchors)
        provenance[-1]['seat_adaptation']=adaptation
        if ident=='seated_idle':
            count=max(0,round(box.get('hold',2.)*30))
            if not count:continue
            original=p.copy()
            while len(p)<count:p=np.concatenate((p,bridge(p[-1],original[0]),original))
            p=p[:count]
        if parts:parts.append(bridge(parts[-1][-1],p[0]))
        parts.append(p)
    combined=np.concatenate(parts);combined,_=pin_ankles(app._interaction_skin,combined,anchors)
    skin=app._interaction_skin;half=np.asarray(box['size'][:2])/2;top=box['position'][2]+box['size'][2]/2;total_lift=np.zeros(len(combined))
    from scipy.ndimage import maximum_filter1d,gaussian_filter1d
    for iteration in range(3):
        p,r=forward(combined,skin.parents);required=np.zeros(len(combined))
        for start in range(0,len(combined),8):
            vertices=skin.vertices(p[start:start+8],r[start:start+8])[:,skin.seat_vertices]
            within=np.all(np.abs(vertices[:,:,:2])<half-.004,axis=-1)
            minimum=np.where(within,vertices[:,:,2],np.inf).min(axis=1);required[start:start+len(vertices)]=np.maximum(0,top+.001-minimum)
        if required.max()>.08:raise InteractionFitError('The seat needs a different source pose / この椅子には別の着座姿勢が必要です。')
        if required.max()<.001:break
        lift=np.maximum(required,gaussian_filter1d(maximum_filter1d(required,size=7),1.));total_lift+=lift;offset=np.zeros((len(combined),3));offset[:,2]=lift
        combined,_=pin_ankles(skin,combined,anchors,offset)
    for source in provenance:source['seat_surface_clearance_adjustment']=dict(max_lift_m=float(total_lift.max()),method='Pelvis/upper-thigh vertex clearance, support-leg IK, no arm or finger edits')
    return combined,provenance,sources


class SkinPoints:
    """Exact LBS vertex samples; intersections are a vertex proxy, not physics."""
    def __init__(self,assets):
        bind=assets['bind_world'];inverse=Rotation.from_quat(bind[:,3:]).as_matrix().swapaxes(-1,-2);self.groups=[];self.count=0;self.hip_vertices=[];self.seat_vertices=[]
        self.names=list(assets['joint_names']);self.parents=assets['parents'];self.reference=assets['reference']
        from .studio_mocap_retarget import SkinFootHeights
        self.foot_heights=SkinFootHeights.soma(assets)
        for mesh in range(int(assets['mesh_count'])):
            prefix=f'mesh_{mesh}_';ids=assets[prefix+'joints'];weights=assets[prefix+'weights'];points=assets[prefix+'points'];offset=self.count;self.count+=len(points)
            dominant=ids[np.arange(len(ids)),weights.argmax(axis=1)];self.hip_vertices.extend((np.flatnonzero(dominant==self.names.index('Hips'))+offset).tolist())
            self.seat_vertices.extend((np.flatnonzero(np.isin(dominant,[self.names.index(n) for n in ('Hips','LeftLeg','RightLeg')]))+offset).tolist())
            for bone in np.unique(ids[weights>1e-8]):
                v,k=np.where((ids==bone)&(weights>1e-8));unique,indices=np.unique(v,return_inverse=True);coefficient=np.zeros((len(unique),4))
                local=(points[v]-bind[bone,:3])@inverse[bone].T
                np.add.at(coefficient,indices,np.c_[local,np.ones(len(v))]*weights[v,k,None]);self.groups.append((int(bone),unique+offset,coefficient))
    def vertices(self,position,rotation):
        out=np.zeros((len(position),self.count,3))
        for bone,vertices,coefficient in self.groups:
            out[:,vertices]+=np.einsum('fij,vj->fvi',rotation[:,bone],coefficient[:,:3])+position[:,bone,None,:]*coefficient[None,:,3,None]
        return out


def adapt_seat(skin,poses,ident,height,anchors):
    """Calibrate the seat surface while holding original ankle paths/orientations."""
    p,r=forward(poses,skin.parents);sample=np.arange(max(0,len(poses)-5),len(poses)) if ident=='sit_down' else np.arange(min(5,len(poses))) if ident=='stand_up' else np.arange(0,len(poses),max(1,len(poses)//5))
    surface=skin.vertices(p[sample],r[sample])[:,skin.hip_vertices,2].min(axis=1);reference_height=float(np.median(surface))
    if ident=='seated_idle':weight=np.ones(len(poses))
    else:
        standing=poses[0,0,2] if ident=='sit_down' else poses[-1,0,2];seated=poses[-1,0,2] if ident=='sit_down' else poses[0,0,2]
        weight=np.clip((standing-poses[:,0,2])/max(float(standing-seated),.1),0,1);weight=weight*weight*(3-2*weight)
    offset=np.zeros((len(poses),3));offset[:,2]=(height-reference_height)*weight
    if ident!='seated_idle':offset[:,1]=-.3*(1-weight)
    result,check=pin_ankles(skin,poses,anchors,offset)
    return result,dict(method='Measured pelvis skin surface; seat approach and two-bone support-leg IK; source foot rotations retained',reference_height_m=reference_height,target_height_m=height,max_pelvis_shift_m=float(np.linalg.norm(offset,axis=1).max()),**check)


def pin_ankles(skin,poses,anchors,offset=None):
    p,r=forward(poses,skin.parents);names=skin.names;reference=skin.reference;_,reference_r=forward(reference[None],skin.parents)
    offset=np.zeros((len(poses),3)) if offset is None else offset.copy();feet=[names.index(s+'Foot') for s in ('Left','Right')];goals=p[:,feet].copy();goals[:,:,:2]=anchors
    desired=.001;result=poses.copy()
    for iteration in range(4):
        world=r.copy()
        for k,side in enumerate(('Left','Right')):
            a,b,c=[names.index(side+n) for n in ('Leg','Shin','Foot')];u,v=[np.linalg.norm(reference[j,:3]) for j in (b,c)];h=p[:,a]+offset;goal=goals[:,k]
            cap=goal[:,2]+np.sqrt(np.maximum(0,(u+v-1e-5)**2-np.sum((goal[:,:2]-h[:,:2])**2,axis=1)))-p[:,a,2]
            offset[:,2]=np.minimum(offset[:,2],cap)
        for k,side in enumerate(('Left','Right')):
            a,b,c=[names.index(side+n) for n in ('Leg','Shin','Foot')];u,v=[np.linalg.norm(reference[j,:3]) for j in (b,c)];h=p[:,a]+offset;goal=goals[:,k]
            direction=goal-h;distance=np.linalg.norm(direction,axis=1);direction/=np.maximum(distance[:,None],1e-9);distance=np.clip(distance,abs(u-v)+1e-5,u+v-1e-5)
            pole=np.einsum('fij,j->fi',r[:,a],reference_r[0,a].T@np.array([0.,-1.,0.]));pole-=direction*np.sum(pole*direction,axis=1,keepdims=True)
            measured=p[:,b]-p[:,a];measured-=direction*np.sum(measured*direction,axis=1,keepdims=True);strong=np.linalg.norm(measured,axis=1)>.005;pole[strong]=measured[strong]
            bad=np.linalg.norm(pole,axis=1)<1e-6;fallback=np.tile([0.,-1.,0.],(len(poses),1));fallback-=direction*np.sum(fallback*direction,axis=1,keepdims=True);pole[bad]=fallback[bad];pole/=np.maximum(np.linalg.norm(pole,axis=1,keepdims=True),1e-9)
            along=(u*u-v*v+distance*distance)/(2*distance);middle=h+direction*along[:,None]+pole*np.sqrt(np.maximum(0,u*u-along*along))[:,None]
            world[:,a]=align_batch(p[:,b]-p[:,a],middle-h)@r[:,a];world[:,b]=align_batch(p[:,c]-p[:,b],goal-middle)@r[:,b]
        result=local_from_world(world,poses[:,0,:3]+offset,reference,skin.parents).astype(np.float32);final,rot=forward(result,skin.parents)
        sole=skin.foot_heights.evaluate(final,rot);goals[:,:,2]+=desired-sole
    error=float(np.linalg.norm(final[:,feet,:2]-anchors,axis=-1).max())
    if error>.002 or np.abs(sole-desired).max()>.003:raise InteractionFitError('Cannot satisfy the seat support constraints. Use a matching seat/motion / 座面と足の接触条件を満たせません。')
    return result,dict(max_support_xy_error_m=error,min_sole_z_m=float(sole.min()),max_sole_z_m=float(sole.max()),max_root_adjustment_m=float(np.linalg.norm(offset,axis=1).max()))


def trim_flow_exit(app,poses,box,direction):
    """Leave a through-action after body clearance/landing, before its stop tail.

    This selects an unchanged prefix at runtime; it never rewrites source keys.
    Chairs deliberately use their separate hold/standing behavior.
    """
    skin=app._interaction_skin;d=np.asarray(direction,dtype=float);d=d/np.linalg.norm(d)
    c=Rotation.from_euler('z',box['yaw'],degrees=True).as_matrix()[:2,:2]
    edge=float(np.abs(d@c)@(np.asarray(box['size'][:2])/2))
    center=np.asarray(box['position'][:2]);root=(poses[:,0,:2]-center)@d
    p,r=forward(poses,skin.parents);sole=skin.foot_heights.evaluate(p,r)
    velocity=np.linalg.norm(np.diff(poses[:,0,:2],axis=0),axis=1)*30
    vz=np.gradient(poses[:,0,2])*30;clear=None
    for first in range(0,len(poses),8):
        candidates=np.arange(first,min(first+8,len(poses)))
        candidates=candidates[root[candidates]>edge+.3]
        if not len(candidates):continue
        vertices=skin.vertices(p[candidates],r[candidates])
        minimum=np.min((vertices[:,:,:2]-center)@d,axis=1)
        good=candidates[minimum>edge+.03]
        if len(good):clear=int(good[0]);break
    if clear is not None:
        for end in range(max(6,clear+6),len(poses)-4):
            if np.max(sole[end-2:end+1].min(axis=1))>.04 or abs(vz[end])>.8:continue
            if np.min(velocity[end-2:end+1])<.3:continue
            return poses[:end+1].copy(),dict(used_frames=[0,end],source_frames=len(poses),fully_clear_frame=clear,exit_speed_m_s=float(velocity[end]),method='All skinned vertices beyond far face + 6 frames; grounded support and moving exit, source prefix unchanged')
    return poses,dict(used_frames=[0,len(poses)-1],source_frames=len(poses),reason='No safe moving exit detected; source retained')


def collision_cloud(app,poses,box,direction=(0.,-1.),span=0.):
    """Skin once; retain exactly the vertices any searched placement can hit."""
    if not hasattr(app,'_interaction_skin'):
        from .studio_original_build import static_assets
        app._interaction_skin=SkinPoints(static_assets())
    p,r=forward(poses,app.skeleton._np_parent_indices);c=Rotation.from_euler('z',-box['yaw'],degrees=True).as_matrix()
    center=np.asarray(box['position']);half=np.asarray(box['size'])/2;cloud=[];frame_ids=[]
    direction=np.asarray(direction,dtype=float);direction=direction/np.linalg.norm(direction)
    local_direction=np.r_[direction,0.]@c.T
    reach=half-.008+abs(span)*np.abs(local_direction)
    for start in range(0,len(poses),8):
        points=(app._interaction_skin.vertices(p[start:start+8],r[start:start+8])-center)@c.T
        mask=np.all(np.abs(points)<reach,axis=-1)
        f,v=np.where(mask);cloud.append(points[f,v]);frame_ids.append(f+start)
    return np.concatenate(cloud),np.concatenate(frame_ids)


def object_check(app,poses,box,*,surface=None):
    """Vertex penetration preview. Does not certify support/contact or triangles."""
    points,frame_ids=collision_cloud(app,poses,box) if surface is None else surface
    margin=np.asarray(box['size'])/2-np.abs(points);inside=np.all(margin>.008,axis=-1)
    d=np.where(inside,margin.min(axis=-1),0.);depth=float(d.max()) if len(d) else 0.
    peak=int(frame_ids[d.argmax()]) if depth>0 else 0;count=int(inside.sum())
    return dict(method='LBS vertex-in-OBB proxy; not triangle/physics intersection',interior_margin_m=.008,penetrating_vertex_frames=count,max_depth_m=depth,peak_frame=peak)


def fit_translation(app,poses,box,direction,span=1.25,*,require_crossing=True,surface=None,crossing_margin=.25):
    """Search only a constant forward/back offset; never warp a joint or frame."""
    c=Rotation.from_euler('z',-box['yaw'],degrees=True).as_matrix()
    center=np.asarray(box['position']);half=np.asarray(box['size'])/2
    direction=np.asarray(direction,dtype=float);direction=direction/np.linalg.norm(direction)
    local_direction=np.r_[direction,0.]@c.T
    cloud,frame_ids=collision_cloud(app,poses,box,direction,span) if surface is None else surface
    best=None
    z_margin=half[2]-np.abs(cloud[:,2])
    root_projection=(poses[[0,-1],0,:2]-center[:2])@direction
    for shift in sorted(np.linspace(-span,span,81),key=abs):
        if require_crossing and (root_projection[0]+shift>-crossing_margin or root_projection[1]+shift<crossing_margin):continue
        mx=half[0]-np.abs(cloud[:,0]+shift*local_direction[0]);my=half[1]-np.abs(cloud[:,1]+shift*local_direction[1])
        inside=(mx>.008)&(my>.008)
        depths=np.where(inside,np.minimum(np.minimum(mx,my),z_margin),0.);depth=float(depths.max()) if len(depths) else 0.
        score=(depth,abs(shift))
        if best is None or score<best[0]:best=(score,shift,int(inside.sum()),int(frame_ids[int(depths.argmax())]) if len(depths) else 0)
        if depth<=.008:break
    if best is None:return poses,dict(method='Rigid shift search; no crossing interval',penetrating_vertex_frames=0,max_depth_m=float('inf'),peak_frame=0)
    _,shift,count,peak=best;result=poses.copy();result[:,0,:2]+=shift*direction
    return result,dict(method='LBS vertex-in-OBB proxy with constant forward shift; not triangle/physics intersection',interior_margin_m=.008,penetrating_vertex_frames=count,max_depth_m=best[0][0],peak_frame=peak,rigid_shift_m=float(shift))

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
