"""Run with Blender --background --python ... -- snapshot.npz animation.fbx [inplace]."""
import json
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector


def matrix(t):
    x,y,z,w=t[3:]
    return Matrix.LocRotScale(Vector(t[:3]),Quaternion((w,x,y,z)),Vector((1,1,1)))


def main():
    args=sys.argv[sys.argv.index('--')+1:]
    data=np.load(args[0],allow_pickle=False)
    names=data['joint_names'].tolist()
    parents=data['parents']
    poses=data['poses'].copy()
    if len(args)>2 and args[2]=='inplace':
        poses[:,0,:2]=poses[0,0,:2]
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(Path(args[1]).resolve()),use_anim=True,anim_offset=0)
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    assert len(rig.pose.bones)==len(names)+1
    errors=[]
    details=[]
    mesh_errors=[]
    for f in sorted({1,len(poses)//2,len(poses)}):
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        worlds=[]
        for i,name in enumerate(names):
            m=matrix(poses[f-1,i])
            if parents[i]>=0:m=worlds[int(parents[i])]@m
            worlds.append(m)
            expected=m.translation
            actual=rig.matrix_world@rig.pose.bones[name].head
            errors.append((expected-actual).length)
            details.append(((expected-actual).length,f,name,list(expected),list(actual)))
        for k in range(int(data['mesh_count'])):
            mesh=bpy.data.objects.get(f'SOMA_Mesh_{k}')
            if mesh is None:continue
            prefix=f'mesh_{k}_'
            points=data[prefix+'points']
            indices,weights=data[prefix+'joints'],data[prefix+'weights']
            skin=np.array([np.array(worlds[i]@matrix(data['bind_world'][i]).inverted()) for i in range(len(names))])
            expected=np.zeros_like(points)
            for influence in range(indices.shape[1]):
                transforms=skin[indices[:,influence]]
                expected+=(np.einsum('nij,nj->ni',transforms[:,:3,:3],points)+transforms[:,:3,3])*weights[:,influence,None]
            evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
            actual=np.array([mesh.matrix_world@v.co for v in evaluated.data.vertices])
            mesh_errors.append(float(np.linalg.norm(expected-actual,axis=1).max()))
    result=dict(fbx=args[1],frames=len(poses),joints=len(names)+1,
                max_joint_position_error_m=max(errors),max_mesh_position_error_m=max(mesh_errors,default=0))
    print('FBX_VALIDATION '+json.dumps(result))
    print('JOINT_DIAGNOSTICS '+json.dumps(sorted(details,reverse=True)[:8]))
    assert max(errors)<.0001,result
    assert max(mesh_errors,default=0)<.0001,result


if __name__=='__main__':main()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
