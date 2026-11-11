"""Independent interaction assets and exact playback, in Studio meters/Z-up."""
import copy,json,math,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from .runtime.common.rig import ASSETS_ROOT
from .studio_data import read_document,root_transform
from .studio_motion_data import sample_track

ORIGINALS=ASSETS_ROOT/'ti_original'

def load_clip(app,ident):
    manifest=json.loads((ORIGINALS/'interactions.json').read_text(encoding='utf-8'))
    if manifest.get('schema')!='motionbricks-ti-independent-interactions' or manifest.get('version')!=1:raise ValueError('Invalid interaction manifest')
    if manifest.get('clips',{}).get(ident,{}).get('kind')=='kimodo-role':
        from .studio_scene_kimodo import load_role
        return load_role(app,ident)
    if not hasattr(app,'_original_interaction_cache'):app._original_interaction_cache={}
    if ident not in app._original_interaction_cache:
        manifest=json.loads((ORIGINALS/'interactions.json').read_text(encoding='utf-8'))
        if manifest.get('schema')!='motionbricks-ti-independent-interactions' or manifest.get('version')!=1:raise ValueError('Invalid independent interaction manifest')
        if ident not in manifest['clips']:
            raise ValueError('This interaction motion was retired. Import/rebuild its replacement first. / この動作は削除済みです。代わりの動作データを作成・登録してください。')
        meta=manifest['clips'][ident];path=(ORIGINALS/meta['file']).resolve()
        override=ORIGINALS/'reference_overrides.json'
        licensed=False
        if override.exists():
            references=json.loads(override.read_text(encoding='utf-8'))
            if references.get('schema')!='motionbricks-ti-reference-interactions' or references.get('version')!=1:raise ValueError('Invalid reference interaction manifest')
            if ident in references['clips']:
                meta=references['clips'][ident];path=(ORIGINALS/meta['file']).resolve();licensed=True
        if not path.is_relative_to(ORIGINALS.resolve()):raise ValueError('Interaction path escapes the asset folder')
        track=read_document(path,app.skeleton,'motion')[0]['motion_track']
        if licensed:
            provenance=track.get('provenance',{})
            if track['origin']!='licensed_reference' or not all(provenance.get(k) for k in ('creator','license','source_url')):raise ValueError('Missing reference license or attribution')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['file_sha256']:raise ValueError('Reference interaction file differs from its review')
            meta=copy.deepcopy(meta);meta['provenance']=copy.deepcopy(provenance)
        elif track['origin']!='reference' or track.get('seed_source'):raise ValueError('Interaction must be independently authored from reference geometry')
        poses=dense_track(track);app._original_interaction_cache[ident]=(poses,meta,path)
    poses,meta,path=app._original_interaction_cache[ident]
    return poses.copy(),meta,path

def dense_track(track):
    keys=track['keys']
    if len(keys)==track['last_frame']+1:return np.stack([k['pose'] for k in keys]).astype(np.float32)
    return np.stack([sample_track(track,i) for i in range(track['last_frame']+1)])

def exact_track(poses,ident,provenance=None):
    generated=bool(provenance and provenance.get('kind')=='kimodo_generated')
    result=dict(last_frame=len(poses)-1,sample_frame=0,origin='generated' if generated else 'licensed_reference' if provenance else 'reference',seed_source=provenance.get('source_file','') if generated else provenance.get('source_url','') if provenance else '',
                playback='scene_exact',performance_id=ident,authoring_method='Independent static-reference interaction',
                keys=[dict(frame=i,pose=p.copy()) for i,p in enumerate(poses)])
    if provenance:result['provenance']=copy.deepcopy(provenance);result['authoring_method']='Kimodo clips; rigid placement, seat pelvis/support-foot adaptation and separate transitions' if generated else 'Licensed motion reference, SOMA retarget and placement'
    return result

def blend_tail(frames,target,count=10):
    frames=frames.copy();count=min(count,len(frames))
    for j,i in enumerate(range(len(frames)-count,len(frames))):
        w=(j+1)/count;w=w*w*(3-2*w)
        a=frames[i,:,3:];b=target[:,3:];b=b*np.where(np.sum(a*b,axis=-1,keepdims=True)<0,-1,1)
        q=(1-w)*a+w*b;frames[i,:,3:]=q/np.linalg.norm(q,axis=-1,keepdims=True)
        frames[i,:,:3]=(1-w)*frames[i,:,:3]+w*target[:,:3]
    frames[-1]=target
    return frames


def adapt_seat(app,poses,meta,height):
    delta=height-meta['reference_height']
    if abs(delta)<1e-5:return poses
    if not hasattr(app,'_interaction_reference_rig'):
        from .studio_original_build import static_assets
        from .studio_original_library import AdultPerformance
        app._interaction_reference_rig=AdultPerformance(static_assets())
    rig=app._interaction_reference_rig
    weights=meta.get('seat_weights')
    for frame,pose in enumerate(poses):
        world=rig.world(pose);feet={}
        for side in ('Left','Right'):
            a=world[rig.index[side+'Foot']];toe=world[rig.index[side+'ToeBase']]
            supports=meta.get('supports')
            feet[side]=dict(ankle=a[:3,3].copy(),foot_rotation=a[:3,:3],toe_rotation=toe[:3,:3],support=bool(supports[frame][0 if side=='Left' else 1]) if supports is not None else True)
        seated=weights[frame] if weights is not None else np.clip((.99-pose[0,2])/(.99-.580),0,1);pose[0,2]+=delta*seated
        pose[:]=rig.finish(pose,feet)
    return poses

