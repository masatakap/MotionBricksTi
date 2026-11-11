"""Validated Studio documents and CPU-side skeletal editing. Quaternion order: XYZW."""
from __future__ import annotations

import json
import gzip
from pathlib import Path
import re
import numpy as np
from scipy.spatial.transform import Rotation

FORMAT = "motionbricks-studio"
VERSION = 1


def validate_poses(poses, count):
    a = np.asarray(poses, dtype=np.float32).copy()
    if a.ndim not in (2, 3) or a.shape[-2:] != (count, 7) or not np.isfinite(a).all():
        raise ValueError(f"Expected finite poses [..., {count}, 7].")
    norm = np.linalg.norm(a[..., 3:], axis=-1, keepdims=True)
    if np.any(norm < 1e-6):
        raise ValueError("A bone has an invalid rotation.")
    a[..., 3:] /= norm
    return a


def fk(pose, parents):
    """World transforms; parent joints must precede children."""
    p = np.asarray(pose)
    result = p.copy()
    for i, parent in enumerate(parents):
        if parent >= 0:
            r = Rotation.from_quat(result[parent, 3:])
            result[i, :3] = result[parent, :3] + r.apply(p[i, :3])
            result[i, 3:] = (r * Rotation.from_quat(p[i, 3:])).as_quat()
    return result


def same_transform(a,b,atol=1e-6):
    """Quaternion q and -q encode the same rotation, including gizmo roundtrips."""
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    if not np.allclose(a[:3],b[:3],atol=atol,rtol=0.):return False
    qa=a[3:]/max(np.linalg.norm(a[3:]),1e-12);qb=b[3:]/max(np.linalg.norm(b[3:]),1e-12)
    return bool(np.allclose(qa,qb,atol=atol,rtol=0.) or np.allclose(qa,-qb,atol=atol,rtol=0.))


def root_transform(poses, transform, inverse=False):
    a = np.asarray(poses, dtype=np.float32).copy()
    t = np.asarray(transform, dtype=np.float32)
    r = Rotation.from_quat(t[3:])
    root = a[..., 0, :].reshape(-1, 7)
    if inverse:
        root[:, :3] = r.inv().apply(root[:, :3] - t[:3])
        root[:, 3:] = (r.inv() * Rotation.from_quat(root[:, 3:])).as_quat()
    else:
        root[:, :3] = r.apply(root[:, :3]) + t[:3]
        root[:, 3:] = (r * Rotation.from_quat(root[:, 3:])).as_quat()
    a[..., 0, :] = root.reshape(a[..., 0, :].shape)
    return a


def solve_ik(pose, parents, effector, goal, chain_length=2, iterations=18):
    """CCD IK rotates ancestors while preserving joint offsets / bone lengths."""
    a = np.asarray(pose, dtype=np.float32).copy()
    chain = []
    j = int(parents[effector])
    while j > 0 and len(chain) < chain_length:
        chain.append(j)
        j = int(parents[j])
    for _ in range(iterations):
        for j in chain:
            world = fk(a, parents)
            v, w = world[effector, :3] - world[j, :3], np.asarray(goal) - world[j, :3]
            if np.linalg.norm(v) < 1e-8 or np.linalg.norm(w) < 1e-8:
                continue
            v, w = v / np.linalg.norm(v), w / np.linalg.norm(w)
            cross = np.cross(v, w)
            dot = np.clip(np.dot(v, w), -1, 1)
            if np.linalg.norm(cross) < 1e-7:
                if dot > 0:
                    continue
                cross = np.cross(v, [1, 0, 0] if abs(v[0]) < .8 else [0, 1, 0])
            angle = min(float(np.arccos(dot)), .45)
            delta = Rotation.from_rotvec(cross / np.linalg.norm(cross) * angle)
            parent = int(parents[j])
            rp = Rotation.identity() if parent < 0 else Rotation.from_quat(world[parent, 3:])
            a[j, 3:] = (rp.inv() * delta * rp * Rotation.from_quat(a[j, 3:])).as_quat()
        if np.linalg.norm(fk(a, parents)[effector, :3] - goal) < 1e-4:
            break
    return a


