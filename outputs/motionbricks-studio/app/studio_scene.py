"""Studio environment authoring and original Smart Primitive target sequences."""
import copy,json,math
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
import warp as wp
from .studio_scene_data import ACTIONS,PRESETS,new_box,validate_scene,segment_hit,route,choose_action,approach_error,ray_box_hit
from .studio_data import root_transform
from .runtime.common.rig import ASSETS_ROOT

def _custom_primitive_targets(app,box,direction,action):
    from .runtime.common.io.smart_primitive_document import SmartPrimitiveAssetPool
    if not hasattr(app,'scene_asset_pool'):
        app.scene_asset_pool=SmartPrimitiveAssetPool(app.clip_registry,app.skeleton.reference_local_transforms,app.model_to_runtime)
    path=Path(box.get('asset') or ASSETS_ROOT/'smart_primitives/soma'/f'{action}.smart_primitive.json')
    primitive=app.scene_asset_pool.instantiate(path)
    sequences=[min(box.get('sequence',0),primitive.sequence_count-1)]
    if action=='sit':sequences=[primitive.sequence_index('Sit'),primitive.sequence_index('Stand')]
    if min(sequences)<0:raise ValueError('Chair preset needs Sit and Stand sequences')
    output=wp.empty((primitive.max_sequence_length*4,app.skeleton.num_joints),dtype=wp.transform,device=app.engine.device)
    params=primitive.get_world_target_poses_for_sequence(sequences[0],output,app.engine.stream)
    app.engine.synchronize();sample=output.numpy()[:len(params)*4]
    travel=sample[-4,0,:2]-sample[0,0,:2]
    if action=='sit':
        # Chair +Y is the authored seating direction; box yaw controls the seat.
        yaw=math.radians(box['yaw'])
    else:
        yaw=math.atan2(direction[1],direction[0])-math.atan2(travel[1],travel[0])
    placement=np.r_[box['position'][:2],0.,Rotation.from_euler('z',yaw).as_quat()]
    primitive.set_node_local_transform(0,wp.transform(*placement),app.engine.stream)
    results=[]
    for sequence in sequences:
        params=primitive.get_world_target_poses_for_sequence(sequence,output,app.engine.stream)
        app.engine.synchronize();values=output.numpy()[:len(params)*4].reshape(len(params),4,app.skeleton.num_joints,7)
        for i,(window,param) in enumerate(zip(values,params)):
            hold=round(box.get('hold',2.)*30) if action=='sit' and sequence==sequences[0] and i==len(params)-1 else 0
            results.append(dict(window=window.copy(),num=param.num_poses_to_use,minimum=min(param.allowed_token_counts),maximum=max(param.allowed_token_counts),
                                pins=int(param.ik_pin_mask),early=param.transition_early_by_frames,hold=hold,
                                name=f'{box["name"]} / {primitive.sequence_name(sequence)} {i+1}',source=str(path)))
    if action in ('avoidance','sit'):
        # Keep the crouched/standing pose until the body has cleared the object.
        heading=np.asarray(direction,dtype=float) if action=='avoidance' else np.array([math.cos(yaw),math.sin(yaw)])
        from .studio_scene_data import rotation
        reach=float(np.dot(np.abs(heading@rotation(box)),np.array(box['size'][:2])/2))+.7
        point=np.asarray(box['position'][:2])+heading*reach
        stage=copy.deepcopy(results[-1])
        stage['window'][:,0,:2]+=point-stage['window'][0,0,:2]
        stage.update(name=box['name']+' / Exit',pins=0,early=0,hold=0)
        results.append(stage)
    return results

def primitive_targets(app,box,direction,action):
    from .studio_scene_original import primitive_targets as original_targets
    asset=box.get('asset')
    if asset and Path(asset).name.endswith('.motion.json'):
        from .studio_scene_original import imported_transit_targets
        return imported_transit_targets(app,box,direction,action)
    # Saved projects may still carry a path to an old bundled preset. Migrate
    # those references; only an explicitly supplied external custom file uses
    # the legacy Smart Primitive loader.
    if asset and not Path(asset).resolve().is_relative_to((ASSETS_ROOT/'smart_primitives').resolve()):
        return _custom_primitive_targets(app,box,direction,action)
    return original_targets(app,box,direction,action)