def placed(poses,xy,yaw):
    transform=np.r_[xy,0.,Rotation.from_euler('z',yaw).as_quat()]
    return root_transform(poses,transform)

def route_window(app,point,direction):
    ident='walk' if app.environment['speed']=='walk' else 'run';poses,_,path=load_clip(app,ident)
    window=poses[8:12].copy();window[:,0,:2]-=window[0,0,:2].copy()
    yaw=math.atan2(direction[0],-direction[1]);window=placed(window,np.asarray(point)[:2],yaw)
    return dict(window=window,name='Route / '+ident,source=str(path))


def imported_transit_targets(app,box,direction,action):
    from .studio_interval import validate_settings
    from .studio_scene_kimodo import collision_cloud,fit_translation,trim_flow_exit,InteractionFitError

    if action not in ('jump_0_5m','jump_0_75m','avoidance'):
        raise InteractionFitError('Select Jump or Duck for an imported obstacle motion / 通過用の動作にはジャンプまたはくぐりを選んでください。')
    path=Path(box['asset'])
    entry=read_document(path,app.skeleton,'motion')[0]
    track=entry['motion_track'];adjustment=track.get('import_adjustment',{})
    if adjustment.get('purpose')!='transit':
        raise InteractionFitError('Select a motion prepared for obstacle passage / 障害物を通過する動作として登録した素材を選択してください。')
    interval=validate_settings(track);start,end=interval['start'],interval['end']
    poses=dense_track(track)[start:end+1].copy()
    roots=poses[:,0,:2];travel=roots[-1]-roots[0]
    if np.linalg.norm(travel)<.1:
        raise InteractionFitError('The selected frame range needs forward root travel / 使用範囲内に前方へのルート移動が必要です。')
    heading=np.asarray(direction,dtype=float)[:2];heading/=np.linalg.norm(heading)
    yaw=math.atan2(heading[1],heading[0])-math.atan2(travel[1],travel[0])
    # Center the highest/lowest pelvis over the object initially. The rigid
    # placement search then checks the actual skinned character at every frame.
    z=poses[:,0,2]
    anchor=int(np.argmin(z) if action=='avoidance' else np.argmax(z))
    roots-=roots[anchor].copy()
    poses=placed(poses,box['position'][:2],yaw)
    axes=Rotation.from_euler('z',box['yaw'],degrees=True).as_matrix()[:2,:2]
    half_depth=float(np.abs(heading@axes)@np.asarray(box['size'][:2])/2)
    surface=collision_cloud(app,poses,box,heading,1.25)
    poses,check=fit_translation(app,poses,box,heading,surface=surface,crossing_margin=half_depth+.1)
    if not np.isfinite(check['max_depth_m']):
        raise InteractionFitError('The motion does not travel across the box in the selected range / 選択した範囲ではボックスの手前から反対側まで届きません。')
    if check['max_depth_m']>.02:
        raise InteractionFitError(f"Imported motion intersects the box ({check['max_depth_m']:.3f} m) / 取り込んだ動作がボックスと干渉しています。")
    credit=copy.deepcopy(track.get('provenance',{}))
    credit.update(imported_motion=str(path),source_range=[start,end],object_check=check)
    if adjustment.get('continue_after',True):
        poses,credit['flow_exit']=trim_flow_exit(app,poses,box,heading)
    exact=exact_track(poses,'imported_transit')
    exact.update(origin=track['origin'],seed_source=track['seed_source'],provenance=credit,
                 authoring_method='Imported obstacle clip with rigid placement and measured clearance')
    return [dict(window=poses[:4].copy(),name=box['name']+' / '+entry['name'],source=str(path),track=exact)]

