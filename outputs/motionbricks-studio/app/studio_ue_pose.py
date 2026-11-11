"""Explicit, revision-checked UE pose exchange. Runtime meters/Z-up -> UE cm/Z-up."""
from pathlib import Path
import json
import os
import uuid
from .studio_ue_transport import write_json as atomic_json,read_json
import numpy as np
from scipy.spatial.transform import Rotation
from .studio_data import fk, root_transform, validate_poses

SCHEMA='motionbricks-ue-pose'
# SOMA runtime: +X left, -Y forward, +Z up. UE: +X forward, +Y right, +Z up.
# This reflection maps both sides of each rotation matrix, not just translations.
BASIS=np.array([[0.,-1.,0.],[-1.,0.,0.],[0.,0.,1.]])


def to_ue(world):
    a=validate_poses(world,len(world)).astype(float)
    a[:,:3]=(a[:,:3]@BASIS.T)*100
    a[:,3:]=Rotation.from_matrix(BASIS@Rotation.from_quat(a[:,3:]).as_matrix()@BASIS).as_quat()
    return a.tolist()


def from_ue(world):
    a=validate_poses(world,len(world)).astype(float)
    a[:,:3]=(a[:,:3]@BASIS)/100
    a[:,3:]=Rotation.from_matrix(BASIS@Rotation.from_quat(a[:,3:]).as_matrix()@BASIS).as_quat()
    return a


def make_request(names,parents,reference,pose,entry_id,name):
    reference=validate_poses(reference,len(names));pose=validate_poses(pose,len(names))
    return dict(schema=SCHEMA,version=1,request_id=uuid.uuid4().hex,entry_id=int(entry_id),name=str(name),
                units='centimeters',space='UE_component',names=list(names),parents=list(map(int,parents)),
                reference=to_ue(fk(reference,parents)),pose=to_ue(fk(pose,parents)),
                source_local=pose.tolist())


def decode_response(request,response):
    if response.get('schema')!=SCHEMA or response.get('version')!=1:raise ValueError('Unsupported UE pose format')
    if response.get('request_id')!=request['request_id']:raise ValueError('UE pose belongs to a different request. Send the pose again.')
    names=request['names'];parents=request['parents'];n=len(names)
    source=validate_poses(request['source_local'],n)
    # Returned component-space poses are already converted to SOMA reference axes by UE.
    world=from_ue(response['soma_component'])
    if world.shape!=(n,7):raise ValueError('UE skeleton does not match the sent pose')
    result=source.copy()
    mapped=set(response['mapping'])
    if not {'Hips','LeftHand','RightHand','LeftFoot','RightFoot'}<=mapped:raise ValueError('Required UE bone mappings are missing')
    actual=[]
    for i,p in enumerate(parents):
        parent=actual[p] if p>=0 else Rotation.identity()
        if names[i] in mapped:
            desired=Rotation.from_quat(world[i,3:])
            result[i,3:]=(parent.inv()*desired).as_quat()
        else:
            desired=parent*Rotation.from_quat(source[i,3:])
        actual.append(desired)
    result[0,:3]=world[0,:3]
    # All child translations remain the SOMA lengths, even for a different UE body size.
    result=validate_poses(result,n)
    negative=np.sum(result[:,3:]*source[:,3:],axis=-1)<0
    result[negative,3:]*=-1
    return result


class UEPoseAuthoring:
    def send_ue_pose(self):
        reference=root_transform(self.skeleton.reference_local_transforms.numpy(),np.asarray(self.model_to_runtime))
        pose=root_transform(self.entry.preview_pose.numpy(),np.asarray(self.entry.placement),inverse=True)
        self.ue_pose_request=make_request(self.skeleton.joint_names,self.skeleton._np_parent_indices,
                                        reference,pose,self.entry.id,self.entry.name)
        self.ue_pose_request['placement']=np.asarray(self.entry.placement).tolist()
        self.ue_pose_request['source']=str(self.entry.path)
        self.ue_pose_request['motion_frame']=self.motion_cursor() if getattr(self.entry,'motion_track',None) is not None else None
        atomic_json(self.user_directory/'ue_bridge'/'request.json',self.ue_pose_request)
        self.status='Sent pose to UE. Use MotionBricks > Create IK Pose Editor in UE.'

    def receive_ue_pose(self,as_new=True):
        import warp as wp
        request=getattr(self,'ue_pose_request',None)
        if request is None:raise ValueError('Send a pose to UE first in this app session.')
        path=self.user_directory/'ue_bridge'/'response.json'
        if path.stat().st_size>4*1024*1024:raise ValueError('UE pose response is too large')
        response=read_json(path)
        pose=decode_response(request,response)
        index=next((i for i,e in enumerate(self.pose_entries) if e.id==request['entry_id']),None)
        if index is None:raise ValueError('The original target was deleted. Send another pose.')
        self.selected_index=index
        self.preview_playing=False;self.audio.pause();self.motion_playing=False
        if as_new:
            self.duplicate_target(index)
            self.entry.motion_track=None
            self.entry.placement=wp.transform(*request['placement']);self.entry.euler_degrees=None
            self.entry.name=request['name']+' UE IK'
            self.entry.path=Path(request.get('source') or 'ue-edited-pose')
            self.entry.manual_window=np.repeat(pose[None],4,axis=0)
            self.entry.num_poses_to_use=1;self.entry.hold_frames=0
            self.changed('Imported UE IK pose as a new target.')
        else:
            frame=request['motion_frame']
            if frame is not None:
                if getattr(self.entry,'motion_track',None) is None:raise ValueError('The source motion was replaced. Send another pose.')
                self.open_motion_editor();self.motion_frame=float(frame)
            self.edit_pose(pose if request.get('world_space') else root_transform(pose,np.asarray(self.entry.placement)),continuous=False)
        self.show_targets=True;self.show_generated=False;self.pose_name=self.entry.name


def draw_ue_menu(app,ui):
    if not ui.begin_menu('Unreal Engine'):return
    try:
        from .studio_ue_live import draw_live_menu
        draw_live_menu(app,ui)
        if ui.menu_item('Set up UE project connection...','',False,not app.busy)[0]:
            app.pending='configure_ue_project'
        if ui.menu_item('Fab…','',False)[0]:
            import webbrowser
            webbrowser.open('https://www.fab.com/')
    finally:ui.end_menu()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
