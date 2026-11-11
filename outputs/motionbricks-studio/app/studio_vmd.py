"""PMX/PMD-aware SOMA to MMD FK retargeting and VMD 0002 serialization.

Original implementation. PMX rest positions, actual parent chains and limb
directions are used; simply renaming SOMA's local rotations is insufficient.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import struct
import numpy as np
from scipy.spatial.transform import Rotation
from .studio_data import fk

AXES=np.array([[1,0,0],[0,0,1],[0,1,0]],float) # Z-up RH -> MMD Y-up LH


@dataclass
class Bone:
    name:str
    position:np.ndarray
    parent:int
    flags:int=0
    tail:int=-1
    grant:int=-1
    grant_weight:float=0.
    axis:object=None
    tail_offset:object=None


class PMXReader:
    def __init__(self,stream):self.stream=stream
    def read(self,n):
        if n<0:raise ValueError('Negative MMD model data length.')
        data=self.stream.read(n)
        if len(data)!=n:raise ValueError('Truncated MMD model file.')
        return data
    def number(self,fmt):return struct.unpack('<'+fmt,self.read(struct.calcsize('<'+fmt)))[0]
    def vector(self):return np.array(struct.unpack('<3f',self.read(12)),float)
    def count(self):
        n=self.number('i')
        if n<0:raise ValueError('Negative PMX item count.')
        return n
    def index(self,size):return self.number({1:'b',2:'h',4:'i'}[size])
    def text(self):return self.read(self.count()).decode(self.encoding)


def read_pmx(path):
    with Path(path).open('rb') as stream:
        r=PMXReader(stream)
        if r.read(4)!=b'PMX ':raise ValueError('Select a PMX 2.0 or 2.1 model.')
        if not np.isclose(r.number('f'),[2.,2.1]).any():raise ValueError('Unsupported PMX version.')
        header=list(r.read(r.number('B')))
        if len(header)<8 or header[0] not in (0,1):raise ValueError('Invalid PMX header.')
        r.encoding='utf-16-le' if header[0]==0 else 'utf-8'
        _,uv,vi,ti,mi,bi,mo,ri=header[:8]
        if any(s not in (1,2,4) for s in (vi,ti,mi,bi,mo,ri)) or uv>4:
            raise ValueError('Invalid PMX index sizes.')
        name=r.text();r.text();r.text();r.text()
        for _ in range(r.count()):
            r.read(32+uv*16)
            mode=r.number('B')
            sizes={0:bi,1:bi*2+4,2:bi*4+16,3:bi*2+40,4:bi*4+16}
            if mode not in sizes:raise ValueError('Unsupported PMX vertex weight mode.')
            r.read(sizes[mode]+4)
        r.read(r.count()*vi)
        for _ in range(r.count()):r.text()
        for _ in range(r.count()):
            r.text();r.text();r.read(65+ti*2+1)
            shared=r.number('B')
            if shared not in (0,1):raise ValueError('Invalid PMX toon mode.')
            r.read(1 if shared else ti);r.text();r.read(4)
        bones=[]
        for _ in range(r.count()):
            bone_name=r.text();r.text();position=r.vector();parent=r.index(bi)
            r.read(4);flags=r.number('H')
            tail=r.index(bi) if flags&1 else -1
            tail_offset=r.vector() if not flags&1 else None
            grant,weight=-1,0.
            if flags&0x300:grant=r.index(bi);weight=r.number('f')
            axis=r.vector() if flags&0x400 else None
            if flags&0x800:r.read(24)
            if flags&0x2000:r.read(4)
            if flags&0x20:
                r.read(bi+8)
                for _ in range(r.count()):
                    r.read(bi)
                    if r.number('B'):r.read(24)
            bones.append(Bone(bone_name,position,parent,flags,tail,grant,weight,axis,tail_offset))
    if not bones or not np.isfinite([b.position for b in bones]).all():raise ValueError('Invalid PMX bones.')
    if len({b.name for b in bones})!=len(bones):raise ValueError('PMX has duplicate Japanese bone names.')
    order=parent_order(bones)
    return name,bones,order


def parent_order(bones):
    order=[];visiting=set();done=set()
    def visit(i):
        if i in done:return
        if i in visiting:raise ValueError('MMD model bone hierarchy contains a cycle.')
        visiting.add(i)
        parent=bones[i].parent
        if parent>=len(bones) or parent< -1:raise ValueError('Invalid MMD bone parent.')
        if parent>=0:visit(parent)
        visiting.remove(i);done.add(i);order.append(i)
    for i in range(len(bones)):visit(i)
    return order


def read_pmd(path):
    """Read PMD 1.0 bone records and the separate IK table into the common rig."""
    with Path(path).open('rb') as stream:
        r=PMXReader(stream)
        if r.read(3)!=b'Pmd' or not np.isclose(r.number('f'),1.):
            raise ValueError('Select a PMD 1.0 model.')
        name=r.read(20).split(b'\0')[0].decode('cp932')
        r.read(256)
        r.read(r.number('I')*38) # vertices: position, normal, UV, weights, edge
        r.read(r.number('I')*2)  # triangle indices
        r.read(r.number('I')*70) # materials
        bones=[];types=[]
        for _ in range(r.number('H')):
            label=r.read(20).split(b'\0')[0].decode('cp932')
            parent=r.number('H');tail=r.number('H');kind=r.number('B')
            influence=r.number('h' if kind==9 else 'H')
            position=r.vector()
            if kind>9:raise ValueError('Unsupported PMD bone type.')
            bone=Bone(label,position,-1 if parent==65535 else parent,
                      tail=-1 if tail==65535 or (tail==0 and kind not in (8,9)) else tail)
            if kind==5:bone.flags|=0x100;bone.grant=influence;bone.grant_weight=1.
            if kind==9:
                bone.flags|=0x100;bone.grant=bone.tail;bone.grant_weight=influence/100.
                bone.tail=-1
            bones.append(bone);types.append(kind)
        for _ in range(r.number('H')):
            controller=r.number('H');target=r.number('H');links=r.number('B')
            r.read(6)
            chain=[r.number('H') for _ in range(links)]
            if any(i>=len(bones) for i in [controller,target,*chain]):
                raise ValueError('Invalid PMD IK bone index.')
            bones[controller].flags|=0x20
    if not bones or not np.isfinite([b.position for b in bones]).all():raise ValueError('Invalid PMD bones.')
    if len({b.name for b in bones})!=len(bones):raise ValueError('PMD has duplicate bone names.')
    for bone,kind in zip(bones,types):
        if kind==8 and 0<=bone.tail<len(bones):
            bone.axis=bones[bone.tail].position-bone.position
            bone.flags|=0x400
    return name,bones,parent_order(bones)


def read_mmd_model(path):
    with Path(path).open('rb') as stream:signature=stream.read(4)
    if signature==b'PMX ':return read_pmx(path)
    if signature[:3]==b'Pmd':return read_pmd(path)
    raise ValueError('Select a PMX or PMD model.')


def bone_mapping(bones,names):
    target={b.name:i for i,b in enumerate(bones)}
    pairs={'下半身':'Hips','上半身':'Spine1','首':'Neck1','頭':'Head'}
    if '上半身３' in target or '上半身3' in target:pairs.update({'上半身2':'Spine2','上半身３':'Chest'})
    else:pairs['上半身2']='Chest'
    for side,source in [('左','Left'),('右','Right')]:
        for label,joint in [('肩','Shoulder'),('腕','Arm'),('ひじ','ForeArm'),('手首','Hand'),
                            ('足','Leg'),('ひざ','Shin'),('足首','Foot'),('つま先','ToeBase')]:
            pairs[side+label]=source+joint
        for digit in range(3):pairs[side+'親指'+str(digit)]=source+'HandThumb'+str(digit+1)
        for label,joint in [('人指','Index'),('中指','Middle'),('薬指','Ring'),('小指','Pinky')]:
            for digit in range(1,4):pairs[side+label+str(digit)]=source+'Hand'+joint+str(digit+1)
    # MMD models use both ASCII and full-width digit variants.
    normalized={name.translate(str.maketrans('０１２３','0123')):i for name,i in target.items()}
    if len(normalized)!=len(target):raise ValueError('Ambiguous half/full-width MMD bone names.')
    lookup={name:i for i,name in enumerate(names)}
    mapping={normalized[label.translate(str.maketrans('０１２３','0123'))]:lookup[joint]
             for label,joint in pairs.items()
             if label.translate(str.maketrans('０１２３','0123')) in normalized and joint in lookup}
    required=['下半身','上半身','左腕','右腕','左ひじ','右ひじ','左足','右足','左ひざ','右ひざ','左足首','右足首']
    missing=[name for name in required if name not in target]
    if missing:raise ValueError('Model is missing standard MMD bones: '+', '.join(missing))
    if 'センター' not in target:raise ValueError('Model needs a センター bone for root movement.')
    return mapping,target['センター']


def align_vectors(a,b):
    a=np.asarray(a,float);b=np.asarray(b,float)
    if min(np.linalg.norm(a),np.linalg.norm(b))<1e-7:return np.eye(3)
    a/=np.linalg.norm(a);b/=np.linalg.norm(b)
    cross=np.cross(a,b);dot=np.clip(np.dot(a,b),-1,1)
    if dot<-.999999:
        axis=np.cross(a,[1,0,0] if abs(a[0])<.8 else [0,1,0]);axis/=np.linalg.norm(axis)
        return Rotation.from_rotvec(axis*np.pi).as_matrix()
    if np.linalg.norm(cross)<1e-8:return np.eye(3)
    return Rotation.from_rotvec(cross/np.linalg.norm(cross)*np.arccos(dot)).as_matrix()


def validate_mmd_target(path,names):
    name,bones,order=read_mmd_model(path)
    mapping,center=bone_mapping(bones,names)
    for index in list(mapping)+[center]:
        i=index
        while i>=0:
            if bones[i].flags&0x300 and abs(bones[i].grant_weight)>1e-7:
                raise ValueError('MMD grant/inherit bone in driven chain is unsupported: '+bones[i].name)
            i=bones[i].parent
    target={b.name:i for i,b in enumerate(bones)}
    for side in ('左','右'):
        for a,b in [('足','ひざ'),('ひざ','足首')]:
            if np.linalg.norm(bones[target[side+a]].position-bones[target[side+b]].position)<1e-6:
                raise ValueError('MMD leg bone length is zero: '+side+a)
    return name,bones,order


def retarget(payload,bones,order,inplace=False):
    names=payload['joint_names'].tolist();parents=payload['parents']
    mapping,center=bone_mapping(bones,names)
    reference=fk(payload['reference'],parents)
    rest_rotation=Rotation.from_quat(reference[:,3:]).as_matrix()
    # Reject unsupported rotational/translation grants in the driven chain rather
    # than producing a file with subtly doubled motion.
    for index in list(mapping)+[center]:
        i=index
        while i>=0:
            if bones[i].flags&0x300 and abs(bones[i].grant_weight)>1e-7:
                raise ValueError('MMD grant/inherit bone in driven chain is unsupported: '+bones[i].name)
            i=bones[i].parent
    if center in mapping:raise ValueError('Invalid center mapping.')
    lookup={name:i for i,name in enumerate(names)}
    scale_parts=[]
    for side in ('左','右'):
        ids={b.name:i for i,b in enumerate(bones)}
        for a,b in [('足','ひざ'),('ひざ','足首')]:
            ta,tb=ids[side+a],ids[side+b]
            sa,sb=mapping[ta],mapping[tb]
            scale_parts.append(np.linalg.norm(bones[ta].position-bones[tb].position)/
                               max(np.linalg.norm(reference[sa,:3]-reference[sb,:3]),1e-7))
    scale=float(np.median(scale_parts))
    if not np.isfinite(scale) or scale<=0:raise ValueError('Invalid PMX leg proportions.')
    alignment={i:np.eye(3) for i in mapping}
    directions={}
    for i,source in mapping.items():
        if bones[i].name in ('下半身','上半身','上半身2','上半身２','上半身3','上半身３','首','頭'):continue
        # Prefer a mapped descendant; ignore helper/twist bones when finding direction.
        candidates=[]
        for child,source_child in mapping.items():
            parent=bones[child].parent;distance=0
            while parent>=0 and parent!=i:parent=bones[parent].parent;distance+=1
            if parent==i and source_child!=source:candidates.append((distance,child,source_child))
        if candidates:
            _,child,source_child=min(candidates,key=lambda c:(c[0],0 if 'Middle' in names[c[2]] else 1,c[1]))
            direction=bones[child].position-bones[i].position
            directions[i]=(direction,source_child)
            alignment[i]=align_vectors(direction,
                AXES@(reference[source_child,:3]-reference[source,:3]))
        else:
            source_children=np.flatnonzero(parents==source)
            direction=(bones[bones[i].tail].position-bones[i].position if 0<=bones[i].tail<len(bones)
                       else bones[i].tail_offset)
            if len(source_children) and direction is not None:
                directions[i]=(direction,source_children[0])
                alignment[i]=align_vectors(direction,AXES@(reference[source_children[0],:3]-reference[source,:3]))
    tracks={bones[i].name:[] for i in mapping};tracks[bones[center].name]=[]
    origin=payload['poses'][0,0,:3]
    previous={}
    for frame,pose in enumerate(payload['poses']):
        world=fk(pose,parents)
        source_rot=Rotation.from_quat(world[:,3:]).as_matrix()
        effective={}
        for i in order:
            parent=effective.get(bones[i].parent,np.eye(3))
            if i in mapping:
                source=mapping[i]
                delta=AXES@(source_rot[source]@rest_rotation[source].T)@AXES.T
                desired=delta@alignment[i]
                if i in directions:
                    direction,source_child=directions[i]
                    # Imported clip offsets can differ slightly from the model's
                    # reference offsets. Correct swing while preserving its twist.
                    desired=align_vectors(desired@direction,AXES@(world[source_child,:3]-world[source,:3]))@desired
                local=parent.T@desired
                q=Rotation.from_matrix(local).as_quat()
                if bones[i].axis is not None:
                    axis=np.asarray(bones[i].axis,float);length=np.linalg.norm(axis)
                    if length>1e-7:
                        axis/=length;q[:3]=axis*np.dot(q[:3],axis)
                        if np.linalg.norm(q)>1e-7:q/=np.linalg.norm(q)
                        else:q=np.array([0.,0.,0.,1.])
                if i in previous and np.dot(q,previous[i])<0:q=-q
                previous[i]=q
                effective[i]=parent@Rotation.from_quat(q).as_matrix()
                tracks[bones[i].name].append((frame,np.zeros(3),q))
            else:effective[i]=parent
        root=world[0,:3].copy()
        if inplace:root[:2]=origin[:2]
        translation=AXES@(root-reference[0,:3])*scale
        tracks[bones[center].name].append((frame,translation,np.array([0.,0.,0.,1.])))
    return tracks,scale


def encode_name(value,size):
    data=value.encode('cp932')
    if len(data)>size:raise ValueError('VMD name exceeds byte limit: '+value)
    return data.ljust(size,b'\0')


def export_vmd(payload,destination,pmx_path,inplace=False):
    if int(payload['fps'])!=30 or not np.isfinite(payload['poses']).all():
        raise ValueError('VMD export needs finite 30 fps animation.')
    model,bones,order=read_mmd_model(pmx_path)
    tracks,scale=retarget(payload,bones,order,inplace)
    path=Path(destination).resolve();path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.exporting.vmd')
    # Each channel has control points (20,20),(107,107): linear at 30 fps.
    interpolation=bytes([20]*8+[107]*8)*4
    try:
        with temporary.open('wb') as stream:
            stream.write(b'Vocaloid Motion Data 0002'.ljust(30,b'\0'))
            # Truncate the model label without splitting a CP932 character.
            header_name=b''
            for letter in model:
                encoded=letter.encode('cp932',errors='replace')
                if len(header_name)+len(encoded)>20:break
                header_name+=encoded
            stream.write(header_name.ljust(20,b'\0'))
            stream.write(struct.pack('<I',sum(map(len,tracks.values()))))
            for name,frames in tracks.items():
                encoded=encode_name(name,15)
                for frame,position,quaternion in frames:
                    stream.write(encoded+struct.pack('<I3f4f',frame,*position,*quaternion)+interpolation)
            stream.write(struct.pack('<4I',0,0,0,0)) # morph, camera, light, self shadow
            ik=[b.name for b in bones if b.flags&0x20]
            stream.write(struct.pack('<IIBI',1,0,1,len(ik)))
            for name in ik:stream.write(encode_name(name,20)+b'\0') # FK legs: disable IK solvers
        temporary.replace(path)
    finally:temporary.unlink(missing_ok=True)
    report=dict(model=model,target_model=str(Path(pmx_path).resolve()),target_format=Path(pmx_path).suffix.lower(),fps=30,frames=len(payload['poses']),
                scale_meters_to_pmx=scale,mapped_bones=list(tracks),disabled_ik=ik,
                mode='FK; target-model rest-direction correction; center translation')
    path.with_suffix('.vmd.report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return str(path)

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
