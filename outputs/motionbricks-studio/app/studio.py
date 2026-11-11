"""MotionBricks Studio Ti: official realtime viewer + pose authoring + UE FBX export."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import time
import traceback
from dataclasses import replace
import numpy as np
from scipy.spatial.transform import Rotation
import warp as wp

from .inbetweener_demo import InbetweenerDemo, PoseEntry, sample_pose_window
from .authoring.common import log_transform_gizmo, draw_transform_editor, draw_token_range_property, drag_source, accept_drop
from .runtime.common.rig import ASSETS_ROOT
from .utils.file_dialog import choose_file
from .utils.cli import create_gl_parser, configure_logging
from .utils.model_loading import require_tensorrt
from .studio_data import fk, root_transform, solve_ik, write_document, read_document, safe_name, retime_motion, mirror_pose, same_transform
from .studio_i18n import LocalizedUI, text, load_language, save_language, install_font
from .studio_locales import LANGUAGES
from .studio_settings import load_autosave_enabled,save_autosave_enabled
from .studio_camera import install_camera_controls
from .studio_export import export_fbx
from .studio_audio import AudioTransport
import shutil
import copy
from .studio_motion import MotionAuthoring
from .studio_scene import SceneAuthoring,draw_environment
from .studio_ue_pose import draw_ue_menu
from .studio_ue_live import UEBridge
from .studio_motion_data import conditioning_window,serialize_track,plays_entire_motion,sample_track
from .studio_library import LibraryGenres,label as library_label,keep_visible_selection,infer_genre,motion_name
from .studio_hand_pose import SUFFIX as HAND_POSE_SUFFIX,display_name as hand_pose_name,read_hand_pose
from motionbricks.animation.animation_buffer import AnimationBuffer
from motionbricks.model.contract import ModelRig
from motionbricks.model.config import MotionBricksInferenceConfig
from motionbricks.model.soma.contract import SOMA_N1_CONTRACT

ROOT = Path(__file__).resolve().parents[1]
USER = ROOT / 'user_data'
AUTOSAVE_INTERVAL_SECONDS = 15 * 60


class Studio(SceneAuthoring,UEBridge,MotionAuthoring,InbetweenerDemo):
    def _initial_clip(self,rig):
        # Startup must not depend on retired animation assets. This is the
        # model's static reference geometry, not an authored motion clip.
        pose=self.skeleton.reference_local_transforms.numpy()
        poses=np.repeat(pose[None],4,axis=0)
        return Path('static-soma-reference'),AnimationBuffer(self.skeleton,30,wp.array(poses,dtype=wp.transform,device=self.engine.device))

    def __init__(self, viewer, *, fp16=False):
        self.user_directory=USER
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='studio')
        self.language=load_language(USER/'settings.json')
        self.autosave_enabled=load_autosave_enabled(USER/'settings.json')
        from .studio_kimodo_link import KimodoLink
        self.kimodo_link=KimodoLink(USER)
        from .studio_external_panel import ExternalPanel
        self.external_panel=ExternalPanel()
        self.show_manual=False
        self.motion_editor_open=False
        self.motion_playing=False
        self.motion_frame=0.
        self.motion_entry_id=None
        self.show_licenses=False
        self.license_index=0
        self.manual_search=''
        self.job = None
        self.job_kind = ''
        self.pending = None
        self.status = 'Select a motion, choose a frame, then edit a bone.'
        self.dirty = False
        self.project_path = None
        self.library_filter = ''
        self.library_index = 0
        self.library_files = []
        self.library_genres=LibraryGenres(ROOT,USER/'library_categories.json')
        self.library_genre_name=''
        self.pose_name = 'My Pose'
        self.edit_bones = True
        self.tool = 0
        self.bone_index = 0
        self.bone_filter = ''
        self.undo_stack, self.redo_stack = [], []
        self.last_edit = 0.
        self.last_autosave = time.perf_counter()
        self._autosave_saved_revision = 0
        self.timeline = None
        self.timeline_stale = False
        self.timeline_cpu = None
        self.timeline_time = 0.
        self.preview_playing = False
        self.preview_loop = True
        self.preview_speed=1.
        self.audio=AudioTransport()
        self.audio_sync=True
        self.video_exporting=False
        self.video_audio=True
        self.vmd_target_path=None
        self.notice=None
        self.export_inplace = False
        self.export_mesh = True
        self.show_targets = True
        self.show_generated = True
        self.generation_seconds = 0.
        self._last_gizmo_change = False
        self.smoke_result = None
        self.init_scene()
        (USER/'poses').mkdir(parents=True, exist_ok=True)
        (USER/'exports').mkdir(exist_ok=True)
        super().__init__(viewer, ModelRig.SOMA, fp16=fp16)
        self.viewer.renderer.set_title('MotionBricks Studio Ti')
        self.model = self.mesh_renderer.skeletal_mesh
        # Display the actual saved finger transforms; previews must agree with exported motion.
        self.mesh_renderer.set_override_pose(None)
        self.bone_indices = [i for i,n in enumerate(self.skeleton.joint_names) if n in SOMA_N1_CONTRACT.joint_names]
        self.bone_index = self.skeleton.joint_index('LeftForeArm')
        if self.bone_index < 0:
            self.bone_index = 0
        self._scan_library()
        self._load_startup_walk()
        self.camera_home()
        # Warp's viewer synchronizes the device; CUDA graph capture cannot overlap it.
        # Capture once on the UI thread before starting any background generation.
        show_ui=viewer.show_ui
        viewer.show_ui=False
        try:
            viewer.show_loading_splash('Preparing motion generation...')
            viewer.begin_frame(0.)
            viewer.end_frame()
            self.generate_snapshot(self.generation_snapshot())
        finally:
            viewer.hide_loading_splash()
            viewer.show_ui=show_ui

    def _load_startup_walk(self):
        path=USER/'poses/Walk.motion.json'
        if not path.is_file():return
        try:
            item=read_document(path,self.skeleton,'motion')[0]
            entry=self.pose_entries[0]
            entry.path=path;entry.name='Walk';entry.manual_window=item['window'].copy()
            entry.motion_track=copy.deepcopy(item['motion_track'])
            entry.num_poses_to_use=item['num_poses']
            from .studio_motion_data import apply_library_playback_default
            apply_library_playback_default(entry.motion_track,'locomotion')
            self.refresh_poses()
        except Exception as exc:
            self.status='Walk startup could not load: '+str(exc)

    def _setup_viewer(self):
        super()._setup_viewer()
        if self.viewer.ui is None:return
        self._studio_font=install_font(self.viewer.ui.imgui)
        self.viewer.ui.imgui.get_io().font_default=self._studio_font['zh' if self.language=='zh' else 'default']
        install_camera_controls(self.viewer)

    def set_language(self,language):
        if language not in {code for _,code in LANGUAGES}: return
        self.language=language
        self.manual_search=''
        self.viewer.ui.imgui.get_io().font_default=self._studio_font['zh' if language=='zh' else 'default']
        save_language(USER/'settings.json',language)

    def duplicate_target(self,index):
        source=self.pose_entries[index]
        name=f'{source.name} {text("Copy",self.language)}'
        e=replace(source,id=self._next_id,name=name[:256],placement=wp.transform(source.placement),
                  color=(.25,.65,1.),translation_locks=list(source.translation_locks),
                  rotation_locks=list(source.rotation_locks),
                  euler_degrees=list(source.euler_degrees) if source.euler_degrees else None)
        window=getattr(source,'manual_window',None)
        e.manual_window=window.copy() if window is not None else None
        e.motion_track=copy.deepcopy(getattr(source,'motion_track',None))
        e.hold_frames=getattr(source,'hold_frames',0)
        e.duration_seconds=getattr(source,'duration_seconds',0.)
        e.ik_pin_mask=getattr(source,'ik_pin_mask',0)
        e.scene_generated=getattr(source,'scene_generated',False)
        e.scene_object_id=getattr(source,'scene_object_id','')
        self._next_id+=1
        self.pose_entries.insert(index+1,e)
        self.selected_index=index+1
        self.changed()
        return e

    def move_target(self,source,destination):
        if source==destination:return
        if not (0<=source<len(self.pose_entries) and 0<=destination<len(self.pose_entries)):return
        entry=self.pose_entries.pop(source)
        self.pose_entries.insert(destination,entry)
        self.selected_index=destination
        self.changed()

    def delete_library_pose(self):
        if not 0<=self.library_index<len(self.library_files):return
        path=self.library_files[self.library_index]
        if not path.name.endswith(('.pose.json','.motion.json')):return
        trash=USER/'deleted_poses'
        trash.mkdir(exist_ok=True)
        destination=trash/(str(time.time_ns())+'_'+path.name)
        shutil.move(str(path),str(destination))
        self._scan_library()
        self.status='Pose moved to deleted_poses: '+str(destination)

    def reset_bone_rotation(self):
        pose=self.entry.preview_pose.numpy().copy()
        reference=root_transform(self.skeleton.reference_local_transforms.numpy(),np.asarray(self.model_to_runtime))
        reference=root_transform(reference,np.asarray(self.entry.placement))
        pose[self.bone_index,3:]=reference[self.bone_index,3:]
        self.edit_pose(pose,continuous=False)

    @property
    def skeleton(self):
        return self.mesh_renderer.skeletal_mesh.skeleton

    @property
    def entry(self):
        return self.pose_entries[self.selected_index]

    @property
    def busy(self):
        return self.job is not None

    @property
    def dirty(self):
        return getattr(self,'_dirty',False)

    @dirty.setter
    def dirty(self,value):
        self._dirty=bool(value)
        if value:self._autosave_revision=getattr(self,'_autosave_revision',0)+1

    def set_autosave_enabled(self,enabled):
        save_autosave_enabled(USER/'settings.json',enabled)
        self.autosave_enabled=bool(enabled)
        # Enabling starts a fresh interval rather than blocking immediately.
        self.last_autosave=time.perf_counter()

    def _autosave_if_idle(self):
        # Large captured clips take seconds to compress. Never block the
        # playback clock with recovery serialization, including audio/editor playback.
        if not getattr(self,'autosave_enabled',True):return
        if not self.dirty or self.busy:return
        if self.preview_playing or self.audio.playing or getattr(self,'motion_playing',False):return
        revision=getattr(self,'_autosave_revision',0)
        if revision==getattr(self,'_autosave_saved_revision',-1):return
        if time.perf_counter()-self.last_autosave<AUTOSAVE_INTERVAL_SECONDS:return
        write_document(USER/'recovery.mbstudio.json','project',self.skeleton,self.serialize_entries(),extras=self.project_extras())
        self.last_autosave=time.perf_counter()
        self._autosave_saved_revision=revision

    def camera_home(self):
        from pyglet.math import Vec3
        self.viewer.camera.pos = Vec3(-4., -5.5, 2.8)
        self.viewer.camera.look_at(np.array([0., -.8, 1.], dtype=np.float32))

    def mirror_selected_pose(self):
        reference=root_transform(self.skeleton.reference_local_transforms.numpy(),np.asarray(self.model_to_runtime))
        pose=mirror_pose(self.entry.preview_pose.numpy(),reference,self.skeleton._np_parent_indices,
                         list(self.skeleton.joint_names))
        self.edit_pose(pose,continuous=False)

    @property
    def transport_duration(self):
        return self.audio.duration if self.audio.path else (self.timeline.duration if self.timeline is not None else 0.)

    @property
    def transport_position(self):
        return self.audio.position if self.audio.path else (self.timeline_time if self.timeline is not None else 0.)

    @property
    def transport_playing(self):
        return self.audio.playing if self.audio.path else self.preview_playing

    def seek_transport(self,seconds,pause=False):
        seconds=float(np.clip(seconds,0.,self.transport_duration))
        if self.audio.path:
            self.audio_sync=True
            if pause:self.audio.pause()
            self.audio.seek(seconds)
        if self.timeline is not None:
            self.timeline_time=min(seconds,self.timeline.duration)
            if pause:self.preview_playing=False
            self.timeline.sample(self.timeline_time,self.current_pose,stream=self.engine.stream)

    def toggle_transport(self):
        if self.audio.path:
            self.audio_sync=True
            if self.audio.playing:self.audio.pause()
            else:self.audio.play()
        elif self.timeline is not None:
            if not self.preview_playing and self.timeline_time>=self.timeline.duration:self.timeline_time=0.
            self.preview_playing=not self.preview_playing

    def stop_transport(self):
        self.audio.pause();self.preview_playing=False
        self.seek_transport(0.,pause=True)

    def _scan_library(self):
        previous=self.library_files[self.library_index] if 0<=self.library_index<len(self.library_files) else None
        self.library_files = sorted((ASSETS_ROOT/'motions'/'soma').rglob('*.bvh'))
        self.library_files += sorted((USER/'poses').glob('*.pose.json'))
        self.library_files += sorted((USER/'poses').glob('*.motion.json'))
        self.library_files += sorted((ASSETS_ROOT/'ti_original'/'hand_poses').glob('*'+HAND_POSE_SUFFIX))
        manifest=USER/'library.json'
        try:
            paths=json.loads(manifest.read_text(encoding='utf-8')) if manifest.is_file() else []
            if isinstance(paths,list):
                self.library_files += [Path(p) for p in paths if isinstance(p,str) and
                    p.lower().endswith(('.bvh','.pose.json','.motion.json',HAND_POSE_SUFFIX)) and Path(p).is_file()]
        except (OSError,ValueError):
            pass
        self.library_files=list(dict.fromkeys(self.library_files))
        self.library_index=self.library_files.index(previous) if previous in self.library_files else -1
        self._filter_library_selection()

    def _filter_library_selection(self):
        if not hasattr(self,'library_genres'):self.library_genres=LibraryGenres(ROOT,USER/'library_categories.json')
        indices=self.library_genres.filter(self.library_files,self.library_filter)
        self.library_index=keep_visible_selection(self.library_files,self.library_index,indices)
        return indices

    def _load_library_selection(self):
        visible=self._filter_library_selection()
        if self.library_index not in visible:return
        self.use_library_file(self.library_files[self.library_index])

    def canonical_window(self, entry):
        return root_transform(entry.sampled_poses.numpy(), np.asarray(entry.placement), inverse=True)

    def refresh_poses(self):
        for index, e in enumerate(self.pose_entries):
            anchor = 3 if index == 0 else 0
            window = getattr(e, 'manual_window', None)
            if getattr(e,'motion_track',None) is not None:
                if plays_entire_motion(e.motion_track):
                    window=np.stack([sample_track(e.motion_track,i) for i in range(4)])
                else:window=conditioning_window(e.motion_track,anchor)
                e.manual_window=window
            if window is None:
                e.sampled_poses = wp.empty_like(self.context.poses)
                sample_pose_window(e, self.model_to_runtime, e.sampled_poses, anchor=anchor)
            else:
                e.sampled_poses = wp.array(root_transform(window, np.asarray(e.placement)), dtype=wp.transform,
                                         device=self.engine.device)
            e.preview_pose = e.sampled_poses[anchor]
            if plays_entire_motion(getattr(e,'motion_track',None)):e.preview_pose=e.sampled_poses[0]
            roots = e.sampled_poses.numpy()[:,0,:3]
            e.root_position = roots[0 if plays_entire_motion(getattr(e,'motion_track',None)) else anchor]
            pair = roots[-2:] if index == 0 else roots[:2]
            e.velocity = (pair[1]-pair[0])*30
            if e.num_poses_to_use == 1:
                e.velocity[:] = 0
            e.hold_frames = getattr(e, 'hold_frames', 0)
            e.duration_seconds=getattr(e,'duration_seconds',0.)
        self._refresh_order_markers()
        self.reset()
        self.update_motion_preview()

    def changed(self, message=None):
        self.dirty = True
        self.timeline_stale = self.timeline is not None
        self.preview_playing = False
        if message:
            self.status = message
        self.refresh_poses()

    def remember(self, *, continuous=False):
        now = time.perf_counter()
        cursor=self.motion_cursor() if getattr(self.entry,'motion_track',None) is not None else None
        if not continuous or now-self.last_edit > .4 or not self.undo_stack or self.undo_stack[-1][0]!=self.entry.id or self.undo_stack[-1][5]!=cursor:
            self.undo_stack.append((self.entry.id, self.canonical_window(self.entry).copy(),
                                    self.entry.num_poses_to_use,np.asarray(self.entry.placement).copy(),
                                    copy.deepcopy(getattr(self.entry,'motion_track',None)),cursor))
            self.undo_stack = self.undo_stack[-80:]
            self.redo_stack.clear()
        self.last_edit = now

    def history(self, redo=False):
        source, dest = (self.redo_stack,self.undo_stack) if redo else (self.undo_stack,self.redo_stack)
        while source:
            ident, window, num, placement, track, cursor = source.pop()
            index = next((i for i,e in enumerate(self.pose_entries) if e.id==ident),None)
            if index is None:
                continue
            self.selected_index = index
            dest.append((ident,self.canonical_window(self.entry).copy(),self.entry.num_poses_to_use,
                         np.asarray(self.entry.placement).copy(),copy.deepcopy(getattr(self.entry,'motion_track',None)),
                         self.motion_cursor() if getattr(self.entry,'motion_track',None) is not None else None))
            self.entry.manual_window = window
            self.entry.num_poses_to_use = num
            self.entry.placement=wp.transform(*placement)
            self.entry.euler_degrees=None
            self.entry.motion_track=track
            if cursor is not None:self.motion_frame=float(cursor)
            self.changed('Redo' if redo else 'Undo')
            break

    def edit_pose(self, world_pose, *, continuous=True):
        if getattr(self.entry,'motion_track',None) is not None:
            self.edit_motion_pose(world_pose,continuous)
            return
        self.remember(continuous=continuous)
        canonical = root_transform(np.asarray(world_pose), np.asarray(self.entry.placement), inverse=True)
        self.entry.manual_window = np.repeat(canonical[None],4,axis=0)
        self.entry.num_poses_to_use = 1
        self.changed('Edited pose. Save Pose registers it in your library.')

    def _select_pose(self, origin, direction):
        if self.busy or (self.external_panel.open and self.external_panel.preview):return
        distance,box_index=self.pick_scene_box(origin,direction)
        if box_index is not None:
            # A visible character in front of a box keeps normal pose selection.
            nearest=float(self.viewer.camera.far)
            if self.show_targets:
                for entry in self.pose_entries:
                    if entry.show_mesh:nearest=min(nearest,self.mesh_renderer.raycast_pose(entry.preview_pose,wp.transform_identity(),origin,direction,nearest))
            if distance<nearest:
                self.select_scene_box(box_index)
                return
        self.scene_editing=False
        if self.edit_bones and not self.busy:
            world = fk(self.entry.preview_pose.numpy(), self.skeleton._np_parent_indices)
            o,d = np.asarray(origin),np.asarray(direction)
            best, joint = float('inf'),None
            for i in getattr(self,'bone_indices',[]):
                ray = np.dot(world[i,:3]-o,d)
                distance = np.linalg.norm(world[i,:3]-(o+ray*d))
                if ray > 0 and distance < .085 and ray < best:
                    best,joint = ray,i
            if joint is not None:
                self.bone_index = joint
                return
        super()._select_pose(origin,direction)

    def use_library_file(self, path, *, register=True, name=None):
        path = Path(path)
        if path.suffix.lower()=='.npz':
            from .studio_kimodo import save_import
            reference=root_transform(self.skeleton.reference_local_transforms.numpy(),np.asarray(self.model_to_runtime))
            path,_,_=save_import(path,self.skeleton,reference,USER/'poses',name=name)
            self._scan_library()
        if path.name.endswith(HAND_POSE_SUFFIX):
            indices,rotations=read_hand_pose(path,self.skeleton.joint_names)
            self.remember()
            track=getattr(self.entry,'motion_track',None)
            if track is None:
                window=self.canonical_window(self.entry).copy()
                window[:,indices,3:]=rotations
                self.entry.manual_window=window
            else:
                from .studio_motion_data import put_key
                cursor=self.motion_cursor()
                pose=sample_track(track,cursor).copy()
                pose[indices,3:]=rotations
                put_key(track,cursor,pose)
                self.motion_playing=False
        elif path.name.endswith(('.pose.json','.motion.json')):
            items = read_document(path,self.skeleton,'motion' if path.name.endswith('.motion.json') else 'pose')
            e = items[0]
            self.remember()
            # Preserve the authored file's provenance instead of inheriting the
            # previous target's sample-clip path when it is replaced.
            self.entry.path = Path(e.get('source') or path)
            self.entry.manual_window = e['window']
            self.entry.placement = wp.transform(*e['placement'])
            self.entry.num_poses_to_use = e['num_poses']
            self.entry.motion_track=copy.deepcopy(e.get('motion_track'))
            from .studio_motion_data import apply_library_playback_default
            apply_library_playback_default(self.entry.motion_track,infer_genre(path))
            self.entry.name = e['name']
            self.pose_name = e['name']
            if self.entry.motion_track is not None:self.open_motion_editor()
        else:
            from motionbricks.io.bvh import load_skeleton_from_bvh
            source_skeleton = load_skeleton_from_bvh(path)
            missing = set(SOMA_N1_CONTRACT.joint_names)-set(source_skeleton.joint_names)
            if missing:
                raise ValueError('BVH needs SOMA-compatible joint names. Missing: '+', '.join(sorted(missing)[:8]))
            self.remember()
            self.entry.path = path
            self.entry.clip = self.clip_registry.load(path).animation
            self.entry.sample_time = min(.5,self.entry.clip.duration)
            self.entry.manual_window = None
            self.entry.motion_track=None
            self.entry.num_poses_to_use = 4
            self.entry.name = path.stem[:55]
        self.changed('Loaded '+path.name)
        if register and path not in self.library_files:
            # Keep a reference to the selected file; never rewrite or move the source.
            external=[str(p.resolve()) for p in self.library_files if not p.is_relative_to(ASSETS_ROOT)
                      and not p.is_relative_to(USER/'poses')]
            external.append(str(path.resolve()))
            (USER/'library.json').write_text(json.dumps(list(dict.fromkeys(external)),ensure_ascii=False,indent=2),encoding='utf-8')
            self._scan_library()

    def serialize_entries(self, entries=None):
        return [dict(name=e.name.strip()[:256] or f'Pose {e.id}',window=self.canonical_window(e).tolist(),
                     placement=np.asarray(e.placement).tolist(),num_poses=e.num_poses_to_use,
                     min_tokens=e.min_tokens,max_tokens=e.max_tokens,
                     hold_frames=getattr(e,'hold_frames',0),duration_seconds=getattr(e,'duration_seconds',0.),source=str(e.path),
                     motion_track=serialize_track(getattr(e,'motion_track',None)),ue_target_id=getattr(e,'ue_target_id',str(e.id)),
                     ik_pin_mask=getattr(e,'ik_pin_mask',0),transition_early_by_frames=e.transition_early_by_frames,
                     scene_generated=getattr(e,'scene_generated',False),scene_object_id=getattr(e,'scene_object_id',''))
                for e in (self.pose_entries if entries is None else entries)]

    def save_pose(self, path):
        e = self.serialize_entries([self.entry])[0]
        if e['motion_track'] is not None:
            pose=root_transform(self.entry.preview_pose.numpy(),np.asarray(self.entry.placement),inverse=True)
            e['window']=np.repeat(pose[None],4,axis=0).tolist();e['num_poses']=1;e['motion_track']=None
        e['name'] = self.pose_name.strip()[:256] or e['name']
        write_document(path,'pose',self.skeleton,[e])
        self._scan_library()
        self.status = 'Saved pose: '+str(path)

    def save_project(self, path):
        write_document(path,'project',self.skeleton,self.serialize_entries(),extras=self.project_extras())
        self.project_path = Path(path)
        self.dirty = False
        self.status = 'Saved project: '+str(path)

    def load_project(self, path):
        data = read_document(path,self.skeleton,'project')
        from .studio_data import read_extras
        extras=read_extras(path);frames=None
        from .studio_scene_data import validate_scene
        environment=validate_scene(extras.get('environment',{}))
        motion=extras.get('generated_motion')
        if motion is not None:
            frames=np.asarray(motion['poses'],dtype=np.float32)
            if frames.ndim!=3 or frames.shape[1:]!=(self.skeleton.num_joints,7) or len(frames)<2 or motion.get('fps')!=30 or not np.isfinite(frames).all():
                raise ValueError('Invalid saved animation')
            if np.max(np.abs(np.linalg.norm(frames[:,:,3:],axis=-1)-1))>.001:raise ValueError('Invalid saved animation rotations')
        if getattr(self,'ue_live',False):self.disconnect_ue()
        self.ue_pose_request=None
        old = self.pose_entries[0]
        items = []
        for i,d in enumerate(data):
            e = PoseEntry(i,d['name'],Path(d.get('source') or old.path),old.clip,0.,wp.transform(*d['placement']))
            e.manual_window = d['window']
            e.motion_track=copy.deepcopy(d.get('motion_track'))
            e.num_poses_to_use = d['num_poses']
            e.min_tokens,e.max_tokens = d['min_tokens'],d['max_tokens']
            e.hold_frames = d['hold_frames']
            e.duration_seconds=d['duration_seconds']
            e.ue_target_id=d.get('ue_target_id',str(i))
            e.ik_pin_mask=d.get('ik_pin_mask',0);e.transition_early_by_frames=d.get('transition_early_by_frames',0)
            e.scene_generated=d.get('scene_generated',False);e.scene_object_id=d.get('scene_object_id','')
            if i==0: e.color=(.2,.9,.4)
            e.show_skeletons = False
            items.append(e)
        self.mesh_renderer.clear(self.viewer)
        self.skeleton_renderer.clear(self.viewer)
        self.pose_entries = items
        self.environment=environment;self.scene_plan_stale=bool(environment['boxes']);self.scene_editing=False
        self._next_id = len(items)
        self.selected_index = min(1,len(items)-1)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.motion_editor_open=False;self.motion_playing=False
        self.refresh_poses()
        self.project_path = Path(path)
        self.dirty = False
        self.timeline = self.timeline_cpu = None
        self.ue_clip_id=extras.get('ue_clip_id') or __import__('uuid').uuid4().hex
        self.ue_generated_target_times=extras.get('ue_target_times',{})
        if frames is not None:
            self.timeline_cpu=frames
            self.timeline=AnimationBuffer(self.skeleton,30,wp.array(frames,dtype=wp.transform,device=self.engine.device))
            self.timeline_time=0.;self.preview_playing=False;self.timeline_stale=bool(motion.get('stale',False))
            self.show_generated=True
        self.status = 'Opened project: '+str(path)

    def generation_snapshot(self):
        from .studio_scene_original import dense_track
        from .studio_interval import mode,payload,action_frames,settings
        result=[];route_tracks={}
        for e in self.pose_entries:
            track=getattr(e,'motion_track',None);exact=None
            if track is not None:track=dict(track,display_name=getattr(e,'name',''))
            if plays_entire_motion(track):
                exact=root_transform(dense_track(track),np.asarray(e.placement))
            action=bool(track and mode(track)=='action')
            if action:exact=root_transform(action_frames(track,getattr(self.skeleton,'joint_names',None)),np.asarray(e.placement))
            full=bool(track and track.get('playback')=='full_clip') or action
            window=exact[:4].copy() if exact is not None else e.sampled_poses.numpy().copy()
            route_target=bool(getattr(e,'scene_generated',False) and track is None)
            motion_spec=payload(track,getattr(self.skeleton,'joint_names',None))
            if motion_spec is None and route_target and getattr(e,'name','').startswith('Route / '):
                path=Path(getattr(e,'path',''))
                if path.is_file():
                    if path not in route_tracks:route_tracks[path]=read_document(path,self.skeleton,'motion')[0]['motion_track']
                    motion_spec=payload(route_tracks[path],getattr(self.skeleton,'joint_names',None))
            result.append((window,1 if full else e.num_poses_to_use,e.min_tokens,e.max_tokens,
                 getattr(e,'hold_frames',0),getattr(e,'duration_seconds',0.),getattr(e,'ik_pin_mask',0),e.transition_early_by_frames,exact,motion_spec,bool(track and settings(track)['stop']),route_target))
        return result

    def generate_snapshot(self, entries):
        """Only worker uses inference buffers; UI keeps displaying independent pose arrays."""
        started = time.perf_counter()
        with wp.ScopedDevice(self.engine.device),wp.ScopedStream(self.engine.stream):
            context = self.engine.create_input(self.skeleton)
            target = self.engine.create_input(self.skeleton)
            output = self.engine.create_output(self.skeleton)
            segments = [];target_times=[];offset=0
            self._worker_full_motion_spans=[]
            self._worker_interval_reports=[]
            initial=entries[0][8] if len(entries[0])>8 else None
            if initial is not None:
                frames=initial.copy();self._worker_full_motion_spans.append(dict(entry_index=0,start_frame=0,end_frame=len(frames)-1))
                if entries[0][4]:frames=np.concatenate([frames,np.repeat(frames[-1:],entries[0][4],axis=0)])
                segments.append(frames);offset=len(frames)-1
                context.update_from_poses(wp.array(frames[-4:],dtype=wp.transform),stream=self.engine.stream)
            else:context.update_from_poses(wp.array(entries[0][0],dtype=wp.transform),stream=self.engine.stream)
            context_frames=segments[-1][-4:].copy() if segments else entries[0][0].copy()
            active_interval=entries[0][9] if len(entries[0])>9 else None
            from motionbricks.runtime.target_pose import TargetPoseIKCorrector,create_soma_target_pose_ik_rig,IKPin
            ik=None
            for entry_index,item in enumerate(entries[1:],1):
                window,num,minimum,maximum,hold,duration=item[:6]
                pin_mask=int(item[6]) if len(item)>6 else 0
                early=int(item[7]) if len(item)>7 else 0
                if hold or (len(item)>10 and item[10]): num=1
                source_spec=active_interval
                dest_spec=item[9] if len(item)>9 else None
                route_target=bool(item[11]) if len(item)>11 else False
                if route_target and source_spec:dest_spec=source_spec
                if duration>0 and not (source_spec or dest_spec):
                    minimum=maximum=max(6,min(16,round((duration*30+7)/4)))
                def infer_interval(current,goal,count,seconds=None):
                    context.update_from_poses(wp.array(current,dtype=wp.transform),stream=self.engine.stream)
                    target.update_from_poses(wp.array(goal[:count],dtype=wp.transform),stream=self.engine.stream)
                    tokens=tuple(range(minimum,maximum+1)) if seconds is None else (max(6,min(16,round((seconds*30+6)/4))),)
                    self.engine.generate_animation(context,target,output,config=MotionBricksInferenceConfig(allowed_token_counts=tokens))
                    return output.poses[:output.num_frames].numpy().copy()
                from .studio_interval import generate_interval
                frames,interval_report=(generate_interval(infer_interval,context_frames,window,source_spec or dest_spec,
                    destination_spec=dest_spec,num=num,hold=hold,duration=duration,stop=bool(item[10]) if len(item)>10 else False) if source_spec or dest_spec else (None,None))
                if frames is None:frames=infer_interval(context_frames,window,num)
                else:self._worker_interval_reports.append(dict(entry_index=entry_index,**interval_report))
                if early and interval_report is None:frames=frames[:max(4,len(frames)-early)]
                if pin_mask:
                    if ik is None:ik=TargetPoseIKCorrector(self.skeleton,create_soma_target_pose_ik_rig(self.skeleton))
                    ik.capture_pins(wp.array(window[0],dtype=wp.transform),IKPin(pin_mask),self.engine.stream)
                    corrected=wp.array(frames,dtype=wp.transform)
                    for frame_index in range(len(frames)):
                        x=max(0.,min(1.,(frame_index/max(1,len(frames)-1)-.65)/.35))
                        ik.apply(corrected[frame_index],x*x*(3-2*x),self.engine.stream)
                    self.engine.synchronize();frames=corrected.numpy()
                if duration>0 and interval_report is None:
                    frames=retime_motion(frames,max(2,round(duration*30)+1))
                exact=item[8] if len(item)>8 else None
                if exact is not None:
                    from .studio_scene_original import blend_tail
                    first_frame=offset+len(frames)-1
                    self._worker_full_motion_spans.append(dict(entry_index=entry_index,start_frame=first_frame,end_frame=first_frame+len(exact)-1))
                    frames=np.concatenate([blend_tail(frames,exact[0]),exact[1:]])
                target_times.append((offset+len(frames)-1)/30)
                if hold:
                    frames = np.concatenate([frames,np.repeat(frames[-1:],hold,axis=0)])
                segments.append(frames if not segments else frames[1:])
                offset+=len(frames)-1
                context.update_from_poses(wp.array(frames[-4:],dtype=wp.transform),stream=self.engine.stream)
                context_frames=frames[-4:].copy()
                if dest_spec:active_interval=dest_spec
                elif not route_target and exact is None:active_interval=None
            self.engine.synchronize()
        if not segments:
            raise ValueError('Add at least one target pose.')
        self._ue_worker_target_times=target_times
        return np.concatenate(segments), time.perf_counter()-started

    def start_generation(self):
        if self.busy:
            return False
        try:
            if (getattr(self,'environment',{}).get('boxes') or getattr(self,'scene_plan_stale',False)) and (self.scene_plan_stale or self.scene_plan_signature!=self.scene_base_signature()):return self.start_environment_plan(generate=True)
            snapshot=self.generation_snapshot()
        except Exception as exc:
            # Expected layout errors must not escape the ImGui callback and
            # tear down the viewer. Keep the existing project and animation.
            self.preview_playing=False
            self.scene_window=bool(getattr(self,'environment',{}).get('boxes'))
            self.error=str(exc)
            return False
        self.motion_playing=False
        self.preview_playing = False
        self.job_kind = 'generate'
        self.ue_pending_target_ids=[getattr(e,'ue_target_id',str(e.id)) for e in self.pose_entries[1:]]
        self.ue_pending_target_names=[e.name for e in self.pose_entries[1:]]
        self.job = self.pool.submit(self.generate_snapshot,snapshot)
        self.status = 'Generating motion... You can still orbit the camera.'
        return True

    def export_payload(self):
        if self.timeline_cpu is None:
            raise ValueError('Generate an animation before exporting.')
        ref = self.skeleton.reference_local_transforms.numpy()
        conversion = np.asarray(self.model_to_runtime)
        ref = root_transform(ref,conversion)
        data = dict(joint_names=np.asarray(self.skeleton.joint_names),parents=self.skeleton._np_parent_indices,
                    reference=ref,poses=self.timeline_cpu.copy(),fps=np.asarray(30),
                    mesh_count=np.asarray(len(self.model.skinned_meshes)))
        rotation = Rotation.from_quat(conversion[3:])
        inverse_bind=self.model.inverse_bind_transforms.numpy()
        bind_rotation=Rotation.from_quat(inverse_bind[:,3:]).inv()
        bind_world=np.empty_like(inverse_bind)
        bind_world[:,:3]=rotation.apply(-bind_rotation.apply(inverse_bind[:,:3]))+conversion[:3]
        bind_world[:,3:]=(rotation*bind_rotation).as_quat()
        data['bind_world']=bind_world
        for k,m in enumerate(self.model.skinned_meshes):
            data[f'mesh_{k}_points'] = rotation.apply(m.points.numpy())+conversion[:3]
            data[f'mesh_{k}_triangles'] = m.indices.numpy().reshape(-1,3)
            data[f'mesh_{k}_joints'] = m.joint_indices.numpy().reshape(-1,m.num_influences)
            data[f'mesh_{k}_weights'] = m.joint_weights.numpy().reshape(-1,m.num_influences)
        return data

    def _dispatch(self):
        action,self.pending = self.pending,None
        if not action:
            return
        try:
            def dialog(title,label,*args,**kwargs):
                return choose_file(text(title,self.language),text(label,self.language),*args,**kwargs)
            if action=='configure_ue_project':
                path=dialog('Set up UE project connection...','Unreal Engine project','.uproject')
                if path:
                    self.configure_ue_project(path)
                    self.status=text('UE project configured. Start synchronization in Studio, then connect the character in UE.',self.language)
            elif action=='install_ue_bridge':
                path=dialog('Install UE Bridge...','Unreal Engine project','.uproject')
                if path:
                    from ue.install_bridge import install
                    self.status='UE Bridge installed. Restart the selected UE project. '+str(install(path))
            elif action=='scene_preset':
                import tkinter as tk
                from tkinter import filedialog
                root=tk.Tk();root.withdraw()
                try:path=filedialog.askopenfilename(title=text('Load custom interaction preset',self.language),
                    filetypes=[('Studio motion / SOMA Smart Primitive','*.motion.json *.smart_primitive.json')],initialdir=str(self.user_directory/'poses'))
                finally:root.destroy()
                if path:
                    if path.endswith('.motion.json'):
                        track=read_document(path,self.skeleton,'motion')[0]['motion_track']
                        if track.get('import_adjustment',{}).get('purpose')!='transit':
                            raise ValueError('Select a motion prepared for obstacle passage / 「障害物を通過する動作」として登録した素材を選択してください。')
                    else:
                        from .runtime.common.io.smart_primitive_document import load_smart_primitive_rig
                        if load_smart_primitive_rig(path)!=ModelRig.SOMA:raise ValueError('Select a SOMA Smart Primitive')
                    self.environment['boxes'][self.scene_selected]['asset']=str(Path(path).resolve());self.scene_changed()
            elif action=='external_file':
                import tkinter as tk
                from tkinter import filedialog
                from .studio_external_panel import label
                root=tk.Tk();root.withdraw()
                try:path=filedialog.askopenfilename(title=label('file',self.language),filetypes=[('NPZ / FBX / BVH','*.npz *.fbx *.bvh')])
                finally:root.destroy()
                if path:
                    reference=root_transform(self.skeleton.reference_local_transforms.numpy(),np.asarray(self.model_to_runtime))
                    self.external_panel.choose(path,self.skeleton,reference)
            elif action in ('external_profile_save','external_profile_load'):
                from .studio_external_panel import label
                save=action.endswith('save')
                path=choose_file(label('profile_save' if save else 'profile_load',self.language),'Bone mapping','.json',save=save)
                if path:
                    if save:self.external_panel.save_mapping(path)
                    else:self.external_panel.load_mapping(path)
            elif action=='kimodo_folder':
                import tkinter as tk
                from tkinter import filedialog
                from .studio_kimodo_link import label
                root=tk.Tk();root.withdraw()
                try:path=filedialog.askdirectory(title=label('folder',self.language),initialdir=str(self.kimodo_link.root.parent))
                finally:root.destroy()
                if path:self.kimodo_link.choose_root(path);self.kimodo_link.check()
            elif action in ('import','kimodo_import'):
                import tkinter as tk
                from tkinter import filedialog
                root=tk.Tk();root.withdraw()
                options=(dict(filetypes=[('Kimodo SOMA77 NPZ','*.npz')],initialdir=str(self.kimodo_link.results)) if action=='kimodo_import' else dict(filetypes=[('NPZ / FBX / BVH','*.npz *.fbx *.bvh')]))
                try:path=filedialog.askopenfilename(title=text('Import SOMA motion',self.language),**options)
                finally:root.destroy()
                if path:
                    reference=root_transform(self.skeleton.reference_local_transforms.numpy(),np.asarray(self.model_to_runtime))
                    self.external_panel.choose(path,self.skeleton,reference)
            elif action=='audio':
                import tkinter as tk
                from tkinter import filedialog
                root=tk.Tk();root.withdraw()
                try:
                    path=filedialog.askopenfilename(title=text('Load Music...',self.language),
                        filetypes=[('MP3 / WAV','*.mp3 *.wav')])
                finally:root.destroy()
                if path:
                    self.audio.load(path)
                    self.audio_sync=True
            elif action=='delete_pose':
                self.delete_library_pose()
            elif action=='load_pose':
                import tkinter as tk
                from tkinter import filedialog
                root=tk.Tk();root.withdraw()
                try:path=filedialog.askopenfilename(title=text('Load Pose...',self.language),filetypes=[('Studio / Kimodo NPZ','*.pose.json *.handpose.json *.motion.json *.npz'),('Kimodo motion','*.npz')])
                finally:root.destroy()
                if path:
                    if Path(path).suffix.lower()=='.npz':
                        reference=root_transform(self.skeleton.reference_local_transforms.numpy(),np.asarray(self.model_to_runtime))
                        self.external_panel.choose(path,self.skeleton,reference)
                    else:self.use_library_file(path)
            elif action=='save_motion':
                path=dialog('Save Motion As...','Studio motion','.motion.json',USER/'poses'/(safe_name(self.pose_name)+'.motion.json'),save=True)
                if path:self.save_authored_motion(path)
            elif action=='save_pose':
                path = dialog('Save New Pose','Studio poses','.pose.json',
                                   USER/'poses'/(safe_name(self.pose_name)+'.pose.json'),save=True)
                if path:
                    self.save_pose(path)
            elif action=='save_project':
                path = self.project_path or dialog('Save Project','Studio projects','.mbstudio.json',
                                                        USER/'Project.mbstudio.json',save=True)
                if path:
                    self.save_project(path)
            elif action=='save_project_as':
                path = dialog('Save Project As','Studio projects','.mbstudio.json',
                                   self.project_path or USER/'Project.mbstudio.json',save=True)
                if path:
                    self.save_project(path)
            elif action in ('load_project','recover'):
                path = USER/'recovery.mbstudio.json' if action=='recover' else dialog(
                    'Open Project','Studio projects','.mbstudio.json',USER/'Project.mbstudio.json')
                if path:
                    self.load_project(path)
                    if action=='recover':
                        self.project_path = None
                        self.dirty = True
            elif action=='video':
                path=dialog('Export Reference MP4','MP4 video','.mp4',USER/'exports'/'Reference.mp4',save=True)
                if path:
                    from .studio_video import export_video
                    self.status='Exported: '+export_video(self,path,self.video_audio)
            elif action=='vmd_model':
                import tkinter as tk
                from tkinter import filedialog
                root=tk.Tk();root.withdraw()
                try:
                    path=filedialog.askopenfilename(title=text('Choose MMD target model',self.language),
                        filetypes=[(text('PMX or PMD model',self.language),'*.pmx *.pmd'),
                                   ('PMX','*.pmx'),('PMD','*.pmd')])
                finally:root.destroy()
                if path:
                    from .studio_vmd import validate_mmd_target
                    from .studio_ui_refresh import caption
                    try:
                        validate_mmd_target(path,list(self.skeleton.joint_names))
                    except Exception as exc:
                        self.vmd_target_path=None
                        self.notice=None
                        self.error=caption('mmd_failed',self.language)+'\n\n'+str(exc)
                    else:
                        self.error=None
                        self.vmd_target_path=Path(path)
                        self.notice=caption('mmd_ready',self.language)+'\n'+Path(path).name
            elif action=='vmd':
                path=dialog('Export MMD VMD','VMD motion','.vmd',USER/'exports'/'Motion.vmd',save=True)
                if path:
                    from .studio_vmd import export_vmd
                    self.job_kind='export'
                    self.job=self.pool.submit(export_vmd,self.export_payload(),path,self.vmd_target_path,self.export_inplace)
                    self.status='Exporting VMD...'
            elif action=='export':
                path = dialog('Export FBX','FBX animation','.fbx',
                                   USER/'exports'/'Motion.fbx',save=True)
                if path:
                    payload = self.export_payload()
                    self.job_kind = 'export'
                    self.job = self.pool.submit(export_fbx,payload,path,
                                                inplace=self.export_inplace,include_mesh=self.export_mesh)
                    self.status = 'Exporting FBX in the background...'
        except Exception as exc:
            self.error = str(exc)

    def _poll_job(self):
        if self.job is None or not self.job.done():
            return
        future,self.job = self.job,None
        try:
            result = future.result()
            if self.job_kind=='scene_plan':
                from .studio_scene_plan import apply
                apply(self,result)
            elif self.job_kind=='generate':
                self.timeline_cpu,self.generation_seconds = result
                self.dirty=True
                self.ue_generated_target_times=dict(zip(getattr(self,'ue_pending_target_ids',[]),getattr(self,'_ue_worker_target_times',[])))
                names=getattr(self,'ue_pending_target_names',[])
                self.ue_generated_target_times.update({name:value for name,value in zip(names,getattr(self,'_ue_worker_target_times',[])) if names.count(name)==1})
                self.ue_revision=__import__('uuid').uuid4().hex
                self.timeline = AnimationBuffer(self.skeleton,30,
                    wp.array(self.timeline_cpu,dtype=wp.transform,device=self.engine.device))
                self.timeline_time = 0
                self.preview_playing = True
                self.timeline_stale = False
                self.show_generated = True
                self.status = f'{len(self.timeline_cpu)} frames generated in {self.generation_seconds:.2f} s'
            else:
                self.status = 'Exported: '+result
        except Exception as exc:
            if self.job_kind=='scene_plan':self.scene_window=True;self.preview_playing=False
            traceback.print_exc()
            self.error = str(exc)

    def step(self, delta_time):
        self._dispatch()
        self._poll_job()
        from .studio_external_panel import poll_external
        poll_external(self)
        self.external_panel.advance(delta_time)
        self.step_motion_editor(delta_time)
        if self.timeline is not None and self.preview_playing:
            self.timeline_time += delta_time*self.preview_speed
            if self.timeline_time > self.timeline.duration:
                if self.preview_loop:
                    self.timeline_time %= max(self.timeline.duration,.001)
                else:
                    self.timeline_time = self.timeline.duration
                    self.preview_playing = False
        if self.timeline is not None:
            if self.audio.path and self.audio_sync:
                self.timeline_time=min(self.audio.position,self.timeline.duration)
                self.preview_playing=False
            self.timeline.sample(self.timeline_time,self.current_pose,stream=self.engine.stream)
        self._autosave_if_idle()
        self.step_ue_bridge()
        self.poll_scene_objects()

    def _panel(self,ui,title,pos,size):
        ui.set_next_window_pos(ui.ImVec2(*pos),ui.Cond_.always)
        ui.set_next_window_size(ui.ImVec2(*size),ui.Cond_.always)
        return ui.begin(title+'###Ti19'+title,flags=ui.WindowFlags_.no_move|ui.WindowFlags_.no_resize)[0]

    def _draw_pose_list(self,ui):
        move=None
        copy_index=None
        ui.begin_child('pose_list',ui.ImVec2(0,160),child_flags=ui.ChildFlags_.borders)
        try:
            for index,entry in enumerate(self.pose_entries):
                if self._rename.item_id==entry.id:
                    if name:=self._rename.draw(ui): entry.name=name;self.dirty=True
                    continue
                if ui.selectable(f'{entry.name}###pose_{entry.id}',self.selected_index==index)[0]:
                    self.selected_index=index;self.scene_editing=False
                row_min,row_max=ui.get_item_rect_min(),ui.get_item_rect_max()
                if ui.is_item_hovered() and ui.is_mouse_double_clicked(0):
                    self.selected_index=index;self._rename.begin(entry.id,entry.name)
                if ui.begin_popup_context_item(f'pose_context_{entry.id}'):
                    try:
                        self.selected_index=index
                        if ui.menu_item('Copy and Add','',False,not self.busy)[0]: copy_index=index
                    finally: ui.end_popup()
                if not self.busy:
                    drag_source(ui,'INBETWEENER_POSE',entry.id,entry.name)
                    dropped=accept_drop(ui,'INBETWEENER_POSE')
                    if dropped is not None:
                        source=next(i for i,e in enumerate(self.pose_entries) if e.id==dropped)
                        insertion=index+int(ui.get_mouse_pos().y>(row_min.y+row_max.y)/2)
                        move=(source,insertion-int(source<insertion))
        finally: ui.end_child()
        if move is not None: self.move_target(*move);self.dirty=True;self.timeline_stale=self.timeline is not None
        if copy_index is not None: self.duplicate_target(copy_index)

    def _draw_main_menu(self,ui):
        if ui.begin_main_menu_bar():
            if ui.begin_menu('Project'):
                for label,action in [('Open...','load_project'),('Save','save_project'),
                                     ('Save As...','save_project_as'),('Recover Autosave','recover')]:
                    if ui.menu_item(label,'',False,not self.busy)[0]:
                        self.pending=action
                clicked,enabled=ui.menu_item('Autosave (every 15 minutes)','',self.autosave_enabled)
                if clicked:
                    try:self.set_autosave_enabled(enabled)
                    except Exception as exc:self.error=str(exc)
                ui.end_menu()
            if ui.begin_menu('Environment'):
                if ui.menu_item('Environment & Interactions','',False,not self.busy)[0]:self.scene_window=True
                ui.end_menu()
            if ui.begin_menu('View'):
                if ui.menu_item('Frame character','',False)[0]: self.camera_home()
                _,self._viewer_ui.show_options = ui.menu_item('Viewer options','',self._viewer_ui.show_options)
                ui.end_menu()
            if ui.begin_menu('Import'):
                from .studio_external_panel import label
                if ui.menu_item(label('title',self.language)+'...', '',False)[0]:self.external_panel.open=True
                ui.end_menu()
            from .studio_ui_refresh import draw_export_menu
            draw_export_menu(self,ui)
            draw_ue_menu(self,ui)
            if ui.begin_menu('Kimodo'):
                from .studio_kimodo_link import label
                if ui.menu_item(label('title',self.language)+'...', '',False)[0]:self.kimodo_link.open=True
                ui.end_menu()
            if ui.begin_menu('Languages / 言語'):
                for label,language in LANGUAGES:
                    if ui.menu_item(label,'',self.language==language)[0]: self.set_language(language)
                ui.end_menu()
            if ui.begin_menu('Help'):
                if ui.menu_item('User Guide','',False)[0]:self.show_manual=True
                from .studio_licenses import LABELS
                if ui.menu_item(LABELS[self.language][0]+'###licenses_menu','',False)[0]:self.show_licenses=True
                ui.end_menu()
            ui.text_unformatted('  MotionBricks Studio Ti'+('  * unsaved' if self.dirty else ''))
            ui.end_main_menu_bar()

    def _draw_new_library_genre(self,ui):
        lang=self.language
        popup=library_label('new',lang)+'###create_library_genre'
        if ui.button(popup):
            self.library_genre_name=''
            ui.open_popup(popup)
        if not ui.begin_popup_modal(popup,flags=ui.WindowFlags_.always_auto_resize)[0]:return
        try:
            if ui.is_window_appearing():ui.set_keyboard_focus_here()
            submitted,self.library_genre_name=ui.input_text(library_label('name',lang),self.library_genre_name,
                flags=ui.InputTextFlags_.enter_returns_true)
            error=self.library_genres.name_error(self.library_genre_name)
            if self.library_genre_name and error:ui.text_wrapped(library_label(error,lang))
            ui.begin_disabled(error is not None)
            clicked=ui.button(library_label('create',lang))
            ui.end_disabled()
            if (submitted or clicked) and error is None:
                try:self.library_genres.create(self.library_genre_name)
                except OSError as exc:self.error=str(exc)
                ui.close_current_popup()
            ui.same_line()
            if ui.button(library_label('cancel',lang)):ui.close_current_popup()
        finally:ui.end_popup()

    def _draw_delete_library_genre(self,ui):
        genres=self.library_genres
        ident=genres.active
        if ident not in genres.custom:return
        lang=self.language
        popup=library_label('delete_genre',lang)+'###delete_library_genre'
        if ui.button(popup):ui.open_popup(popup)
        if not ui.begin_popup_modal(popup,flags=ui.WindowFlags_.always_auto_resize)[0]:return
        try:
            ui.push_text_wrap_pos(ui.get_cursor_pos_x()+420)
            ui.text_unformatted(library_label('confirm_delete',lang).format(name=genres.custom[ident]))
            ui.pop_text_wrap_pos()
            if ui.button(library_label('delete',lang)):
                try:genres.remove(ident)
                except OSError as exc:self.error=str(exc)
                ui.close_current_popup()
            ui.same_line()
            if ui.button(library_label('cancel',lang)):ui.close_current_popup()
        finally:ui.end_popup()

    def gui(self,ui):
        ui=LocalizedUI(ui,self.language)
        v = ui.get_main_viewport()
        scale = max(1.,ui.get_font_size()/13.)
        self._draw_main_menu(ui)
        io = ui.get_io()
        if io.key_ctrl and not io.want_text_input and not self.busy:
            if ui.is_key_pressed(ui.Key.z,False): self.history(redo=io.key_shift)
            if ui.is_key_pressed(ui.Key.y,False): self.history(redo=True)
            if ui.is_key_pressed(ui.Key.s,False): self.pending='save_project'
        from .studio_ui_refresh import panel_layout
        left,right,top,timeline_height=panel_layout(v.size.x,v.size.y,scale)
        if self._panel(ui,'Motion & Pose Library',(v.pos.x+10,v.pos.y+top),(left,v.size.y-top-12)):
            _,self.library_filter=ui.input_text('Search',self.library_filter)
            genres=self.library_genres;ids=genres.ids;counts=genres.counts(self.library_files);choices=('all',*ids)
            captions=[genres.caption(c,self.language)+f' ({len(self.library_files) if c=="all" else counts[c]})' for c in choices]
            ui.text_unformatted(library_label('genre',self.language))
            ui.set_next_item_width(-1)
            changed,index=ui.ui.combo('##library_genre',choices.index(genres.active),captions)
            if changed:
                previous=genres.active
                genres.active=choices[index]
                try:genres.save()
                except OSError as exc:genres.active=previous;self.error=str(exc)
            ui.begin_disabled(self.busy)
            self._draw_new_library_genre(ui)
            self._draw_delete_library_genre(ui)
            ui.end_disabled()
            ids=genres.ids
            visible_indices=self._filter_library_selection()
            ui.begin_disabled(self.busy)
            if self.library_index in visible_indices:
                selected=self.library_files[self.library_index];key=genres.key(selected);override=genres.overrides.get(key)
                current=ids.index(override)+1 if override in ids else 0
                options=[library_label('auto',self.language)+' / '+library_label(infer_genre(selected),self.language)]+[genres.caption(c,self.language) for c in ids]
                ui.text_unformatted(library_label('assign',self.language))
                ui.set_next_item_width(-1)
                changed,category=ui.ui.combo('##library_assign',current,options)
                if changed:
                    try:
                        genres.assign(selected,None if category==0 else ids[category-1])
                        visible_indices=self._filter_library_selection()
                    except OSError as exc:self.error=str(exc)
            if ui.button('Import Motion...'): self.pending='import'
            from .studio_ui_refresh import same_line_if_fits
            same_line_if_fits(ui,'Load Pose...',self.language)
            if ui.button('Load Pose...'): self.pending='load_pose'
            if ui.button('Refresh Library'): self._scan_library()
            can_delete=bool(self.library_index in visible_indices and self.library_files[self.library_index].name.endswith(('.pose.json','.motion.json')))
            ui.begin_disabled(not can_delete)
            same_line_if_fits(ui,'Delete Saved Pose',self.language)
            if ui.button('Delete Saved Pose'):self.pending='delete_pose'
            if ui.is_item_hovered():ui.set_tooltip('Moves the saved pose to deleted_poses. Targets keep their copied data.')
            ui.end_disabled()
            ui.text_wrapped('Double-click a motion to load it into the selected target.')
            ui.begin_child('library_items',ui.ImVec2(0,350*scale),child_flags=ui.ChildFlags_.borders)
            if not visible_indices:ui.text_wrapped(library_label('empty',self.language))
            for i in visible_indices:
                path=self.library_files[i]
                if path.name.endswith(HAND_POSE_SUFFIX):
                    label=hand_pose_name(path,self.language)
                else:
                    label=('[POSE] ' if path.name.endswith('.pose.json') else '[MOTION] ')+motion_name(path)
                clicked,_=ui.selectable(label+f'##lib{i}',self.library_index==i)
                if ui.is_item_hovered(): ui.set_tooltip(str(path))
                if clicked: self.library_index=i
                if ui.is_item_hovered() and ui.is_mouse_double_clicked(0):
                    try: self.use_library_file(path)
                    except Exception as exc: self.error=str(exc)
            ui.end_child()
            ui.begin_disabled(not visible_indices)
            if ui.button('Load Selected into Target'):
                try: self._load_library_selection()
                except Exception as exc: self.error=str(exc)
            ui.end_disabled()
            if ui.button('New Motion (Rest Pose)'):self.new_authored_motion()
            if ui.button('Motion from Current Pose'):self.new_authored_motion(from_current=True)
            if getattr(self.entry,'motion_track',None) is not None:
                if ui.button('Edit Motion'):self.open_motion_editor()
            e=self.entry
            if getattr(e,'manual_window',None) is None:
                changed,t=ui.slider_float('Source frame (s)',e.sample_time,0.,max(.001,e.clip.duration),'%.3f')
                if changed:
                    e.sample_time=t
                    self.changed()
                if ui.button('Extract Frame as Editable Pose'):
                    self.edit_pose(e.preview_pose.numpy(),continuous=False)
            else:
                ui.text_unformatted('Independent pose / saved motion window')
            _,self.pose_name=ui.input_text('Pose name',self.pose_name)
            if ui.button('Save Pose As...'): self.pending='save_pose'
            ui.end_disabled()
            ui.separator()
            ui.text_wrapped('Orbit: right drag. Pan XY: middle drag. Zoom: wheel. Left click selects a joint.')
        ui.end()
        if self._panel(ui,'Targets & Bone Editor',(v.pos.x+v.size.x-right-10,v.pos.y+top),
                       (right,v.size.y-top-12)):
            ui.begin_disabled(self.busy)
            self._draw_pose_list(ui)
            ui.text_wrapped('Drag a pose row to reorder. The first row is the start pose.')
            if ui.button('+ Add Target'):
                source=self.entry
                window=self.canonical_window(source) if getattr(source,'manual_window',None) is not None else None
                hold=getattr(source,'hold_frames',0)
                duration=getattr(source,'duration_seconds',0.)
                self.add_target()
                if window is not None:
                    self.entry.manual_window=window
                    self.entry.num_poses_to_use=source.num_poses_to_use
                self.entry.hold_frames=hold
                self.entry.duration_seconds=duration
                self.entry.motion_track=copy.deepcopy(getattr(source,'motion_track',None))
                self.changed()
            ui.same_line()
            ui.begin_disabled(self.selected_index==0)
            if ui.button('Remove'):
                self.remove_target();self.dirty=True
            ui.end_disabled()
            e=self.entry
            renamed,e.name=ui.input_text('Name',e.name)
            if renamed: self.dirty=True
            self.draw_entire_motion_control(ui)
            from .studio_interval import draw_controls
            draw_controls(self,ui)
            c,self.edit_bones=ui.checkbox('Edit Bones',self.edit_bones)
            if c:self.scene_editing=False
            ui.same_line()
            if ui.button('Undo'): self.history()
            ui.same_line()
            if ui.button('Redo'): self.history(redo=True)
            if ui.button('Mirror Pose'):self.mirror_selected_pose()
            if ui.is_item_hovered():ui.set_tooltip('Swap left and right, preserving position and facing. Undo is available.')
            if ui.collapsing_header('Placement',flags=ui.TreeNodeFlags_.default_open):
                changed,transform,e.euler_degrees=draw_transform_editor(
                    ui,e.placement,e.euler_degrees,min(scale,max(.55,ui.get_content_region_avail().x/440)),[False,False,False],[False,False,False])
                if changed:
                    self.scene_editing=False;self.remember(continuous=True);e.placement=transform;self.changed()
            if self.edit_bones:
                _,self.tool=ui.combo('Tool',self.tool,['Rotate Bone (FK)','Move Joint (IK)'])
                _,self.bone_filter=ui.input_text('Find bone',self.bone_filter)
                ui.begin_child('bones',ui.ImVec2(0,135*scale),child_flags=ui.ChildFlags_.borders)
                for i in self.bone_indices:
                    name=self.skeleton.joint_names[i]
                    if self.bone_filter.lower() not in (name+' '+text(name,self.language)).lower(): continue
                    if ui.selectable(name,self.bone_index==i)[0]: self.bone_index=i;self.scene_editing=False
                ui.end_child()
                pose=e.preview_pose.numpy()
                angles=Rotation.from_quat(pose[self.bone_index,3:]).as_euler('xyz',degrees=True)
                changed,angles=ui.drag_float3('Local rotation',angles.tolist(),.35,-180.,180.,'%.1f')
                if changed:
                    pose[self.bone_index,3:]=Rotation.from_euler('xyz',angles,degrees=True).as_quat()
                    self.edit_pose(pose)
                if ui.button('Reset Bone'): self.reset_bone_rotation()
                if ui.is_item_hovered(): ui.set_tooltip('Restore only this bone rotation to the skeleton rest pose. Undo is available.')
                if self.tool==1: ui.text_wrapped('Drag the joint gizmo. IK preserves bone lengths; best on hands / feet.')
            if ui.collapsing_header('Generation Settings'):
                minimum,maximum=draw_token_range_property(ui,e.min_tokens,e.max_tokens,e.id)
                if (minimum,maximum)!=(e.min_tokens,e.max_tokens):
                    e.min_tokens,e.max_tokens=minimum,maximum;self.dirty=True;self.timeline_stale=self.timeline is not None
                ui.begin_disabled(plays_entire_motion(getattr(e,'motion_track',None)))
                changed,num=ui.slider_int('Target poses',e.num_poses_to_use,1,4)
                if changed: e.num_poses_to_use=num;self.changed()
                ui.end_disabled()
                changed,hold=ui.slider_int('Hold frames',e.hold_frames,0,150)
                if changed: e.hold_frames=hold;self.dirty=True;self.timeline_stale=self.timeline is not None
                ui.begin_disabled(self.selected_index==0)
                changed,duration=ui.input_float('Transition duration (s)',e.duration_seconds,.1,.5,'%.2f')
                if changed:
                    if np.isfinite(duration): e.duration_seconds=max(0.,min(60.,float(duration)))
                    self.dirty=True;self.timeline_stale=self.timeline is not None
                ui.text_wrapped('0 = automatic. Duration is baked into the generated motion and FBX.')
                ui.text_wrapped('Large duration changes can cause foot sliding or slow-motion movement.')
                ui.end_disabled()
            ui.begin_disabled(not self.can_generate_motion())
            if ui.button('Generate Motion',ui.ImVec2(-1,32*scale)): self.start_generation()
            ui.end_disabled()
            ui.end_disabled()
            if self.timeline is not None:
                ui.separator()
                playing=self.audio.playing if self.audio.path and self.audio_sync else self.preview_playing
                if ui.button('Pause' if playing else 'Play'):
                    self.toggle_transport()
                ui.same_line()
                ui.begin_disabled(bool(self.audio.path and self.audio_sync))
                _,self.preview_loop=ui.checkbox('Loop',self.preview_loop)
                _,self.preview_speed=ui.slider_float('Preview speed',self.preview_speed,.1,3.,'%.2f x')
                if ui.is_item_hovered(): ui.set_tooltip('Preview speed does not change FBX duration.')
                ui.end_disabled()
                _,self.show_targets=ui.checkbox('Show target poses',self.show_targets)
                _,self.show_generated=ui.checkbox('Show generated motion',self.show_generated)
                changed,t=ui.slider_float('Time',self.transport_position,0.,max(.001,self.transport_duration),'%.3f s')
                if changed:
                    self.seek_transport(t,pause=True)
                ui.text_unformatted(f'{self.timeline.num_frames} frames | 30 fps')
                if self.timeline_stale: ui.text_wrapped('Targets changed. Generate again to update this preview.')
                ui.begin_disabled(self.busy)
                if ui.button('Capture Playback as New Target'):
                    pose=self.current_pose.numpy().copy()
                    self.add_target()
                    self.entry.placement=wp.transform_identity()
                    self.edit_pose(pose,continuous=False)
                ui.end_disabled()
            ui.separator()
            ui.text_wrapped(self.status)
            if self.busy: ui.text_unformatted('Working...')
        ui.end()
        if self._panel(ui,'Playback Timeline',(v.pos.x+left+20,v.pos.y+v.size.y-timeline_height-12),
                       (max(300,v.size.x-left-right-40),timeline_height)):
            if ui.button('Load Music...'):self.pending='audio'
            ui.same_line()
            ui.text_unformatted(self.audio.path.name if self.audio.path else 'Motion duration')
            ui.begin_disabled(self.transport_duration<=0.)
            if ui.button('Pause' if self.transport_playing else 'Play'):
                try:self.toggle_transport()
                except Exception as exc:self.error=str(exc)
            ui.same_line()
            if ui.button('Stop'):self.stop_transport()
            changed,t=ui.slider_float('Playback Time',self.transport_position,0.,max(.001,self.transport_duration),'%.2f s')
            if changed:self.seek_transport(t)
            ui.text_unformatted(f'{self.transport_position:.2f} / {self.transport_duration:.2f} s')
            ui.end_disabled()
            if self.transport_duration<=0.:ui.text_wrapped('Generate motion or load music to use the timeline.')
        ui.end()
        if self.show_manual:
            from .studio_manual import draw_manual
            draw_manual(self,ui)
        draw_environment(self,ui)
        from .studio_kimodo_link import draw_connection
        draw_connection(self,ui)
        from .studio_external_panel import draw_external
        draw_external(self,ui)
        if self.motion_editor_open:
            from .studio_motion import draw_motion_editor
            draw_motion_editor(self,ui)
        if self.show_licenses:
            from .studio_licenses import draw_licenses
            draw_licenses(self,ui)
        if self.notice:
            from .studio_ui_refresh import caption
            title=caption('notice',self.language)+'###studio_notice'
            ui.open_popup(title)
            ui.set_next_window_size(ui.ImVec2(min(640.,v.size.x-40),0.),ui.Cond_.always)
            if ui.begin_popup_modal(title,flags=ui.WindowFlags_.always_auto_resize)[0]:
                position=ui.get_window_pos();size=ui.get_window_size();self._notice_ui_bounds=(position.x,position.y,size.x,size.y)
                ui.text_wrapped(self.notice)
                if ui.button('OK'):
                    self.notice=None;ui.close_current_popup()
                ui.end_popup()
        if self.error:
            ui.open_popup('Studio Error')
        # Wrapped text alone cannot determine an auto-sized popup's width.
        ui.set_next_window_size(ui.ImVec2(min(640.,v.size.x-40),0.),ui.Cond_.always)
        if ui.begin_popup_modal('Studio Error',flags=ui.WindowFlags_.always_auto_resize)[0]:
            ui.text_wrapped(self.error or '')
            if ui.button('OK'):
                self.error=None;ui.close_current_popup()
            ui.end_popup()

    def render(self):
        entry=self.entry
        index=self.selected_index
        self.viewer.begin_frame(self.timeline_time)
        self.render_environment()
        import_pose=self.external_panel.preview_pose()
        if import_pose is not None:
            for e in self.pose_entries:self.mesh_renderer.hide(self.viewer,e.id)
            self.mesh_renderer.hide(self.viewer,-1)
            self.viewer.log_points('studio/joints',None)
            self.viewer.log_points('studio/selected',None)
            self.skeleton_renderer.hide(self.viewer,-42)
            self.mesh_renderer.draw_pose(self.viewer,wp.array(import_pose,dtype=wp.transform,device=self.engine.device),
                                         wp.transform_identity(),wp.vec3(.82,.88,.95),'studio-import')
            self.viewer.log_state(self.state)
            self.viewer.end_frame()
            return
        self.mesh_renderer.hide(self.viewer,'studio-import')
        if self.show_targets:
            self._draw_target_previews()
        else:
            for e in self.pose_entries: self.mesh_renderer.hide(self.viewer,e.id)
        if self.timeline is not None and self.show_generated:
            self.mesh_renderer.draw_pose(self.viewer,self.current_pose,wp.transform_identity(),
                                         wp.vec3(.82,.88,.95),-1)
        else:
            self.mesh_renderer.hide(self.viewer,-1)
        pose=entry.preview_pose.numpy()
        world=fk(pose,self.skeleton._np_parent_indices)
        target=wp.transform(entry.placement)
        before=np.asarray(target).copy()
        scene_box=self.scene_gizmo_box()
        scene_before=np.array(scene_box['position']) if scene_box else None
        scene_ident=scene_box['id'] if scene_box else None
        scene_target=wp.transform(wp.vec3(*scene_before),wp.quat_identity()) if scene_box else None
        editing=self.edit_bones and scene_box is None and not self.busy and not getattr(self,'motion_playing',False)
        if editing:
            target=wp.transform(*world[self.bone_index])
            before=np.asarray(target).copy()
            self.viewer.log_points('studio/joints',wp.array(world[self.bone_indices,:3],dtype=wp.vec3),
                                   radii=.021,colors=wp.array([(.95,.65,.18)]*len(self.bone_indices),dtype=wp.vec3))
            self.viewer.log_points('studio/selected',wp.array(world[self.bone_index:self.bone_index+1,:3],dtype=wp.vec3),
                                   radii=.035,colors=wp.array([(1.,.25,.15)],dtype=wp.vec3))
            displayed=entry.sampled_poses
            if getattr(entry,'motion_track',None) is not None:
                displayed=wp.array(np.repeat(pose[None],4,axis=0),dtype=wp.transform,device=self.engine.device)
            self.skeleton_renderer.draw_batch(self.viewer,displayed,1,wp.transform_identity(),
                wp.array([(.95,.65,.18)]*4,dtype=wp.vec3),-42)
        else:
            self.viewer.log_points('studio/joints',None)
            self.viewer.log_points('studio/selected',None)
            self.skeleton_renderer.hide(self.viewer,-42)
        if not self.busy and not self.video_exporting:
            if scene_box:
                log_transform_gizmo(self.viewer,'studio/environment/'+scene_ident,scene_target,
                    translation_locks=[False]*3,rotation_locks=[True]*3)
            else:
                log_transform_gizmo(self.viewer,'studio/edit',target,
                    translation_locks=[editing and self.tool==0 and self.bone_index!=0]*3,
                    rotation_locks=[editing and self.tool==1]*3)
        self.viewer.log_state(self.state)
        self.viewer.end_frame()
        # GUI can change the selected target; apply gizmo only to the one it was drawn for.
        if scene_box is not None:
            self.apply_scene_gizmo(scene_ident,scene_before,np.asarray(scene_target)[:3])
        if scene_box is None and not self.scene_editing and self.selected_index==index and self.entry is entry and not same_transform(target,before):
            if editing:
                if self.tool==1 and self.bone_index!=0:
                    pose=solve_ik(pose,self.skeleton._np_parent_indices,self.bone_index,np.asarray(target)[:3])
                else:
                    parent=self.skeleton.joint_parent(self.bone_index)
                    rw=Rotation.from_quat(np.asarray(target)[3:])
                    if parent>=0:
                        pose[self.bone_index,3:]=(Rotation.from_quat(world[parent,3:]).inv()*rw).as_quat()
                    else:
                        pose[0]=np.asarray(target)
                self.edit_pose(pose)
            else:
                self.remember(continuous=True);entry.placement=target;self.changed()

    def run(self,max_frames=None):
        frame=0
        try:
            while self.viewer.is_running() and (max_frames is None or frame<max_frames):
                with wp.ScopedStream(self.engine.stream):
                    now=time.perf_counter()
                    delta=min(max(now-self._last_frame_time,0.),.1)
                    self._last_frame_time=now
                    try:
                        self.step(delta)
                    except Exception as exc:
                        traceback.print_exc()
                        self.preview_playing=False
                        self.error=str(exc)
                        if max_frames is not None: raise
                    # A UI exception can leave ImGui's frame stack unbalanced. Propagate it
                    # to the launcher instead of repeatedly entering an invalid frame.
                    self.render()
                frame+=1
        finally:
            try:
                if self.dirty:
                    write_document(USER/'recovery.mbstudio.json','project',self.skeleton,self.serialize_entries(),extras=self.project_extras())
            finally:
                if getattr(self,'ue_live',False):self.disconnect_ue()
                self.external_panel.pool.shutdown(wait=True,cancel_futures=True)
                self.pool.shutdown(wait=True,cancel_futures=True)
                self.audio.close()
                self.engine.close()
                self.viewer.close()


def main():
    global USER
    import newton.examples
    parser=create_gl_parser()
    parser.add_argument('--project',type=Path)
    parser.add_argument('--recover',action='store_true',help='Recover the autosaved session without replacing the Save destination.')
    parser.add_argument('--manual',action='store_true',help='Open the built-in user guide on startup.')
    parser.add_argument('--licenses',action='store_true',help='Open licenses and credits on startup.')
    parser.add_argument('--fp16',action='store_true')
    parser.add_argument('--verify',type=Path,help='Run the full Studio integration check into this folder.')
    parser.add_argument('--verify-scene',type=Path,help='Verify environment interactions in an isolated user directory.')
    parser.add_argument('--verify-full-motion',type=Path,help='Verify complete motion playback and exits in an isolated user directory.')
    parser.add_argument('--environment',action='store_true',help='Open the environment authoring window.')
    viewer,args=newton.examples.init(parser)
    configure_logging(args)
    try:
        require_tensorrt()
    except SystemExit as exc:
        viewer.close()
        raise RuntimeError(
            'TensorRT could not start. Check that a compatible NVIDIA GPU is enabled and update its NVIDIA driver.\n'
            'TensorRTを起動できません。対応するNVIDIA GPUが有効か確認し、ドライバーを更新してください。'
        ) from exc
    if args.verify or args.verify_scene or args.verify_full_motion:
        # Verification must never replace the user's recovery file or preferences.
        USER=(args.verify or args.verify_scene or args.verify_full_motion).resolve()/'user_data'
    studio=Studio(viewer,fp16=args.fp16)
    if args.verify_full_motion:
        from .studio_verify_full_motion import verify
        try:verify(studio,args.verify_full_motion.resolve())
        finally:
            studio.pool.shutdown(wait=True,cancel_futures=True);studio.engine.close();viewer.close()
        return
    if args.verify_scene:
        from .studio_scene_verify import verify
        try:verify(studio,args.verify_scene.resolve())
        finally:
            studio.pool.shutdown(wait=True,cancel_futures=True);studio.engine.close();viewer.close()
        return
    if args.verify:
        from .studio_verify import verify
        try:
            verify(studio,args.verify)
        finally:
            studio.pool.shutdown(wait=True,cancel_futures=True)
            studio.engine.close()
            viewer.close()
        return
    if args.project: studio.load_project(args.project)
    elif args.recover:
        studio.pending='recover'
        studio._dispatch()
    studio.show_manual=args.manual
    studio.show_licenses=args.licenses
    studio.scene_window=args.environment
    studio.run(args.num_frames if args.test else None)


if __name__=='__main__':
    main()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
