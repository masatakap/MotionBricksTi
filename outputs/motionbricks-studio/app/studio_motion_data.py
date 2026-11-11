"""Editable local skeletal tracks with preserved authoring/source provenance."""
import copy
import numpy as np
from .studio_data import validate_poses


def create_track(pose,origin='reference',source=''):
    pose=np.asarray(pose,dtype=np.float32).copy()
    return dict(last_frame=30,sample_frame=0,origin=origin,seed_source=source,
                keys=[dict(frame=0,pose=pose.copy()),dict(frame=30,pose=pose.copy())])


def validate_track(track,joints):
    if not isinstance(track,dict):raise ValueError('Invalid authored motion')
    last=track.get('last_frame');sample=track.get('sample_frame',0)
    if type(last) is not int or last<3 or type(sample) is not int or not 0<=sample<=last:raise ValueError('Invalid motion frame range')
    keys=track.get('keys')
    if not isinstance(keys,list) or len(keys)<2:raise ValueError('A motion needs at least two keys')
    previous=-1;result=copy.deepcopy(track)
    for key in result['keys']:
        frame=key.get('frame')
        if type(frame) is not int or not previous<frame<=last:raise ValueError('Motion keys must be unique and ordered')
        key['pose']=validate_poses(key.get('pose'),joints)
        if key['pose'].shape!=(joints,7):raise ValueError('Invalid motion key pose')
        previous=frame
    if keys[0]['frame']!=0 or keys[-1]['frame']!=last:raise ValueError('Motion needs first and last keys')
    if result.get('origin') not in ('reference','current_pose','licensed_reference','video_reference','generated','imported'):raise ValueError('Invalid motion origin')
    if not isinstance(result.get('seed_source',''),str):raise ValueError('Invalid seed source')
    if result.get('playback','conditioning') not in ('conditioning','full_clip','scene_exact'):raise ValueError('Invalid motion playback mode')
    if 'import_adjustment' in result:
        from .studio_import_adjustment import PURPOSES
        adjustment=result['import_adjustment']
        if (not isinstance(adjustment,dict) or adjustment.get('purpose') not in PURPOSES
                or type(adjustment.get('continue_after')) is not bool or 'interval' not in result):
            raise ValueError('Invalid motion import adjustment')
    if 'interval' in result:
        from .studio_interval import validate_settings
        validate_settings(result)
    return result


def plays_entire_motion(track):
    return bool(track and track.get('playback') in ('full_clip','scene_exact'))


def apply_library_playback_default(track,genre):
    """Set initial placement mode only; project loading keeps its saved choice."""
    if track is not None and track.get('playback')!='scene_exact' and 'import_adjustment' not in track:
        if genre!='dance':track['playback']='conditioning'
        else:track.setdefault('playback','full_clip')
    return track


def serialize_track(track):
    if track is None:return None
    result=copy.deepcopy(track)
    for key in result['keys']:key['pose']=np.asarray(key['pose']).tolist()
    return result


def sample_track(track,frame):
    keys=track['keys'];frames=[k['frame'] for k in keys]
    frame=float(np.clip(frame,0,track['last_frame']))
    right=min(max(1,int(np.searchsorted(frames,frame,side='right'))),len(keys)-1)
    a,b=keys[right-1],keys[right]
    t=(frame-a['frame'])/(b['frame']-a['frame'])
    p,q=np.asarray(a['pose'],dtype=np.float64),np.asarray(b['pose'],dtype=np.float64)
    out=p*(1-t)+q*t
    qa=p[:,3:];qb=q[:,3:].copy();dot=np.sum(qa*qb,axis=-1)
    qb[dot<0]*=-1;dot=np.clip(np.abs(dot),0,1)
    theta=np.arccos(dot);sine=np.sin(theta);regular=sine>1e-6
    alpha=np.full(len(p),1-t);beta=np.full(len(p),t)
    alpha[regular]=np.sin((1-t)*theta[regular])/sine[regular]
    beta[regular]=np.sin(t*theta[regular])/sine[regular]
    out[:,3:]=qa*alpha[:,None]+qb*beta[:,None]
    out[:,3:]/=np.linalg.norm(out[:,3:],axis=-1,keepdims=True)
    return out.astype(np.float32)


def put_key(track,frame,pose):
    frame=int(np.clip(round(frame),0,track['last_frame']))
    track['keys']=[k for k in track['keys'] if k['frame']!=frame]+[dict(frame=frame,pose=np.asarray(pose).copy())]
    track['keys'].sort(key=lambda k:k['frame'])


def resize_track(track,last):
    last=max(3,int(last));end=sample_track(track,last)
    track['keys']=[k for k in track['keys'] if k['frame']<last]
    track['last_frame']=last;put_key(track,last,end)
    track['sample_frame']=min(track['sample_frame'],last)
    if 'interval' in track:
        s=track['interval'];s['end']=min(s.get('end',last),last)
        s['start']=min(s.get('start',0),s['end']-3)
        if s['start']<0:s.update(start=0,end=3)


def conditioning_window(track,anchor):
    # Move the complete window inside the clip; never duplicate boundary frames.
    if 'import_adjustment' in track:
        from .studio_interval import settings
        interval=settings(track)
        low,high=interval['start'],interval['end']
    else:low,high=0,track['last_frame']
    start=int(np.clip(track['sample_frame']-anchor,low,high-3))
    return np.stack([sample_track(track,start+i) for i in range(4)])


def window_has_motion(window):
    window=np.asarray(window)
    moved=np.max(np.abs(window[...,:3]-window[0,:,:3]))>1e-6
    dot=np.abs(np.sum(window[...,3:]*window[0,:,3:],axis=-1))
    return bool(moved or np.any(1-dot>1e-6))

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
