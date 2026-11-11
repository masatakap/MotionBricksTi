"""Real TensorRT playback/exit verification, with isolated recovery and projects."""
import copy,json,time,hashlib
from pathlib import Path
import numpy as np
import warp as wp
from scipy.spatial.transform import Rotation
from .studio_data import root_transform,fk
from .studio_scene_original import dense_track
from .studio_motion_review import review_motion
from .studio_export import export_fbx


def verify(app,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);root=Path(__file__).resolve().parents[1]
    entries=[copy.copy(e) for e in app.pose_entries[:2]];reports=[]
    standing=app.canonical_window(entries[0]).copy()
    sources={i:root/'user_data/poses'/f'Ti_Reference_v4_dance_ref_{i:02}.motion.json' for i in (1,2)}
    for case,dance,mode in [('dance1_to_walk',1,'walk'),('dance2_to_walk',2,'walk'),('dance2_to_stand',2,'stand'),('start_dance_to_walk',2,'start'),('dance_only',2,'only'),('dance_chain_to_walk',1,'chain')]:
        app.environment=dict(version=1,boxes=[],radius=.35,speed='walk');app.scene_plan_stale=False
        app.pose_entries=[copy.copy(e) for e in entries];app.selected_index=0;app.error=''
        for e in app.pose_entries:e.motion_track=None;e.scene_generated=False;e.manual_window=None;e.hold_frames=0;e.duration_seconds=0.
        app.pose_entries[0].manual_window=standing.copy();app.pose_entries[0].placement=wp.transform_identity()
        app.selected_index=0 if mode in ('start','only') else 1
        app.use_library_file(sources[dance],register=False);app.set_entire_motion(True)
        app.entry.placement=wp.transform(wp.vec3(1,-2,0),wp.quat_from_axis_angle(wp.vec3(0,0,1),.35));app.entry.name=f'Dance {dance}'
        # These must affect only the approach, never trim or retime the dance.
        app.entry.duration_seconds=.8;app.entry.transition_early_by_frames=5
        if mode=='only':app.pose_entries=app.pose_entries[:1];app.selected_index=0
        elif mode=='start':app.pose_entries=app.pose_entries[:1];app.selected_index=0
        if mode=='chain':
            app.add_target();app.selected_index=len(app.pose_entries)-1;app.use_library_file(sources[2],register=False);app.set_entire_motion(True)
            app.entry.placement=wp.transform(wp.vec3(1,-3,0),wp.quat_identity());app.entry.name='Dance 2'
        if mode!='only':
            app.add_target();app.selected_index=len(app.pose_entries)-1
            if mode=='stand':
                app.entry.manual_window=standing.copy();app.entry.motion_track=None;app.entry.num_poses_to_use=1
            else:
                app.use_library_file(root/'user_data/poses/Ti_Original_Adult_walk.motion.json',register=False)
                app.set_entire_motion(False);app.entry.motion_track['sample_frame']=8;app.entry.num_poses_to_use=4
            app.entry.placement=wp.transform(wp.vec3(1,-5 if mode=='chain' else -4,0),wp.quat_identity());app.entry.name='Next: stand' if mode=='stand' else 'Next: walk'
        app.refresh_poses();snapshot=app.generation_snapshot()
        expected={i:v[8] for i,v in enumerate(snapshot) if v[8] is not None}
        assert app.start_generation();started=time.monotonic()
        while app.busy:
            app.step(.016);app.render()
            if app.error:raise RuntimeError(app.error)
            if time.monotonic()-started>180:raise TimeoutError(case)
            time.sleep(.002)
        frames=app.timeline_cpu.copy();assert np.isfinite(frames).all();spans=copy.deepcopy(app._worker_full_motion_spans)
        assert len(spans)==len(expected)
        seams=[];transition_reviews=[]
        for span_index,span in enumerate(spans):
            a,b=span['start_frame'],span['end_frame'];exact=expected[span['entry_index']]
            np.testing.assert_array_equal(frames[a:b+1],exact)
            assert len(exact)==300
            # The source is present through its last key. Measure the outgoing
            # generated step without confusing an intended movement with a jump.
            if b+1<len(frames):
                dot=np.clip(np.abs(np.sum(frames[b,:,3:]*frames[b+1,:,3:],axis=-1)),0,1)
                angle=float(np.rad2deg(2*np.arccos(dot)).max());root_step=float(np.linalg.norm(frames[b+1,0,:3]-frames[b,0,:3]))
                assert angle<25 and root_step<.12,(case,angle,root_step)
                wa,wb=fk(frames[b],app.skeleton._np_parent_indices),fk(frames[b+1],app.skeleton._np_parent_indices)
                delta=Rotation.from_quat(wa[:,3:]).inv()*Rotation.from_quat(wb[:,3:]);world_step=float(np.rad2deg(delta.magnitude()).max())
                feet=[app.skeleton.joint_names.index(s+'Foot') for s in ('Left','Right')];foot_step=float(np.linalg.norm(wb[feet,:3]-wa[feet,:3],axis=-1).max())
                assert world_step<25 and foot_step<.12,(case,world_step,foot_step)
                seams.append(dict(after_frame=b,next_frame=b+1,max_local_step_degrees=angle,max_world_step_degrees=world_step,root_step_m=root_step,max_foot_step_m=foot_step))
                stop=spans[span_index+1]['start_frame'] if span_index+1<len(spans) else len(frames)-1
                if stop-b>=2:
                    transition=review_motion(frames[b:stop+1],app.skeleton._np_parent_indices,list(app.skeleton.joint_names),30)
                    transition_reviews.append(dict(start_frame=b,end_frame=stop,local_max_step_degrees=transition['metrics']['local']['max_step_degrees'],world_max_step_degrees=transition['metrics']['world']['max_step_degrees'],quality='needs_review' if transition['issues'] else 'within_numeric_checks',issues=transition['issues']))
        if mode=='only':np.testing.assert_array_equal(frames,expected[0])
        path=folder/(case+'.mbstudio.json');app.save_project(path);app.load_project(path)
        np.testing.assert_array_equal(app.timeline_cpu,frames)
        assert sum(getattr(e,'motion_track',None) is not None and e.motion_track.get('playback')=='full_clip' for e in app.pose_entries)==len(expected)
        for f in (0,len(frames)//2,len(frames)-1):
            app.timeline.sample(f/30,app.current_pose,stream=app.engine.stream);app.render()
        np.savez_compressed(folder/(case+'.npz'),poses=frames)
        review=review_motion(frames,app.skeleton._np_parent_indices,list(app.skeleton.joint_names),30)
        reports.append(dict(case=case,frames=len(frames),seconds=(len(frames)-1)/30,complete_motion_spans=spans,source_frames_preserved=True,seams=seams,transition_reviews=transition_reviews,project_roundtrip=True,curve_sha256=review['curve_sha256'],full_motion_setting_roundtrip=True,quality_note='Structural replay/continuation verified; generated transition quality is a separate review, not a pass certificate'))
        (folder/'verification.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
        print('FULL_MOTION_CASE',case,'frames',len(frames),'clips',len(expected),'seams',seams,flush=True)
        if case in ('dance2_to_walk','dance_chain_to_walk'):export_fbx(app.export_payload(),folder/(case+'.fbx'),include_mesh=False)

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