def safe_name(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip(' .')[:90] or 'Pose'


def mirror_pose(pose,reference,parents,names):
    """Swap anatomical sides in the root's frame, keeping root placement and offsets."""
    pose=np.asarray(pose,dtype=np.float32)
    reference=np.asarray(reference,dtype=np.float32)
    indices={name:i for i,name in enumerate(names)}
    swapped=[]
    for name in names:
        other=('Right'+name[4:] if name.startswith('Left') else
               'Left'+name[5:] if name.startswith('Right') else name)
        if other not in indices:raise ValueError('Missing mirror bone: '+other)
        swapped.append(indices[other])
    rest=Rotation.from_quat(fk(reference,parents)[:,3:]).as_matrix()
    current=Rotation.from_quat(fk(pose,parents)[:,3:]).as_matrix()
    # Facing is yaw only. Using the full tilted hip frame made the mirror
    # plane tilt with the torso and preserved an unwanted sideways lean.
    direction=(current[0]@rest[0].T)@np.array([0.,-1.,0.])
    yaw=np.arctan2(direction[0],-direction[1]) if np.linalg.norm(direction[:2])>1e-6 else 0.
    root_frame=Rotation.from_euler('z',yaw).as_matrix()
    reflection=np.diag([-1.,1.,1.])
    desired=np.array([root_frame@reflection@(root_frame.T@current[j])@rest[j].T@reflection@rest[i]
                      for i,j in enumerate(swapped)])
    result=pose.copy()
    for i,parent in enumerate(parents):
        local=desired[parent].T@desired[i] if parent>=0 else desired[i]
        result[i,3:]=Rotation.from_matrix(local).as_quat()
    result[0,:3]=pose[0,:3]
    return result


def retime_motion(poses,frame_count):
    """Linear translations and shortest-path quaternion SLERP; keep both endpoints."""
    source=np.asarray(poses,dtype=np.float32)
    if source.ndim!=3 or source.shape[-1]!=7 or len(source)<2 or frame_count<2:
        raise ValueError('Retiming needs at least two source and destination frames.')
    times=np.linspace(0,len(source)-1,int(frame_count))
    lo=np.floor(times).astype(int)
    hi=np.minimum(lo+1,len(source)-1)
    alpha=(times-lo)[:,None,None]
    a,b=source[lo],source[hi]
    out=np.empty((len(times),*source.shape[1:]),dtype=np.float32)
    out[:,:,:3]=a[:,:,:3]*(1-alpha)+b[:,:,:3]*alpha
    qa,qb=a[:,:,3:],b[:,:,3:].copy()
    dot=np.sum(qa*qb,axis=-1,keepdims=True)
    qb=np.where(dot<0,-qb,qb)
    dot=np.clip(np.abs(dot),0.,1.)
    theta=np.arccos(dot)
    sine=np.maximum(np.sin(theta),1e-8)
    spherical=(np.sin((1-alpha)*theta)*qa+np.sin(alpha*theta)*qb)/sine
    q=np.where(dot>.9995,(1-alpha)*qa+alpha*qb,spherical)
    out[:,:,3:]=q/np.maximum(np.linalg.norm(q,axis=-1,keepdims=True),1e-8)
    out[0],out[-1]=source[0],source[-1]
    return out


def write_document(path, kind, skeleton, entries, *, extras=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"format": FORMAT, "version": VERSION, "kind": kind,
            "joint_names": list(skeleton.joint_names),
            "parents": skeleton._np_parent_indices.tolist(), "entries": entries}
    if extras is not None:data['extras']=extras
    tmp = path.with_suffix(path.suffix + '.tmp')
    try:
        with gzip.open(tmp,'wt',encoding='utf-8',compresslevel=6) as stream:
            json.dump(data,stream,ensure_ascii=False,separators=(',',':'),allow_nan=False)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def read_document(path, skeleton, kind=None):
    path = Path(path)
    with path.open('rb') as stream:
        compressed=stream.read(2)==b'\x1f\x8b'
    opener=gzip.open if compressed else open
    with opener(path,'rt',encoding='utf-8') as stream:
        data=json.load(stream)
    if data.get('format') != FORMAT or data.get('version') != VERSION:
        raise ValueError("Unsupported Studio document.")
    if kind and data.get('kind') != kind:
        raise ValueError(f"Expected a {kind} document.")
    if data.get('joint_names') != list(skeleton.joint_names) or data.get('parents') != skeleton._np_parent_indices.tolist():
        raise ValueError("The pose skeleton does not match SOMA. Retarget it before importing.")
    entries = data.get('entries')
    if not isinstance(entries, list) or not entries:
        raise ValueError("A document needs at least one pose.")
    for e in entries:
        if not isinstance(e,dict) or not isinstance(e.get('name'),str) or not 1<=len(e['name'])<=256:
            raise ValueError('Each pose needs a name of 1 to 256 characters.')
        e['window'] = validate_poses(e['window'], skeleton.num_joints)
        if e['window'].shape != (4, skeleton.num_joints, 7):
            raise ValueError("Each entry needs four conditioning poses.")
        e['placement'] = validate_poses(np.asarray(e['placement']).reshape(1, 7), 1)[0]
        e['num_poses'] = int(e.get('num_poses', 1))
        e['min_tokens'], e['max_tokens'] = int(e.get('min_tokens', 8)), int(e.get('max_tokens', 14))
        if not 1 <= e['num_poses'] <= 4 or not 6 <= e['min_tokens'] <= e['max_tokens'] <= 16:
            raise ValueError("Invalid motion generation settings.")
        hold = int(e.get('hold_frames', 0))
        if not 0 <= hold <= 900:
            raise ValueError("Invalid hold duration.")
        e['hold_frames'] = hold
        duration=float(e.get('duration_seconds',0.))
        if not np.isfinite(duration) or not 0<=duration<=60:
            raise ValueError('Duration must be 0 (automatic) or at most 60 seconds.')
        e['duration_seconds']=duration
        e['ik_pin_mask']=int(e.get('ik_pin_mask',0));e['transition_early_by_frames']=int(e.get('transition_early_by_frames',0))
        if not 0<=e['ik_pin_mask']<=15 or not 0<=e['transition_early_by_frames']<=20:raise ValueError('Invalid interaction generation settings')
        e['scene_generated']=bool(e.get('scene_generated',False));e['scene_object_id']=str(e.get('scene_object_id',''))
        if e.get('motion_track') is not None:
            from .studio_motion_data import validate_track
            e['motion_track']=validate_track(e['motion_track'],skeleton.num_joints)
        if data.get('kind')=='motion' and e.get('motion_track') is None:
            raise ValueError('A motion file needs an authored keyframe track.')
    return entries


def read_extras(path):
    path=Path(path)
    with path.open('rb') as stream:compressed=stream.read(2)==b'\x1f\x8b'
    with (gzip.open if compressed else open)(path,'rt',encoding='utf-8') as stream:
        data=json.load(stream)
    return data.get('extras',{})

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
