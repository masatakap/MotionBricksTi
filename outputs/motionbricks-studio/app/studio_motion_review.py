"""Reusable motion QA: final-curve identity, local/world motion and regressions.

Numerical checks deliberately do not certify visual fidelity, collision-free
meshes, physical stability, export correctness, or a target UE skeleton.
"""
import hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation

CHECKLIST='docs/MOTION_QUALITY_CHECKLIST_JA.md'


def curve_hash(poses,parents,names,fps):
    a=np.asarray(poses,dtype='<f4',order='C')
    header=json.dumps(dict(shape=a.shape,parents=np.asarray(parents).tolist(),names=list(names),fps=float(fps)),sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(header+a.tobytes()).hexdigest()


def world_rotations(poses,parents):
    a=np.asarray(poses);r=Rotation.from_quat(a[:,:,3:].reshape(-1,4)).as_matrix().reshape(*a.shape[:2],3,3)
    for j,parent in enumerate(parents):
        if parent>=0:r[:,j]=r[:,parent]@r[:,j]
    return r


def _angular_report(r,fps,names,spatial=False):
    relative=(r[1:]@r[:-1].swapaxes(-1,-2)) if spatial else (r[:-1].swapaxes(-1,-2)@r[1:])
    vectors=Rotation.from_matrix(relative.reshape(-1,3,3)).as_rotvec().reshape(len(r)-1,len(names),3)
    step=np.rad2deg(np.linalg.norm(vectors,axis=-1));f,j=np.unravel_index(np.argmax(step),step.shape)
    acceleration=np.rad2deg(np.linalg.norm(np.diff(vectors,axis=0),axis=-1))*fps*fps
    return dict(max_step_degrees=float(step[f,j]),max_speed_deg_s=float(step[f,j]*fps),p95_speed_deg_s=float(np.percentile(step,95)*fps),max_location=dict(frame=int(f),next_frame=int(f+1),seconds=float(f/fps),bone=names[j]),p95_acceleration_deg_s2=float(np.percentile(acceleration,95)),max_acceleration_deg_s2=float(acceleration.max()))


def review_motion(poses,parents,names,fps=30.,reference=None,extra_metrics=None,speed_warning_deg_s=600.):
    a=np.asarray(poses,dtype=float);parents=np.asarray(parents);names=list(names)
    if a.ndim!=3 or a.shape[2]!=7 or len(a)<3 or a.shape[1]!=len(names) or len(parents)!=len(names):raise ValueError('Expected at least 3 frames of a matching skeleton')
    if not np.isfinite(a).all() or not np.isfinite(fps) or fps<=0:raise ValueError('Motion and fps must be finite; fps must be positive')
    if len(set(names))!=len(names) or any(p < -1 or p>=j for j,p in enumerate(parents)):raise ValueError('Bones must be unique and parents must precede children')
    norms=np.linalg.norm(a[:,:,3:],axis=-1)
    if np.any(norms<1e-8):raise ValueError('Invalid zero quaternion')
    local=Rotation.from_quat(a[:,:,3:].reshape(-1,4)).as_matrix().reshape(*a.shape[:2],3,3)
    world=world_rotations(a,parents);rest=a[0] if reference is None else np.asarray(reference)
    if rest.shape!=a.shape[1:]:raise ValueError('Reference pose does not match skeleton')
    offset_error=float(np.max(np.abs(a[:,1:,:3]-rest[None,1:,:3])))
    root_speed=np.linalg.norm(np.diff(a[:,0,:3],axis=0),axis=-1)*fps
    root_acceleration=np.linalg.norm(np.diff(a[:,0,:3],n=2,axis=0),axis=-1)*fps*fps
    metrics=dict(local=_angular_report(local,fps,names),world=_angular_report(world,fps,names,spatial=True),quaternion_norm_error=float(np.max(np.abs(norms-1))),bone_offset_error_m=offset_error,root_max_speed_m_s=float(root_speed.max()),root_max_acceleration_m_s2=float(root_acceleration.max()))
    issues=[]
    for space in ('local','world'):
        if metrics[space]['max_speed_deg_s']>speed_warning_deg_s:issues.append(dict(code=space+'_rotation_speed',severity='review',**metrics[space]['max_location'],value=metrics[space]['max_speed_deg_s'],unit='deg/s',threshold=speed_warning_deg_s))
    if offset_error>1e-5:issues.append(dict(code='bone_offsets_changed',severity='error',value=offset_error,unit='m'))
    if metrics['quaternion_norm_error']>1e-4:issues.append(dict(code='quaternion_norm',severity='error',value=metrics['quaternion_norm_error']))
    if extra_metrics:metrics.update(extra_metrics)
    return dict(schema='motionbricks-motion-review-v1',checklist=CHECKLIST,curve_sha256=curve_hash(a,parents,names,fps),frames=len(a),fps=float(fps),last_key_time_seconds=(len(a)-1)/fps,encoded_duration_seconds=len(a)/fps,metrics=metrics,issues=issues,numeric_status='needs_attention' if issues else 'within_configured_checks',visual_status='pending',manual_checks={k:'pending' for k in ('source_rights','reference_alignment','front_side_back','normal_and_slow_playback','support_and_balance','mesh_intersections','export_roundtrip','ue_target_retarget')})


def compare_reviews(before,after):
    """Fail closed on geometry regressions, even if angular smoothness improved."""
    regressions=[]
    for key,tolerance in [('collision_proxy_max_m',.001),('front_order_violation_max_m',.001),('image_rmse_m',.002),('balance_envelope_max_m',.003),('bone_offset_error_m',1e-5)]:
        a=before['metrics'].get(key);b=after['metrics'].get(key)
        if a is not None and b is not None and b>a+tolerance:regressions.append(dict(metric=key,before=a,after=b,tolerance=tolerance))
    for key in ('local','world'):
        a=before['metrics'][key]['max_speed_deg_s'];b=after['metrics'][key]['max_speed_deg_s']
        if b>a+3.:regressions.append(dict(metric=key+'_max_speed_deg_s',before=a,after=b,tolerance=3.))
    if before['frames']!=after['frames'] or before['fps']!=after['fps']:regressions.append(dict(metric='timeline_changed',before=[before['frames'],before['fps']],after=[after['frames'],after['fps']]))
    return dict(baseline_curve_sha256=before['curve_sha256'],candidate_curve_sha256=after['curve_sha256'],regressions=regressions,automatic_adoption='blocked' if regressions or after['issues'] else 'requires_visual_and_applicable_export_review')

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