class SceneAuthoring:
    def init_scene(self):
        self.environment=validate_scene({});self.scene_window=False;self.scene_selected=0;self.scene_plan_stale=False
        self.scene_import_pending=None;self.scene_last_export=None;self.scene_plan_signature=None;self.scene_editing=False
    def pick_scene_box(self,origin,direction):
        hits=[(distance,i) for i,b in enumerate(self.environment['boxes']) if b['enabled'] and (distance:=ray_box_hit(origin,direction,b)) is not None]
        return min(hits) if hits else (float('inf'),None)
    def select_scene_box(self,index):
        self.scene_selected=index;self.scene_editing=True;self.scene_window=True
    def scene_gizmo_box(self):
        boxes=self.environment['boxes']
        if not self.scene_editing or self.busy or not 0<=self.scene_selected<len(boxes):return None
        box=boxes[self.scene_selected]
        return box if box['enabled'] else None
    def apply_scene_gizmo(self,ident,before,position):
        """Apply only if selection and numeric values did not change this frame."""
        box=self.scene_gizmo_box()
        if box is None or box['id']!=ident or not np.allclose(box['position'],before,atol=1e-6,rtol=0.):return
        position=np.asarray(position,dtype=float)
        if position.shape!=(3,) or not np.isfinite(position).all():return
        if not np.allclose(position,before,atol=1e-6,rtol=0.):
            box['position']=position.tolist();self.scene_changed()
    def scene_base_signature(self):
        return tuple((e.id,tuple(e.sampled_poses.numpy()[[0,-1],0].ravel())) for e in self.pose_entries if not getattr(e,'scene_generated',False))
    def scene_changed(self):
        self.environment=validate_scene(self.environment);self.scene_plan_stale=True
        self.dirty=True;self.timeline_stale=self.timeline is not None;self.preview_playing=False
    def add_scene_box(self,action):
        a=self.pose_entries[0].sampled_poses.numpy()[-1,0,:3]
        b=self.pose_entries[-1].sampled_poses.numpy()[0,0,:3]
        position=(a+b)/2;position[2]=0.
        self.environment['boxes'].append(new_box(action,position));self.select_scene_box(len(self.environment['boxes'])-1);self.scene_changed()
    def import_scene_objects(self):
        from .studio_ue_pose import from_ue
        from .studio_ue_transport import read_json
        data=read_json(self.ue_directory()/'objects.json')
        if data.get('error'):raise ValueError(data['error'])
        if data.get('request_id')!=getattr(self,'ue_pose_request',{}).get('request_id'):raise ValueError('Objects belong to another UE connection. Send them from UE again.')
        if data.get('schema')!='motionbricks-objects' or data.get('version')!=1:raise ValueError('Unsupported UE object format')
        values=[]
        for item in data['objects']:
            points=from_ue([list(p)+[0,0,0,1] for p in item['corners']])[:,:3]
            low=points.min(axis=0);high=points.max(axis=0)
            if min(high-low)<.002:continue
            values.append(dict(id='ue:'+item['id'],name=item['name'],position=((low+high)/2).tolist(),size=(high-low).tolist(),yaw=0.,action='auto',sequence=0,hold=2.,enabled=True,
                               ue_path=item['path'],approximation='bounds'))
        replacement={b['id']:b for b in self.environment['boxes']}
        for b in values:
            previous=replacement.get(b['id'],{})
            for key in ('action','sequence','hold','asset','enabled'):
                if key in previous:b[key]=previous[key]
        replacement.update({b['id']:b for b in values})
        candidate=dict(self.environment,boxes=list(replacement.values()));self.environment=validate_scene(candidate)
        self.scene_changed();self.scene_window=True
        if values:self.select_scene_box(next(i for i,b in enumerate(self.environment['boxes']) if b['id']==values[-1]['id']))
        self.scene_last_export=data.get('export_id')
        self.status=f'Imported {len(values)} UE objects as bounding boxes.'
    def request_scene_objects(self):
        import time
        if not getattr(self,'ue_live',False):raise ValueError('Start UE synchronization and connect a character first.')
        self.scene_import_pending=(self.ue_command('objects'),time.perf_counter())
        self.status='Waiting for selected UE objects...'
    def poll_scene_objects(self):
        import time
        from .studio_ue_transport import read_json
        pending=getattr(self,'scene_import_pending',None)
        if not pending and not getattr(self,'ue_live',False):return
        try:
            data=read_json(self.ue_directory()/'objects.json',optional=True)
            if pending and data and data.get('command_id')==pending[0]:
                self.scene_import_pending=None;self.import_scene_objects()
            elif not pending and data and data.get('request_id')==getattr(self,'ue_pose_request',{}).get('request_id') and data.get('export_id') and data['export_id']!=self.scene_last_export:
                self.scene_last_export=data['export_id'];self.import_scene_objects()
            elif pending and time.perf_counter()-pending[1]>10:
                self.scene_import_pending=None;raise ValueError('UE object request timed out. Update the bridge and connect a character.')
        except Exception as exc:self.scene_import_pending=None;self.error=str(exc)
    def _scene_entry(self,window,name,source,*,num=4,minimum=8,maximum=14,pins=0,early=0,hold=0,object_id='',track=None):
        from .inbetweener_demo import PoseEntry
        entry=PoseEntry(self._next_id,name,Path(source),self.pose_entries[0].clip,0.,wp.transform_identity())
        self._next_id+=1;entry.manual_window=window.copy();entry.num_poses_to_use=num;entry.min_tokens=minimum;entry.max_tokens=maximum
        entry.ik_pin_mask=pins;entry.transition_early_by_frames=early;entry.hold_frames=hold
        entry.scene_generated=True;entry.scene_object_id=object_id;entry.show_skeletons=False
        entry.motion_track=copy.deepcopy(track)
        return entry
    def _route_entry(self,point,direction):
        from .studio_scene_original import route_window
        return self._scene_entry(**route_window(self,point,direction))
    def start_environment_plan(self,generate=False):
        if self.busy:return False
        # External Smart Primitive loaders retain their existing GPU-based path.
        custom=any(b.get('asset') and not Path(b['asset']).name.endswith('.motion.json')
                   and not Path(b['asset']).resolve().is_relative_to((ASSETS_ROOT/'smart_primitives').resolve()) for b in self.environment['boxes'])
        if custom:
            self.plan_environment()
            if generate:self.start_generation()
            return True
        from .studio_scene_plan import snapshot,compute
        data=snapshot(self,generate);self.job_kind='scene_plan';self.job=self.pool.submit(compute,data)
        self.status='Checking interaction fit in background / 環境動作の適合を計算中…';return True
    def plan_environment(self):
        """Plan off to the side so a failure never removes the user's targets."""
        base=[e for e in self.pose_entries if not getattr(e,'scene_generated',False)]
        if len(base)<2:raise ValueError('Add a start and a destination first')
        boxes=[b for b in validate_scene(self.environment)['boxes'] if b['enabled']]
        planned=[base[0]];radius=self.environment['radius']+(.6 if self.environment['speed']=='run' else 0.);used=set()
        current=base[0].sampled_poses.numpy()[-1,0,:3].copy()
        def append_route(end,exclude=()):
            nonlocal current
            points=route(current,end,[b for b in boxes if b['id'] not in exclude],radius)
            for i,(p,q) in enumerate(zip(points,points[1:])):
                # A locomotion target also makes Walk/Run meaningful on straight legs.
                if np.linalg.norm(q-p)>1.5:planned.append(self._route_entry((p+q)/2,q-p))
                if i+1<len(points)-1:planned.append(self._route_entry(q,points[i+2]-q))
            current=np.r_[np.asarray(end)[:2],0.]
        for destination in base[1:]:
            end=destination.sampled_poses.numpy()[0,0,:3]
            vector=end[:2]-current[:2];distance=np.linalg.norm(vector)
            if distance<.01:planned.append(destination);continue
            direction=vector/distance;origin=current.copy()
            hits=sorted(((t,b) for b in boxes if b['id'] not in used and (t:=segment_hit(origin,end,b,radius)) is not None),key=lambda x:x[0])
            for _,box in hits:
                action=choose_action(box,direction,getattr(self,'language','en'))
                if action=='avoid':continue
                try:stages=primitive_targets(self,box,direction,action)
                except ValueError as exc:
                    from .studio_scene_kimodo import InteractionFitError
                    if box['action']=='auto' and isinstance(exc,InteractionFitError):continue
                    raise
                entry=stages[0]['window'][0,0,:3]
                last=stages[-1]
                exit=last['track']['keys'][-1]['pose'][0,:3] if last.get('track') else last['window'][0,0,:3]
                if np.dot(entry[:2]-current[:2],direction)<-.1 or np.dot(end[:2]-exit[:2],direction)<-.1:
                    if box['action']=='auto':continue
                    raise ValueError(approach_error(box['name'],current,end,entry,exit,direction,getattr(self,'language','en')))
                append_route(entry,() if action=='sit' else (box['id'],))
                for stage in stages:planned.append(self._scene_entry(**stage,object_id=box['id']))
                current=exit.copy();used.add(box['id'])
            append_route(end)
            planned.append(destination)
        self.pose_entries=planned;self.selected_index=min(self.selected_index,len(planned)-1)
        self.changed('Environment route ready. Generated targets can be inspected before playback.');self.scene_plan_stale=False
        self.scene_plan_signature=self.scene_base_signature()
    def render_environment(self):
        from motionbricks.renderers.solid_box_renderer import SolidBoxRenderer
        if not hasattr(self,'scene_box_renderer'):self.scene_box_renderer=SolidBoxRenderer(device=self.engine.device)
        boxes=[b for b in self.environment['boxes'] if b['enabled']]
        transforms=[wp.transform(wp.vec3(*b['position']),wp.quat_from_axis_angle(wp.vec3(0,0,1),math.radians(b['yaw']))) for b in boxes]
        active=self.scene_gizmo_box()
        self.scene_box_renderer.draw_batch(self.viewer,transforms,[wp.vec3(*b['size']) for b in boxes],[wp.vec3(1.,.85,.15) if active and b['id']==active['id'] else wp.vec3(.85,.5,.15) for b in boxes],'studio_environment')

