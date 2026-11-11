"""Lossless-time Kimodo SOMA77 NPZ import; no inference, IK or smoothing.

Kimodo rotations use a standard T frame. Studio uses BONES/SOMA bone axes.
Use the official static axis calibration, not the first animation pose.
"""
from pathlib import Path
import hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation
from .studio_data import write_document,root_transform,safe_name
from .studio_motion_data import conditioning_window,serialize_track
from .studio_mocap_retarget import local_from_world,forward

CALIBRATION=Path(__file__).resolve().parents[1]/'assets/kimodo/soma77.json'
CONTACT_NAMES=['LeftFoot','LeftToeBase','LeftToeEnd','RightFoot','RightToeBase','RightToeEnd']

def convert_npz(path,skeleton,reference,*,fps=30.):
    path=Path(path);cal=json.loads(CALIBRATION.read_text(encoding='utf8'))
    names=list(skeleton.joint_names);parents=np.asarray(skeleton._np_parent_indices)
    if names!=cal['joint_names'] or not np.array_equal(parents,cal['parents']):raise ValueError('Kimodo import requires the supported SOMA77 skeleton.')
    with np.load(path,allow_pickle=False) as archive:
        required={'posed_joints','global_rot_mats','local_rot_mats','root_positions'}
        if not required.issubset(archive.files):raise ValueError('Not a Kimodo motion NPZ: missing '+', '.join(sorted(required-set(archive.files))))
        data={key:archive[key] for key in required|({'foot_contacts'}&set(archive.files))}
        if 'fps' in archive.files:fps=float(archive['fps'].item())
        if 'joint_names' in archive.files and archive['joint_names'].tolist()!=names:raise ValueError('NPZ bone names do not match SOMA77.')
    if fps!=30.:raise ValueError('This importer preserves 30 fps clips. Convert other frame rates explicitly first.')
    p,g,l,root=(np.asarray(data[k],dtype=np.float64) for k in ('posed_joints','global_rot_mats','local_rot_mats','root_positions'))
    frames=len(p)
    if frames<4 or p.shape!=(frames,77,3) or g.shape!=(frames,77,3,3) or l.shape!=g.shape or root.shape!=(frames,3):raise ValueError('Expected unbatched SOMA77 motion arrays with matching frame counts.')
    if not all(np.isfinite(a).all() for a in (p,g,l,root)):raise ValueError('Motion contains non-finite values.')
    for a in (g,l):
        if np.max(np.abs(a.swapaxes(-1,-2)@a-np.eye(3)))>2e-3 or np.max(np.abs(np.linalg.det(a)-1))>2e-3:raise ValueError('Invalid rotation matrices.')
    computed=l.copy()
    for j,parent in enumerate(parents):
        if parent>=0:computed[:,j]=computed[:,parent]@l[:,j]
    consistency=float(np.max(np.abs(computed-g)))
    if consistency>2e-3:raise ValueError('Local and world rotations disagree.')
    neutral=np.asarray(cal['standard_neutral_joints']);expected=np.broadcast_to(root[:,None],p.shape).copy()
    for j,parent in enumerate(parents):
        if parent>=0:expected[:,j]=expected[:,parent]+np.einsum('fij,j->fi',g[:,parent],neutral[j]-neutral[parent])
    source_error=float(np.max(np.linalg.norm(expected-p,axis=-1)))
    if source_error>2e-3:raise ValueError('Joint positions do not match the supported Kimodo skeleton/units/root.')
    contacts=data.get('foot_contacts')
    if contacts is not None and (contacts.shape!=(frames,6) or not np.isin(contacts,[0,1]).all()):raise ValueError('Expected six foot contact channels per frame.')
    c=Rotation.from_euler('x',90,degrees=True).as_matrix()
    world=c@g@np.asarray(cal['standard_to_bvh_global_axes'])
    poses=local_from_world(world,root@c.T,np.asarray(reference),parents).astype(np.float32)
    actual,actual_r=forward(poses,parents)
    angular=float(np.rad2deg(Rotation.from_matrix((world.swapaxes(-1,-2)@actual_r).reshape(-1,3,3)).magnitude()).max())
    metadata=dict(source_file=path.name,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),format='Kimodo SOMA77 NPZ',fps=fps,frames=frames,last_key_seconds=(frames-1)/fps,encoded_seconds=frames/fps,
        coordinate_conversion='meters, Y up -> meters, Z up; +90 degrees about X',axis_calibration_commit=cal['commit'],source_fk_error_m=source_error,source_local_world_matrix_error=consistency,
        destination_world_rotation_error_degrees=angular,destination_joint_position_difference_m=float(np.linalg.norm(actual-p@c.T,axis=-1).max()),
        target_bone_offsets_preserved=True,resampling=False,smoothing=False,ik=False,foot_correction=False,
        foot_contact_joint_names=CONTACT_NAMES if contacts is not None else [],foot_contacts=contacts.astype(bool).tolist() if contacts is not None else [])
    sidecar=path.with_suffix('.meta.json')
    if sidecar.is_file() and sidecar.stat().st_size<20000:
        try:
            job=json.loads(sidecar.read_text(encoding='utf8'))
            if isinstance(job,dict) and job.get('schema')=='motionbricks-kimodo-job-v1' and job.get('source_sha256')==metadata['source_sha256']:
                metadata['generation_job']={key:job[key] for key in ('schema','job_id','model','settings','source_sha256') if key in job}
        except (OSError,ValueError,TypeError):pass
    return poses,metadata

def save_import(path,skeleton,reference,output_dir,*,name=None,converted=None,adjustment=None):
    poses,meta=converted if converted is not None else convert_npz(path,skeleton,reference)
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    stem=safe_name(name or ('Kimodo_'+Path(path).stem));destination=output_dir/(stem+'.motion.json');suffix=2
    while destination.exists():destination=output_dir/(stem+f'_{suffix}.motion.json');suffix+=1
    from .studio_library import infer_genre
    track=dict(last_frame=len(poses)-1,sample_frame=0,origin='generated',seed_source=str(Path(path).resolve()),playback='full_clip' if infer_genre(stem)=='dance' else 'conditioning',
        authoring_method='Kimodo generated motion; static SOMA axis conversion only',provenance=meta,
        keys=[dict(frame=i,pose=pose) for i,pose in enumerate(poses)])
    from .studio_import_adjustment import apply_adjustment,initial_placement
    apply_adjustment(track,adjustment)
    entry=dict(name=name or stem,source=str(Path(path).resolve()),window=conditioning_window(track,0).tolist(),placement=initial_placement(track) if adjustment else [0,0,0,0,0,0,1],num_poses=4,min_tokens=8,max_tokens=14,hold_frames=0,duration_seconds=0.,motion_track=serialize_track(track))
    write_document(destination,'motion',skeleton,[entry],extras={'kimodo_import':meta})
    return destination,poses,meta

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
