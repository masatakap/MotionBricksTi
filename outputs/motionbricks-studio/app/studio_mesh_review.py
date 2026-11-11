"""Targeted proper surface intersections for skinned motion review.

Non-adjacent hand/head, arm/torso and left/right leg triangles are checked.
Coplanar contact, complete containment and unlisted region pairs are not
certified by this test. Counts indicate surface crossings, not penetration depth.
"""
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from .studio_data import fk


def _segments_hit_triangles(a,b,triangles):
    direction=b-a;e1=triangles[:,1]-triangles[:,0];e2=triangles[:,2]-triangles[:,0]
    h=np.cross(direction,e2);det=np.sum(e1*h,axis=-1);usable=np.abs(det)>1e-12
    inverse=np.zeros_like(det);inverse[usable]=1./det[usable]
    s=a-triangles[:,0];u=inverse*np.sum(s*h,axis=-1);q=np.cross(s,e1)
    v=inverse*np.sum(direction*q,axis=-1);t=inverse*np.sum(e2*q,axis=-1)
    return usable&(u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7)&(t>1e-6)&(t<1-1e-6)


def proper_triangle_intersections(a,b):
    """Paired triangle arrays [N,3,3], excluding coplanar-only contacts."""
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    hit=np.zeros(len(a),bool)
    for i in range(3):
        hit|=_segments_hit_triangles(a[:,i],a[:,(i+1)%3],b)
        hit|=_segments_hit_triangles(b[:,i],b[:,(i+1)%3],a)
    return hit


def surface_crossings(points,triangles,first,second):
    ia=np.flatnonzero(first);ib=np.flatnonzero(second)
    if not len(ia) or not len(ib):return []
    va=points[triangles[ia]];vb=points[triangles[ib]]
    if np.any(va.max(axis=(0,1))<vb.min(axis=(0,1))) or np.any(vb.max(axis=(0,1))<va.min(axis=(0,1))):return []
    ca=va.mean(axis=1);cb=vb.mean(axis=1);ra=np.linalg.norm(va-ca[:,None],axis=-1).max(axis=1);rb=np.linalg.norm(vb-cb[:,None],axis=-1).max(axis=1)
    neighbors=cKDTree(cb).query_ball_point(ca,ra+rb.max())
    counts=np.array([len(v) for v in neighbors]);aa=np.repeat(np.arange(len(ia)),counts)
    if not len(aa):return []
    bb=np.concatenate(neighbors).astype(int)
    overlap=np.all(va[aa].max(axis=1)>=vb[bb].min(axis=1),axis=1)&np.all(vb[bb].max(axis=1)>=va[aa].min(axis=1),axis=1)
    aa,bb=aa[overlap],bb[overlap]
    # Shared vertices identify adjacent surface triangles, not self-crossings.
    adjacent=np.any(triangles[ia[aa]][:,:,None]==triangles[ib[bb]][:,None,:],axis=(1,2))
    aa,bb=aa[~adjacent],bb[~adjacent]
    hit=proper_triangle_intersections(va[aa],vb[bb])
    return np.stack((ia[aa[hit]],ib[bb[hit]]),axis=-1).tolist()


class SkinnedSurfaceReview:
    def __init__(self,assets):
        self.parents=assets['parents'];self.names=list(assets['joint_names']);self.meshes=[];self.bind_triangle_centers=[]
        bind=assets['bind_world'];inverse=Rotation.from_quat(bind[:,3:]).as_matrix().swapaxes(-1,-2)
        for mesh in range(int(assets['mesh_count'])):
            prefix=f'mesh_{mesh}_';points=assets[prefix+'points'];ids=assets[prefix+'joints'];weights=assets[prefix+'weights'];triangles=assets[prefix+'triangles']
            local=np.einsum('vkij,vkj->vki',inverse[ids],points[:,None]-bind[ids,:3])
            dominant=ids[np.arange(len(ids)),weights.argmax(axis=1)]
            def region(predicate):
                joints=np.array([i for i,n in enumerate(self.names) if predicate(n)])
                return np.isin(dominant[triangles],joints).sum(axis=1)>=2
            head=region(lambda n:n in ('Head','HeadEnd'))
            torso=region(lambda n:n in ('Hips','Spine1','Spine2','Chest','Neck1','Neck2'))
            masks={}
            for side in ('Left','Right'):
                masks[side+'Hand']=region(lambda n:n.startswith(side+'Hand'))
                masks[side+'Arm']=region(lambda n:any(n.startswith(side+p) for p in ('Shoulder','Arm','ForeArm','Hand')))
                masks[side+'Leg']=region(lambda n:any(n.startswith(side+p) for p in ('Leg','Shin','Foot','Toe')))
            pairs={side+'Hand_Head':(masks[side+'Hand'],head) for side in ('Left','Right')}
            pairs.update({side+'Arm_Torso':(masks[side+'Arm'],torso) for side in ('Left','Right')})
            pairs['LeftLeg_RightLeg']=(masks['LeftLeg'],masks['RightLeg'])
            self.meshes.append((ids,weights,local,triangles,pairs))
            self.bind_triangle_centers.append(points[triangles].mean(axis=1))

    def check_pose(self,pose):
        world=fk(pose,self.parents);r=Rotation.from_quat(world[:,3:]).as_matrix();found={}
        for mesh,(ids,weights,local,triangles,pairs) in enumerate(self.meshes):
            points=np.sum((np.einsum('vkij,vkj->vki',r[ids],local)+world[ids,:3])*weights[:,:,None],axis=1)
            for name,(first,second) in pairs.items():
                hits=surface_crossings(points,triangles,first,second)
                if hits:
                    pairs_array=np.asarray(hits);centers=self.bind_triangle_centers[mesh]
                    separation=np.linalg.norm(centers[pairs_array[:,0]]-centers[pairs_array[:,1]],axis=-1);near=separation<.06
                    found[f'{mesh}:{name}']=dict(pair_count=len(hits),nearby_in_bind_pose_count=int(near.sum()),remote_in_bind_pose_count=int((~near).sum()),bind_proximity_threshold_m=.06,sample_triangle_pairs=hits[:6],sample_remote_pairs=pairs_array[~near][:6].tolist())
        return found

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