def draw_environment(app,ui):
    if not app.scene_window:return
    ui.set_next_window_size(ui.ImVec2(620,650),ui.Cond_.first_use_ever)
    visible,app.scene_window=ui.begin('Environment & Interactions###studio_scene',app.scene_window)
    position=ui.get_window_pos();size=ui.get_window_size();app._scene_ui_bounds=(position.x,position.y,size.x,size.y)
    try:
        if not visible:return
        ui.begin_disabled(app.busy)
        ui.text_wrapped('Objects use bounding boxes. Auto selects supported samples or plans a detour. Inspect generated motion for contact.')
        if ui.button('Import UE objects'):
            try:app.request_scene_objects()
            except Exception as exc:app.error=str(exc)
        for i,action in enumerate(PRESETS):
            if i%2:ui.same_line()
            if ui.button('Add '+action):app.add_scene_box(action)
        boxes=app.environment['boxes']
        ui.begin_child('scene_objects',ui.ImVec2(0,150),child_flags=ui.ChildFlags_.borders)
        for i,box in enumerate(boxes):
            if ui.selectable(box['name']+'##object'+box['id'],app.scene_selected==i)[0]:app.select_scene_box(i)
        ui.end_child()
        if boxes:
            previous=copy.deepcopy(app.environment)
            app.scene_selected=min(app.scene_selected,len(boxes)-1);box=boxes[app.scene_selected]
            _,app.scene_editing=ui.checkbox('Move selected object',app.scene_editing)
            ui.text_wrapped('Click a box in the viewport, then drag its X/Y/Z arrows. Select a character or target row to edit poses again.')
            changed,box['name']=ui.input_text('Object name',box['name'])
            c,box['enabled']=ui.checkbox('Enabled',box['enabled']);changed|=c
            c,value=ui.input_float3('Object center (m)',box['position']);changed|=c
            if c:box['position']=list(value)
            c,value=ui.input_float3('Size (m)',box['size']);changed|=c
            if c:box['size']=[max(.01,float(x)) for x in value]
            ui.text_wrapped('Position Z is the object center. A 0.75 m box on the ground has Z = 0.375 m.')
            if box['action']!='avoidance' and ui.button('Place on ground'):
                box['position'][2]=box['size'][2]/2;changed=True
            if ui.is_item_hovered():ui.set_tooltip('Adjusts the box in Studio only. UE actors are not moved.')
            c,box['yaw']=ui.input_float('Object yaw',box['yaw']);changed|=c
            c,index=ui.combo('Interaction',ACTIONS.index(box['action']),list(ACTIONS));changed|=c
            if c:box['action']=ACTIONS[index]
            c,box['sequence']=ui.input_int('Sample variation',box['sequence']);changed|=c;box['sequence']=max(0,box['sequence'])
            c,box['hold']=ui.slider_float('Seated hold (s)',box['hold'],0.,30.);changed|=c
            if box.get('asset'):
                ui.text_wrapped('Preset: '+box['asset'])
                if ui.button('Clear custom preset'):box['asset']='';changed=True
            if ui.button('Load custom interaction preset...'):app.pending='scene_preset'
            if ui.button('Remove object'):
                boxes.pop(app.scene_selected);changed=True
            if changed:
                app.scene_editing=True
                try:app.scene_changed()
                except Exception as exc:app.environment=previous;app.error=str(exc)
        c,index=ui.combo('Route motion',0 if app.environment['speed']=='walk' else 1,['Walk','Run'])
        if c:app.environment['speed']=('walk','run')[index];app.scene_changed()
        c,radius=ui.slider_float('Clearance radius (m)',app.environment['radius'],.1,1.)
        if c:app.environment['radius']=radius;app.scene_changed()
        if ui.button('Build environment route'):
            try:app.start_environment_plan()
            except Exception as exc:app.error=str(exc)
        ui.same_line()
        if ui.button('Generate environment motion'):
            try:app.start_environment_plan(generate=True)
            except Exception as exc:app.error=str(exc)
        ui.text_wrapped('Environment actions use the replacement Kimodo clips. Object-fit checks run in the background. Auto detours when a clip cannot fit. Seat candidates use 0.4 m seats; inspect contacts and transitions. Jump variant 0 prefers a hand, with a no-hand fallback; variant 1 uses no hands.')
        ui.end_disabled()
    finally:ui.end()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