def primitive_targets(app,box,direction,action):
    d=np.asarray(direction,dtype=float)[:2];d/=np.linalg.norm(d);yaw=math.atan2(d[0],-d[1])
    sequence=int(box.get('sequence',0));height=box['position'][2]+box['size'][2]/2;provenance=[]
    from .studio_scene_kimodo import seat_sequence,object_check,fit_translation,collision_cloud,InteractionFitError
    replacement=False
    if action=='sit' and load_clip(app,'sit_down')[1].get('kind')=='kimodo-role':
        if abs(height-.4)>.025:raise InteractionFitError('This seat candidate is calibrated for a 0.4 m seat. Adjust height or provide a matching motion / この着座候補は座面高0.4m用です。')
        yaw=math.radians(box['yaw']);poses,provenance,sources=seat_sequence(app,box);ident='sit_hold_stand';replacement=True
    elif action=='sit':
        yaw=math.radians(box['yaw']);parts=[];sources=[]
        for ident in ('sit_down','seated_idle','stand_up'):
            p,meta,path=load_clip(app,ident);p=adapt_seat(app,p,meta,height);sources.append(str(path))
            if meta.get('provenance'):provenance.append(meta['provenance'])
            if ident=='seated_idle':
                count=round(box.get('hold',2.)*30)
                if not count:continue
                p=p[np.arange(count+1)%(len(p)-1)];p=blend_tail(p,parts[-1][-1],min(6,len(p)))
            parts.append(p if not parts else p[1:])
        poses=np.concatenate(parts);ident='sit_hold_stand'
    else:
        if action=='jump_0_5m':ident='vault_050'
        elif action=='jump_0_75m':
            ident=('vault_075_hand','vault_075_free')[sequence%2]
            # A narrow or diagonal box may not support the authored hand point.
            hand=np.array([-d[1],d[0]])*.16
            local=Rotation.from_euler('z',-box['yaw'],degrees=True).apply(np.r_[hand,0])[:2]
            if np.any(np.abs(local)>np.asarray(box['size'][:2])/2-.02):ident='vault_075_free'
        else:ident='duck_jog' if app.environment['speed']=='run' or sequence%2 else 'duck_walk'
        poses,meta,path=load_clip(app,ident);sources=[str(path)]
        replacement=meta.get('kind')=='kimodo-role'
        if meta.get('provenance'):provenance.append(meta['provenance'])
        if ident.startswith('vault') and not meta.get('rigid_only'):
            if 'height_adjustment_weights' in meta:
                envelope=np.asarray(meta['height_adjustment_weights'],dtype=float)
                if envelope.shape!=(len(poses),) or not np.isfinite(envelope).all():raise ValueError('Invalid reference flight weights')
                envelope=np.clip(envelope,0,1)
            else:
                flight=.72 if ident=='vault_050' else .82 if ident=='vault_075_hand' else .76
                t=np.arange(len(poses))/30;u=np.clip((t-1.05)/flight,0,1)
                from .studio_walk_authoring import smooth
                envelope=np.array([smooth(x/.22)*(1-smooth((x-.75)/.25)) for x in u])
            lift=(height-meta['reference_height'])*envelope
            lift=np.maximum(lift,.001-np.asarray(meta['minimum_sole_z']))
            poses[:,0,2]+=lift
    poses=placed(poses,box['position'][:2],yaw)
    if replacement:
        fit_direction=Rotation.from_euler('z',yaw).apply([0,-1,0])[:2]
        span=.05 if action=='sit' else 1.25
        surface=collision_cloud(app,poses,box,fit_direction,span)
        check=object_check(app,poses,box,surface=surface)
        if check['max_depth_m']>.02:poses,check=fit_translation(app,poses,box,fit_direction,span,require_crossing=action!='sit',surface=surface)
        if check['max_depth_m']>.02 and ident in ('vault_050','vault_075_hand'):
            original_ident=ident
            alternative,meta,path=load_clip(app,'vault_075_free')
            candidate=placed(alternative,box['position'][:2],yaw);surface=collision_cloud(app,candidate,box,fit_direction,1.25)
            alternative_check=object_check(app,candidate,box,surface=surface)
            if alternative_check['max_depth_m']>.02:candidate,alternative_check=fit_translation(app,candidate,box,fit_direction,surface=surface)
            if alternative_check['max_depth_m']<check['max_depth_m']:
                poses=candidate;check=alternative_check;provenance=[meta['provenance']];sources=[str(path)];ident='vault_050_high_clearance' if original_ident=='vault_050' else 'vault_075_free'
        if check['max_depth_m']>.02:
            raise InteractionFitError(f"Motion does not clear this object (vertex penetration up to {check['max_depth_m']:.3f} m). Use Auto/Avoid or adjust the object / この動作では物体を通過できません。Auto・迂回、または寸法調整を使用してください。")
        for source in provenance:source['object_check']=check
        if action!='sit':
            from .studio_scene_kimodo import trim_flow_exit
            poses,exit_info=trim_flow_exit(app,poses,box,fit_direction)
            for source in provenance:source['flow_exit']=exit_info
    credit=dict(provenance[0],component_sources=provenance) if provenance else None
    stage=dict(window=poses[:4].copy(),name=box['name']+' / '+ident,source=sources[0],track=exact_track(poses,ident,credit))
    result=[stage]
    if action=='sit':
        heading=Rotation.from_euler('z',yaw).apply([0,-1,0])[:2]
        reach=box['size'][1]/2+app.environment['radius']+.3
        approach=poses[0].copy();point=np.asarray(box['position'][:2])+heading*reach
        approach[0,:2]=point
        result.insert(0,dict(window=np.repeat(approach[None],4,axis=0),num=1,name=box['name']+' / Approach',source=sources[0]))
        result.append(route_window(app,np.asarray(box['position'][:2])+heading*reach,heading))
    return result

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
