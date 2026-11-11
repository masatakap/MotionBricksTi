"""Local Live Link transport, explicit control commands and deterministic full-frame bake."""
from pathlib import Path
import gzip
import json
import sys
import time
import uuid
import numpy as np
from scipy.spatial.transform import Rotation
from .studio_ue_pose import UEPoseAuthoring,atomic_json,to_ue,from_ue
from .studio_data import fk,root_transform
from .studio_motion_data import sample_track
from .studio_ue_transport import transient_io,read_json


class UEBridge(UEPoseAuthoring):
    def ue_directory(self):
        return self.user_directory/'ue_bridge'

    def configure_ue_project(self, path):
        project = Path(path).resolve()
        if project.suffix.lower() != '.uproject' or not project.is_file():
            raise ValueError('Select an existing Unreal Engine .uproject file.')
        config = {
            'exchange_directory': str(self.ue_directory().resolve()),
            'studio_python': str(Path(sys.executable).absolute()),
            'font_directory': str(Path(__file__).with_name('fonts').resolve()),
        }
        atomic_json(project.parent/'Saved'/'MotionBricks'/'bridge_config.json', config)

    def connect_ue(self):
        self.send_ue_pose()
        world=self.entry.preview_pose.numpy()
        self.ue_pose_request['source_local']=world.tolist()
        self.ue_pose_request['pose']=to_ue(fk(world,self.skeleton._np_parent_indices))
        self.ue_pose_request['placement']=[0,0,0,0,0,0,1]
        self.ue_pose_request['world_space']=True
        atomic_json(self.ue_directory()/'request.json',self.ue_pose_request)
        self.ue_live=True;self.ue_sequence=0;self.ue_last_publish=0.;self.ue_clip_id=getattr(self,'ue_clip_id',uuid.uuid4().hex)
        self.ue_revision=uuid.uuid4().hex
        self.status='UE connection enabled. Register a character from the UE MotionBricks menu.'

    def disconnect_ue(self):
        self.ue_live=False
        atomic_json(self.ue_directory()/'frame.json',{'connected':False,'sequence':getattr(self,'ue_sequence',0)+1})

    def step_ue_bridge(self):
        if not getattr(self,'ue_live',False):return
        self.poll_ue_save()
        now=time.perf_counter()
        if now-getattr(self,'ue_last_publish',0)<1/30:return
        self.ue_last_publish=now;self.ue_sequence+=1
        generated=self.timeline is not None and self.show_generated and not self.timeline_stale
        pose=self.current_pose.numpy() if generated else self.entry.preview_pose.numpy()
        seconds=(self.transport_position if self.audio.path else self.timeline_time) if generated else (
            getattr(self,'motion_frame',0.)/30 if getattr(self,'motion_editor_open',False) else self.audio.position if self.audio.path else 0.)
        previous=getattr(self,'ue_last_time',seconds)
        if abs(seconds-previous)>.15:self.ue_revision=uuid.uuid4().hex
        self.ue_last_time=seconds
        packet=dict(connected=True,sequence=self.ue_sequence,
            request_id=self.ue_pose_request['request_id'],revision=self.ue_revision,clip_id=self.ue_clip_id,
            time=seconds,playing=bool(self.preview_playing or self.audio.playing or getattr(self,'motion_playing',False)),
            sent_at=time.time(),targets=self.ue_target_times(),pose=to_ue(fk(pose,self.skeleton._np_parent_indices)))
        try:atomic_json(self.ue_directory()/'frame.json',packet)
        except OSError as exc:
            if transient_io(exc):return  # Keep the previous packet; try the next frame.
            self.ue_live=False
            self.status='UE synchronization stopped: '+str(exc)

    def ue_command(self,action,**options):
        ident=uuid.uuid4().hex
        atomic_json(self.ue_directory()/'command.json',dict(id=ident,request_id=self.ue_pose_request['request_id'],action=action,**options))
        return ident

    def poll_ue_save(self):
        request=read_json(self.ue_directory()/'save_request.json',optional=True)
        if request and request.get('request_id')==self.ue_pose_request['request_id'] and request.get('id')!=getattr(self,'ue_last_save_request',None):
            self.ue_last_save_request=request['id']
            if time.time()-request.get('sent_at',0)<30:
                try:self.bake_to_ue(save_id=request['id'])
                except Exception as exc:
                    self.error=str(exc)
                    atomic_json(self.ue_directory()/'save_response.json',dict(request_id=request['request_id'],save_id=request['id'],status='error',error=str(exc)))
        result=read_json(self.ue_directory()/'save_result.json',optional=True)
        if result and result.get('request_id')==self.ue_pose_request['request_id'] and result.get('save_id')==getattr(self,'ue_pending_save_id',None):
            self.ue_pending_save_id=None
            if result.get('status')=='saved':self.status='UEへ保存しました / Saved to UE: '+result['animation']
            else:self.error='UEへの保存に失敗しました / UE save failed: '+str(result.get('error','Unknown error'))

    def ue_export_poses(self):
        if getattr(self,'motion_editor_open',False):
            track=getattr(self.entry,'motion_track',None)
            if track is not None:
                poses=(np.stack([key['pose'] for key in track['keys']]) if len(track['keys'])==track['last_frame']+1 else
                       np.stack([sample_track(track,i) for i in range(track['last_frame']+1)]))
                return root_transform(poses,np.asarray(self.entry.placement)),'selected_clip'
        if self.timeline_cpu is None or self.timeline_stale:
            raise ValueError('保存する動作を動作編集で開くか、モーションを生成してください。 / Open a motion clip or generate the current timeline before saving.')
        return self.timeline_cpu.copy(),'generated_timeline'

    def bake_to_ue(self,*,save_id=None):
        if not getattr(self,'ue_live',False):raise ValueError('Connect to UE first.')
        poses,source=self.ue_export_poses()
        request=self.ue_pose_request
        directory=self.ue_directory();directory.mkdir(parents=True,exist_ok=True)
        save_id=save_id or uuid.uuid4().hex
        if self.audio.path:
            extra=max(0,round(self.audio.duration*30)+1-len(poses))
            if extra:poses=np.concatenate([poses,np.repeat(poses[-1:],extra,axis=0)])
        frames=[to_ue(fk(p,self.skeleton._np_parent_indices)) for p in poses]
        data=dict(schema='motionbricks-ue-bake',version=1,request_id=request['request_id'],
                  clip_id=self.ue_clip_id,revision=uuid.uuid4().hex,fps=30,frames=frames,
                  targets=self.ue_target_times(),save_id=save_id,source=source)
        if self.audio.path:
            import wave,miniaudio
            decoded=miniaudio.decode(Path(self.audio.path).read_bytes(),output_format=miniaudio.SampleFormat.SIGNED16)
            audio=directory/'music.wav'
            with wave.open(str(audio),'wb') as out:
                out.setnchannels(decoded.nchannels);out.setsampwidth(2);out.setframerate(decoded.sample_rate);out.writeframes(decoded.samples.tobytes())
            data['audio_file']=str(audio.resolve())
        path=directory/'bake.json.gz';temporary=directory/'bake.json.gz.tmp'
        try:
            with gzip.open(temporary,'wt',encoding='utf-8') as out:json.dump(data,out,allow_nan=False)
            temporary.replace(path)
        finally:temporary.unlink(missing_ok=True)
        self.ue_pending_save_id=save_id
        self.ue_command('bake',save_id=save_id)
        atomic_json(directory/'save_response.json',dict(request_id=request['request_id'],save_id=save_id,status='sent',frames=len(frames)))
        self.status='Sent all motion frames to UE for retargeting and saving.'

    def ue_target_times(self):
        # Segment lengths come from the actual generated frame ranges, when available.
        return getattr(self,'ue_generated_target_times',{})

    def import_ue_targets(self):
        import warp as wp
        path=self.ue_directory()/'targets.json'
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('request_id')!=self.ue_pose_request['request_id']:raise ValueError('Targets belong to another UE connection.')
        for point in data['targets']:
            transform=from_ue([point['transform']])[0]
            self.duplicate_target(self.selected_index)
            canonical=root_transform(self.entry.preview_pose.numpy(),np.asarray(self.entry.placement),inverse=True)
            offset=Rotation.from_quat(transform[3:]).apply([canonical[0,0],canonical[0,1],0.])
            transform[:3]-=offset
            self.entry.name=point['name'][:256]
            self.entry.placement=wp.transform(*transform);self.entry.euler_degrees=None
            self.entry.ue_target_id=point['id']
        self.changed('Imported UE target points.')

    def project_extras(self):
        data=dict(ue_clip_id=getattr(self,'ue_clip_id',None),ue_target_times=getattr(self,'ue_generated_target_times',{}))
        if hasattr(self,'environment'):data['environment']=self.environment
        if self.timeline_cpu is not None:
            data['generated_motion']=dict(fps=30,poses=self.timeline_cpu.tolist(),stale=self.timeline_stale)
        return data


def draw_live_menu(app,ui):
    for label,action in [('Connect UE / Start synchronization',app.connect_ue),
                         ('Disconnect UE',app.disconnect_ue),
                         ('Import UE target points',app.import_ue_targets),
                         ('Save completed motion to UE',app.bake_to_ue)]:
        if ui.menu_item(label,'',False,not app.busy)[0]:
            try:action()
            except Exception as exc:app.error=str(exc)
    ui.separator()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
