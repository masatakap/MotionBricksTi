"""Authoring controller and timeline UI for hand-keyed SOMA motion."""
from pathlib import Path
import numpy as np
import warp as wp
from .studio_data import root_transform,write_document
from .studio_motion_data import create_track,sample_track,put_key,resize_track,conditioning_window,window_has_motion,plays_entire_motion


class MotionAuthoring:
    def set_entire_motion(self,enabled):
        track=getattr(self.entry,'motion_track',None)
        if track is None or track.get('playback')=='scene_exact':return
        if plays_entire_motion(track)==bool(enabled):return
        self.remember();track['playback']='full_clip' if enabled else 'conditioning'
        self.motion_playing=False
        if enabled:self.motion_frame=0.
        self.changed()

    def draw_entire_motion_control(self,ui):
        track=getattr(self.entry,'motion_track',None)
        if track is None:return
        enabled=plays_entire_motion(track)
        ui.begin_disabled(track.get('playback')=='scene_exact')
        if ui.button('Always Play Entire Motion: ON' if enabled else 'Always Play Entire Motion: OFF'):
            self.set_entire_motion(not enabled)
        ui.end_disabled()
        if enabled:ui.text_wrapped('ON: reach the first pose, play every frame, then transition from the final pose.')
        else:
            hints={'ja':'OFF：区間での動作設定に従い、移動動作の維持・到着後の動作・ポーズ条件を使い分けます。','en':'OFF: interval settings choose continuous movement, an arrival action, or pose conditions.','es':'OFF: el tramo elige movimiento continuo, acción al llegar o condiciones de pose.','fr':'OFF : le trajet utilise mouvement continu, action à l’arrivée ou conditions de pose.','zh':'OFF：区间设置决定持续移动、到达后动作或姿势条件。'}
            ui.text_wrapped(hints.get(getattr(self,'language','en'),hints['en']))
        if enabled:ui.text_wrapped('The clip itself plays without AI or IK corrections. AI is used only to generate the connections before and after it.')

    def can_generate_motion(self):
        from .studio_interval import mode
        t=getattr(self.pose_entries[0],'motion_track',None) if self.pose_entries else None
        return bool(self.pose_entries and (len(self.pose_entries)>1 or plays_entire_motion(t) or mode(t)=='action'))

    def new_authored_motion(self,from_current=False):
        source=str(self.entry.path)
        seed=(root_transform(self.entry.preview_pose.numpy(),np.asarray(self.entry.placement),inverse=True) if from_current else
              root_transform(self.skeleton.reference_local_transforms.numpy(),np.asarray(self.model_to_runtime)))
        self.duplicate_target(self.selected_index)
        e=self.entry
        e.name='My Motion';e.path=Path('authored-current-pose' if from_current else 'authored-reference')
        if not from_current:e.placement=wp.transform_identity();e.euler_degrees=None
        e.motion_track=create_track(seed,'current_pose' if from_current else 'reference',source if from_current else '')
        e.num_poses_to_use=4;e.hold_frames=0;e.duration_seconds=0.
        self.pose_name=e.name
        self.open_motion_editor();self.changed()

    def open_motion_editor(self):
        self.motion_editor_open=True;self.motion_playing=False
        self.motion_entry_id=self.entry.id
        self.motion_frame=float(self.entry.motion_track['sample_frame'])
        self.preview_playing=False;self.audio.pause();self.show_generated=False;self.show_targets=True
        self.update_motion_preview()

    def motion_cursor(self):
        if getattr(self,'motion_editor_open',False) and getattr(self,'motion_entry_id',None)==self.entry.id:
            return int(round(self.motion_frame))
        return int(self.entry.motion_track['sample_frame'])

    def update_motion_preview(self):
        if not getattr(self,'motion_editor_open',False):return
        if getattr(self,'motion_entry_id',None)!=self.entry.id:
            self.motion_playing=False
            return
        track=getattr(self.entry,'motion_track',None)
        if track is not None:
            pose=root_transform(sample_track(track,self.motion_frame),np.asarray(self.entry.placement))
            self.entry.preview_pose=wp.array(pose,dtype=wp.transform,device=self.engine.device)

    def edit_motion_pose(self,world_pose,continuous):
        self.motion_playing=False
        self.remember(continuous=continuous)
        pose=root_transform(world_pose,np.asarray(self.entry.placement),inverse=True)
        put_key(self.entry.motion_track,self.motion_cursor(),pose)
        self.changed()

    def save_authored_motion(self,path):
        if getattr(self.entry,'motion_track',None) is None:raise ValueError('Select an authored motion')
        e=self.serialize_entries([self.entry])[0]
        e['name']=self.pose_name.strip()[:256] or e['name']
        write_document(path,'motion',self.skeleton,[e])
        self._scan_library();self.status='Saved pose: '+str(path)

    def step_motion_editor(self,delta):
        if getattr(self,'motion_editor_open',False) and getattr(self,'motion_playing',False):
            if getattr(self,'motion_entry_id',None)!=self.entry.id:self.motion_playing=False;return
            self.motion_frame+=delta*30
            last=self.entry.motion_track['last_frame']
            if self.motion_frame>=last:self.motion_frame=float(last);self.motion_playing=False
            self.update_motion_preview()


