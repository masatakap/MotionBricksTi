"""Reference-calibrated humanoid FBX/BVH import. Outputs remain review candidates."""
from pathlib import Path
import hashlib,json,math,re,subprocess,tempfile
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
from .studio_mocap_retarget import forward,local_from_world
from .studio_motion_data import conditioning_window,serialize_track
from .studio_data import safe_name,write_document
from .studio_motion_review import review_motion

REQUIRED=['Hips','Head']+[s+n for s in ('Left','Right') for n in ('Arm','ForeArm','Hand','Leg','Shin','Foot')]


def validate_source(data):
    names=data['names'];parents=np.asarray(data['parents']);rest=np.asarray(data['rest']);world=np.asarray(data['world']);fps=float(data['fps'])
    if len(names)!=len(set(names)):raise ValueError('Duplicate source bone names; export one character with unique names.')
    if world.ndim!=3 or world.shape[1:]!=(len(names),7) or rest.shape!=(len(names),7) or len(world)<2:raise ValueError('Invalid source animation dimensions')
    if len(parents)!=len(names) or any(p < -1 or p>=i for i,p in enumerate(parents)):raise ValueError('Invalid source hierarchy')
    if not np.isfinite(world).all() or not np.isfinite(rest).all() or not math.isfinite(fps) or fps<=0:raise ValueError('Non-finite motion or invalid frame rate')
    if np.any(np.linalg.norm(world[:,:,3:],axis=-1)<1e-8) or np.any(np.linalg.norm(rest[:,3:],axis=-1)<1e-8):raise ValueError('Invalid source quaternion')
    return data


