"""Export using the bundled, isolated Autodesk FBX SDK helper; no Blender required."""
from __future__ import annotations
from pathlib import Path
import struct
import subprocess
import tempfile
import warnings
import numpy as np
from scipy.spatial.transform import Rotation


def transforms(values):
    values=np.asarray(values,dtype=np.float64)
    result=np.zeros(values.shape[:-1]+(4,4))
    result[...,:3,:3]=Rotation.from_quat(values[...,3:].reshape(-1,4)).as_matrix().reshape(values.shape[:-1]+(3,3))
    result[...,:3,3]=values[...,:3];result[...,3,3]=1
    return result


def prepare_animation(payload,inplace=False):
    parents=np.asarray(payload['parents'],dtype=np.int32)
    poses=np.asarray(payload['poses'],dtype=np.float64)
    names=[str(n) for n in payload['joint_names']]
    if poses.ndim!=3 or poses.shape[1:]!=(len(names),7) or not len(poses):raise ValueError('Invalid animation dimensions')
    if len(parents)!=len(names) or parents[0]!=-1:raise ValueError('Invalid skeleton root')
    if any(parent<0 or parent>=i for i,parent in enumerate(parents[1:],1)):raise ValueError('Skeleton must be in parent-first order')
    if not np.isfinite(poses).all():raise ValueError('Animation contains non-finite values')
    if len(set(names))!=len(names) or 'RootMotion' in names:raise ValueError('Duplicate bone names')
    local=transforms(poses)
    displacement=poses[:,0,:3]-poses[0,0,:3];displacement[:,2]=0
    rotation=Rotation.from_quat(poses[:,0,3:])*Rotation.from_quat(poses[0,0,3:]).inv()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',UserWarning)
        yaw=rotation.as_euler('xyz')[:,2]
    ground=np.tile(np.eye(4),(len(poses),1,1))
    ground[:,:3,:3]=Rotation.from_euler('z',yaw[:,None]).as_matrix();ground[:,:3,3]=displacement
    if inplace:
        local[:,0,:3,3]-=displacement
        ground[:]=np.eye(4)
    local[:,0]=np.linalg.inv(ground)@local[:,0]
    local=np.concatenate((ground[:,None],local),axis=1)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',UserWarning)
        euler=Rotation.from_matrix(local[...,:3,:3].reshape(-1,3,3)).as_euler('xyz').reshape(len(poses),len(names)+1,3)
    euler=np.rad2deg(np.unwrap(euler,axis=0))
    channels=np.concatenate((local[...,:3,3],euler),axis=-1)
    if 'bind_world' in payload:bind=transforms(payload['bind_world'])
    else:
        bind=transforms(payload['reference'])
        for i,p in enumerate(parents):
            if p>=0:bind[i]=bind[p]@bind[i]
    return ['RootMotion']+names,np.concatenate(([-1],parents+1)),np.concatenate((np.eye(4)[None],bind)),channels


def write_snapshot(payload,path,*,inplace=False,include_mesh=True):
    names,parents,bind,channels=prepare_animation(payload,inplace)
    count=int(payload.get('mesh_count',0)) if include_mesh else 0
    fps=int(payload['fps'])
    if fps!=30:raise ValueError('FBX export requires 30 fps')
    with Path(path).open('wb') as out:
        out.write(struct.pack('<5I',0x54494246,len(names),len(channels),fps,count))
        for name,parent,world in zip(names,parents,bind):
            encoded=name.encode('utf-8');out.write(struct.pack('<I',len(encoded)));out.write(encoded)
            out.write(struct.pack('<i',int(parent)));out.write(np.asarray(world,dtype='<f8').tobytes())
        out.write(np.asarray(channels,dtype='<f8').tobytes())
        for k in range(count):
            prefix=f'mesh_{k}_'
            points=np.asarray(payload[prefix+'points'],dtype='<f8')
            triangles=np.asarray(payload[prefix+'triangles'],dtype='<u4')
            joints=np.asarray(payload[prefix+'joints'],dtype='<i4')
            weights=np.asarray(payload[prefix+'weights'],dtype='<f8')
            if points.ndim!=2 or points.shape[1]!=3 or triangles.ndim!=2 or triangles.shape[1]!=3:raise ValueError('Invalid mesh dimensions')
            if joints.ndim!=2 or weights.shape!=joints.shape or len(joints)!=len(points):raise ValueError('Invalid skin weights')
            if not np.isfinite(points).all() or not np.isfinite(weights).all() or np.any(weights<0):raise ValueError('Invalid mesh values')
            if np.any(triangles>=len(points)) or np.any(joints<0) or np.any(joints>=len(names)-1):raise ValueError('Invalid mesh indices')
            out.write(struct.pack('<3I',len(points),len(triangles),joints.shape[1]))
            for array in (points,triangles,joints,weights):out.write(array.tobytes())


def export_fbx(payload,destination,*,inplace=False,include_mesh=True):
    helper=Path(__file__).with_name('native')/'studio_fbx.exe'
    if not helper.is_file():raise FileNotFoundError('Bundled FBX exporter is missing. Restore app/native/studio_fbx.exe.')
    destination=Path(destination).resolve();destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.studio-fbx-',dir=destination.parent) as folder:
        snapshot=Path(folder)/'motion.bin';temporary=Path(folder)/'motion.fbx'
        write_snapshot(payload,snapshot,inplace=inplace,include_mesh=include_mesh)
        result=subprocess.run([str(helper),str(snapshot),str(temporary)],capture_output=True,text=True,
            encoding='utf-8',errors='replace',timeout=240,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode or not temporary.is_file():raise RuntimeError((result.stderr+'\n'+result.stdout)[-4000:])
        temporary.replace(destination)
    return str(destination)


# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