def draw_motion_key_list(app,ui,track,cursor):
    ui.begin_child('motion_keys',ui.ImVec2(0,95),child_flags=ui.ChildFlags_.borders)
    clipper=ui.ListClipper()
    try:
        clipper.begin(len(track['keys']))
        while clipper.step():
            for index in range(clipper.display_start,clipper.display_end):
                f=track['keys'][index]['frame']
                if ui.selectable(f'{f} | {f/30:.3f} s###motion_key_{f}',cursor==f)[0]:
                    app.motion_frame=float(f);app.update_motion_preview()
    finally:
        clipper.end();ui.end_child()


def draw_motion_editor(app,ui):
    track=getattr(app.entry,'motion_track',None)
    if track is None or app.motion_entry_id!=app.entry.id:
        app.motion_playing=False
        return
    viewport=ui.get_main_viewport()
    ui.set_next_window_pos(ui.ImVec2(viewport.pos.x+viewport.size.x*.32,viewport.pos.y+75),ui.Cond_.first_use_ever)
    ui.set_next_window_size(ui.ImVec2(min(550,viewport.size.x-40),min(650,viewport.size.y-100)),ui.Cond_.first_use_ever)
    visible,app.motion_editor_open=ui.begin('Motion Authoring###motion_authoring',app.motion_editor_open)
    position=ui.get_window_pos();size=ui.get_window_size();app._motion_ui_bounds=(position.x,position.y,size.x,size.y)
    try:
        if not visible:return
        ui.begin_disabled(app.busy)
        _,app.pose_name=ui.input_text('Motion name',app.pose_name)
        app.draw_entire_motion_control(ui)
        from .studio_interval import draw_controls
        draw_controls(app,ui)
        ui.text_wrapped('Edit bones at each time. Edits automatically add a key. Other keys are preserved.')
        if track['origin'] in ('licensed_reference','video_reference'):
            provenance=track.get('provenance',{})
            ui.text_wrapped('Reference: '+str(provenance.get('title',track.get('seed_source',''))))
            ui.text_wrapped('License: '+str(provenance.get('license','See source terms')))
        elif track['origin']=='reference':ui.text_wrapped('Created from the skeleton reference pose; no motion clip was copied.')
        elif track['origin']=='generated':ui.text_wrapped('Kimodo generated clip. Every frame is preserved; source/contact metadata is stored with this motion.')
        elif track['origin']=='imported':
            from .studio_external_panel import label
            ui.text_wrapped(label('note',app.language))
        else:ui.text_wrapped('Created from the current pose. Its source terms still apply.')
        changed,frame=ui.slider_int('Editing frame',int(round(app.motion_frame)),0,track['last_frame'])
        if changed:app.motion_playing=False;app.motion_frame=float(frame);app.update_motion_preview()
        ui.text_unformatted(f'{app.motion_frame/30:.3f} / {track["last_frame"]/30:.3f} s | 30 fps')
        if ui.button('Pause Motion' if app.motion_playing else 'Preview Motion'):
            if app.motion_frame>=track['last_frame']:app.motion_frame=0.
            app.motion_playing=not app.motion_playing;app.update_motion_preview()
        ui.same_line()
        if ui.button('Motion Start'):app.motion_playing=False;app.motion_frame=0.;app.update_motion_preview()
        ui.begin_disabled(app.motion_playing)
        changed,seconds=ui.input_float('Motion length (s)',track['last_frame']/30,.1,1.,'%.3f')
        if changed and np.isfinite(seconds):
            app.remember();resize_track(track,max(3,round(seconds*30)))
            app.motion_frame=min(app.motion_frame,track['last_frame']);app.changed()
        if ui.button('Add Key'):
            app.remember();put_key(track,app.motion_cursor(),sample_track(track,app.motion_frame));app.changed()
        ui.same_line()
        cursor=app.motion_cursor()
        ui.begin_disabled(cursor in (0,track['last_frame']) or not any(k['frame']==cursor for k in track['keys']))
        if ui.button('Delete Key'):
            app.remember();track['keys']=[k for k in track['keys'] if k['frame']!=cursor];app.changed()
        ui.end_disabled()
        draw_motion_key_list(app,ui,track,cursor)
        pose=sample_track(track,app.motion_frame)
        changed,position=ui.drag_float3('Motion root position',pose[0,:3].tolist(),.01,-10000.,10000.,'%.3f')
        if changed:
            pose[0,:3]=position
            app.edit_motion_pose(root_transform(pose,np.asarray(app.entry.placement)),True)
        ui.begin_disabled(plays_entire_motion(track))
        if ui.button('Use This Time (4 Poses)'):
            app.remember()
            anchor=3 if app.selected_index==0 else 0
            track['sample_frame']=int(np.clip(cursor-anchor,0,track['last_frame']-3))+anchor
            app.entry.num_poses_to_use=4;app.entry.hold_frames=0;app.changed()
        ui.end_disabled()
        if plays_entire_motion(track):
            ui.text_wrapped('Every frame is kept. The conditioning time does not trim the motion in this mode.')
            ui.text_unformatted(f'{track["last_frame"]+1} frames | 30 fps')
        else:
            ui.text_unformatted('Conditioning frame')
            ui.same_line();ui.text_unformatted(f'{track["sample_frame"]} | {track["sample_frame"]/30:.3f} s')
            moving=window_has_motion(conditioning_window(track,3 if app.selected_index==0 else 0))
            ui.text_wrapped('The selected four poses contain movement.' if moving else 'The selected four poses are static. Choose a time with movement to carry motion information.')
        if ui.button('Save Motion As...'):app.pending='save_motion'
        ui.end_disabled();ui.end_disabled()
    finally:
        ui.end()
        if not app.motion_editor_open:
            app.motion_playing=False;app.refresh_poses()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