def read_source(path,*,unit=.01,up='Y'):
    path=Path(path)
    if path.suffix.lower()=='.fbx':
        helper=Path(__file__).with_name('native')/'studio_fbx_read.exe'
        if not helper.is_file():raise ValueError('FBX import helper missing. Reinstall/build the Studio FBX reader.')
        with tempfile.TemporaryDirectory(prefix='studio-fbx-read-') as folder:
            output=Path(folder)/'motion.json'
            result=subprocess.run([str(helper),str(path.resolve()),str(output)],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if result.returncode:raise ValueError('FBX: '+result.stderr.strip()[:800])
            data=json.loads(output.read_text(encoding='utf8'))
        data.update(world=np.asarray(data['world']),rest=np.asarray(data['rest']),parents=np.asarray(data['parents']),coordinate='FBX SDK evaluated world, metres, Z up')
    elif path.suffix.lower()=='.bvh':
        if not math.isfinite(unit) or unit<=0:raise ValueError('BVH unit scale must be positive')
        if up not in ('Y','Z'):raise ValueError('Choose Y or Z up')
        import warp as wp
        from motionbricks.io.bvh import _read_bvh
        with wp.ScopedDevice('cpu'):skeleton,samples,channels,fps=_read_bvh(path,False)
        reference=skeleton.reference_local_transforms.numpy().astype(float);reference[:,:3]*=100*unit
        positions=np.broadcast_to(reference[None,:,:3],(len(samples),len(reference),3)).copy()
        rotations=np.broadcast_to(np.eye(3),(len(samples),len(reference),3,3)).copy();column=0
        for j,labels in enumerate(channels):
            order=[];angles=[]
            for name in labels:
                if name.endswith('position'):positions[:,j,'XYZ'.index(name[0])]+=samples[:,column]*unit
                else:order.append(name[0]);angles.append(samples[:,column])
                column+=1
            if order:rotations[:,j]=Rotation.from_euler(''.join(order),np.stack(angles,axis=1),degrees=True).as_matrix()
        parents=skeleton._np_parent_indices
        rp,rr=forward(reference[None],parents)
        for j,p in enumerate(parents):
            if p>=0:positions[:,j]=positions[:,p]+np.einsum('fij,fj->fi',rotations[:,p],positions[:,j]);rotations[:,j]=rotations[:,p]@rotations[:,j]
        basis=Rotation.from_euler('x',90,degrees=True).as_matrix() if up=='Y' else np.eye(3)
        def pack(p,r):return np.concatenate((p@basis.T,Rotation.from_matrix((basis@r).reshape(-1,3,3)).as_quat().reshape(*p.shape[:-1],4)),axis=-1)
        data=dict(names=list(skeleton.joint_names),parents=parents,rest=pack(rp,rr)[0],world=pack(positions,rotations),fps=float(fps),source_fps=float(fps),bind_complete=True,
                  coordinate=f'BVH world, {unit} metres per source unit, {up} up -> Z up',bvh_unit=unit,bvh_up=up)
    else:raise ValueError('Select FBX or BVH')
    data['source_file']=str(path.resolve());data['source_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    return validate_source(data)


def suggested_mapping(names,target_names):
    def key(name):return re.sub('[^a-z0-9]','',name.rsplit(':',1)[-1].lower())
    groups={}
    for name in names:groups.setdefault(key(name),[]).append(name)
    def find(*options):
        for option in options:
            matches=groups.get(key(option),[])
            if len(matches)==1:return matches[0]
        return None
    soma=find('LeftShin') is not None
    aliases={'Hips':('Hips','pelvis','J_Bip_C_Hips'),'Spine1':('Spine','spine_01','J_Bip_C_Spine'),'Spine2':('Spine1','spine_02','J_Bip_C_Chest'),
             'Chest':('Spine2','Chest','spine_03','J_Bip_C_UpperChest'),'Neck1':('Neck','neck_01','J_Bip_C_Neck'),'Neck2':('Neck1','neck_02'),'Head':('Head','J_Bip_C_Head')}
    for side,short,suffix in [('Left','L','l'),('Right','R','r')]:
        for role,mb,ue,vrm in [('Shoulder','Shoulder','clavicle','Shoulder'),('Arm','Arm','upperarm','UpperArm'),('ForeArm','ForeArm','lowerarm','LowerArm'),('Hand','Hand','hand','Hand'),('Leg','UpLeg','thigh','UpperLeg'),('Shin','Leg','calf','LowerLeg'),('Foot','Foot','foot','Foot'),('ToeBase','ToeBase','ball','ToeBase')]:aliases[side+role]=(side+mb,ue+'_'+suffix,f'J_Bip_{short}_{vrm}')
        for finger in ('Thumb','Index','Middle','Ring','Pinky'):
            for segment in range(1,4):
                target=segment if finger=='Thumb' else segment+1
                aliases[side+'Hand'+finger+str(target)]=(side+'Hand'+finger+str(segment),f'J_Bip_{short}_{"Little" if finger=="Pinky" else finger}{segment}')
    result={}
    for target in target_names:
        value=find(target) if soma else find(*aliases.get(target,()))
        if value:result[target]=value
    return result


def validate_mapping(data,mapping):
    names=data['names'];parents=data['parents'];missing=[n for n in REQUIRED if not mapping.get(n)]
    if not any(mapping.get(n) for n in ('Spine1','Spine2','Chest')):missing.append('Spine / Chest')
    if missing:raise ValueError('Map required bones: '+', '.join(missing))
    values=list(mapping.values())
    if len(values)!=len(set(values)) or any(n not in names for n in values):raise ValueError('Source bones must be unique and present in the source')
    def descendant(child,parent):
        child=names.index(mapping[child]);parent=names.index(mapping[parent])
        while child>=0:
            if child==parent:return True
            child=int(parents[child])
        return False
    for side in ('Left','Right'):
        for child,parent in [('ForeArm','Arm'),('Hand','ForeArm'),('Shin','Leg'),('Foot','Shin')]:
            if not descendant(side+child,side+parent):raise ValueError('Invalid limb hierarchy: '+side+child)
    if not descendant('Head','Hips'):raise ValueError('Head must descend from Hips')


def convert(data,mapping,skeleton,reference,*,reference_frame=-1,yaw=0.):
    validate_source(data);validate_mapping(data,mapping)
    source=np.asarray(data['world']);rest=np.asarray(data['rest'])
    if reference_frame>=0:
        if not 0<=reference_frame<len(source):raise ValueError('Invalid neutral reference frame')
        rest=source[reference_frame]
    elif not data.get('bind_complete',False):raise ValueError('No complete FBX bind pose. Specify an actual neutral T-pose frame.')
    names=list(skeleton.joint_names);parents=np.asarray(skeleton._np_parent_indices);reference=np.asarray(reference)
    idx={n:i for i,n in enumerate(data['names'])};dst={n:i for i,n in enumerate(names)}
    for side in ('Left','Right'):
        arm=rest[idx[mapping[side+'ForeArm']],:3]-rest[idx[mapping[side+'Arm']],:3]
        if np.linalg.norm(arm)<1e-6 or abs(arm[2])>np.linalg.norm(arm)*.5:
            raise ValueError('Reference arms are not a neutral T pose. Choose a recorded T-pose frame / 中立T姿勢のフレームを指定してください。')
    if any(n not in dst for n in mapping):raise ValueError('Unknown target bone')
    duration=(len(source)-1)/data['fps'];times=np.minimum(np.arange(math.ceil(duration*30-1e-7)+1)/30,duration);original=np.arange(len(source))/data['fps']
    if len(times)<4:raise ValueError('Motion must cover at least four 30 fps frames')
    p=np.stack([np.interp(times,original,a) for a in source[:,:,:3].reshape(len(source),-1).T],axis=1).reshape(len(times),-1,3)
    rot=np.stack([Slerp(original,Rotation.from_quat(source[:,j,3:]))(times).as_matrix() for j in range(len(idx))],axis=1)
    bind=Rotation.from_quat(rest[:,3:]).as_matrix();tp,tr=forward(reference[None],parents);tr=tr[0]
    right=rest[idx[mapping['RightLeg']],:3]-rest[idx[mapping['LeftLeg']],:3]
    target_right=tp[0,dst['RightLeg']]-tp[0,dst['LeftLeg']]
    if min(np.linalg.norm(right[:2]),np.linalg.norm(target_right[:2]))<1e-6:raise ValueError('Neutral hip positions do not define the facing direction')
    angle=math.atan2(target_right[1],target_right[0])-math.atan2(right[1],right[0])+math.radians(yaw)
    c=Rotation.from_euler('z',angle).as_matrix();local_ref=Rotation.from_quat(reference[:,3:]).as_matrix();world=np.empty((len(times),len(names),3,3))
    for j,name in enumerate(names):
        if name in mapping:
            source_id=idx[mapping[name]];world[:,j]=c@rot[:,source_id]@bind[source_id].T@c.T@tr[j]
        else:world[:,j]=world[:,parents[j]]@local_ref[j] if parents[j]>=0 else local_ref[j]
    lengths=[]
    for side in ('Left','Right'):
        ids=[idx[mapping[side+n]] for n in ('Leg','Shin','Foot')];length=sum(np.linalg.norm(rest[b,:3]-rest[a,:3]) for a,b in zip(ids,ids[1:]))
        target_length=sum(np.linalg.norm(reference[dst[side+n],:3]) for n in ('Shin','Foot'))
        if length<1e-5:raise ValueError('Source leg length is zero')
        lengths.append(target_length/length)
    scale=float(np.mean(lengths));hip=idx[mapping['Hips']];root=reference[0,:3]+scale*((p[:,hip]-rest[hip,:3])@c.T);root[:,:2]-=root[0,:2]
    poses=local_from_world(world,root,reference,parents).astype(np.float32)
    meta=dict(source_file=data['source_file'],source_sha256=data['source_sha256'],format=Path(data['source_file']).suffix,source_fps=data['source_fps'],decoded_fps=data['fps'],fps=30,
              source_frames=len(source),frames=len(poses),coordinate=data['coordinate'],mapping=mapping,reference_frame=reference_frame,translation_scale=scale,yaw_degrees=yaw,
              source_duration_seconds=data.get('duration',duration),last_key_seconds=(len(poses)-1)/30,ik=False,smoothing=False,contact_correction=False,status='review_candidate')
    return poses,meta


def save_candidate(data,mapping,skeleton,reference,folder,*,name=None,reference_frame=-1,yaw=0.,converted=None,adjustment=None):
    poses,meta=converted if converted is not None else convert(data,mapping,skeleton,reference,reference_frame=reference_frame,yaw=yaw)
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);stem=safe_name(name or Path(data['source_file']).stem);path=folder/(stem+'.motion.json');suffix=2
    while path.exists() or path.with_suffix('.review.json').exists():path=folder/(stem+f'_{suffix}.motion.json');suffix+=1
    track=dict(last_frame=len(poses)-1,sample_frame=0,origin='imported',seed_source=data['source_file'],playback='conditioning',provenance=meta,
               authoring_method='User-selected humanoid FBX/BVH reference-calibrated retarget',keys=[dict(frame=i,pose=p) for i,p in enumerate(poses)])
    from .studio_import_adjustment import apply_adjustment,initial_placement
    apply_adjustment(track,adjustment)
    entry=dict(name=name or stem,source=data['source_file'],window=conditioning_window(track,0).tolist(),placement=initial_placement(track) if adjustment else [0,0,0,0,0,0,1],num_poses=4,min_tokens=8,max_tokens=14,hold_frames=0,duration_seconds=0.,motion_track=serialize_track(track))
    review=review_motion(poses,skeleton._np_parent_indices,skeleton.joint_names,30,reference=reference) if len(poses)>=3 else {'numeric_status':'too_short_to_review'}
    write_document(path,'motion',skeleton,[entry],extras={'external_import':meta,'review':review})
    path.with_suffix('.review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf8')
    return path,poses,review

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
