"""Actual TensorRT generation + viewer + save/load integration for interactions."""
import copy,json,time
from pathlib import Path
import numpy as np
import warp as wp
from .studio_scene_data import new_box,local_xy
from .studio_data import fk
from motionbricks.animation.animation_buffer import AnimationBuffer

def verify(app,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    originals=[copy.copy(e) for e in app.pose_entries[:2]];reports=[]
    for action,speed,variation in [('avoid','walk',0),('avoid','run',0),('jump_0_5m','walk',0),('jump_0_75m','walk',0),('jump_0_75m','walk',1),('avoidance','walk',0),('avoidance','run',0),('sit','walk',0)]:
        case=action+('_run' if speed=='run' else '')+('_no_hands' if variation else '')
        app.pose_entries=[copy.copy(e) for e in originals];app.selected_index=0
        for e in app.pose_entries:e.manual_window=None;e.scene_generated=False;e.motion_track=None
        app.pose_entries[0].placement=wp.transform_identity();app.pose_entries[1].placement=wp.transform(wp.vec3(0,-12,0),wp.quat_identity())
        app.refresh_poses();app.environment=dict(version=1,boxes=[new_box(action,(0,-6,0))],radius=.35,speed=speed)
        app.environment['boxes'][0]['sequence']=variation
        app.scene_plan_stale=True;app.scene_window=True
        started=time.perf_counter();app.start_environment_plan(generate=False)
        while app.busy:
            app.step(.016);app.render()
            if app.error:raise RuntimeError(app.error)
            if time.perf_counter()-started>180:raise TimeoutError('environment planning: '+action)
            time.sleep(.002)
        planning_seconds=time.perf_counter()-started
        planned=len(app.pose_entries)
        snapshot=app.generation_snapshot();exact_clips=[item[8] for item in snapshot if len(item)>8 and item[8] is not None]
        from .studio_scene_original import ORIGINALS
        allowed=(ORIGINALS.resolve(),(ORIGINALS.parents[1]/'user_data/poses').resolve())
        assert all(any(e.path.resolve().is_relative_to(root) for root in allowed) for e in app.pose_entries if getattr(e,'scene_generated',False))
        assert planned>2,(action,planned)
        app.start_generation();started=time.time()
        while app.busy:
            app.step(.016);app.render()
            if app.error:raise RuntimeError(app.error)
            if time.time()-started>180:raise TimeoutError(action)
            time.sleep(.002)
        frames=app.timeline_cpu
        assert len(frames)>30 and np.isfinite(frames).all()
        assert np.linalg.norm(frames[-1,0,:2]-np.array([0,-12]))<.3
        for exact in exact_clips:
            matches=np.flatnonzero(np.max(np.abs(frames-exact[0]),axis=(1,2))<2e-6)
            assert any(i+len(exact)<=len(frames) and np.allclose(frames[i:i+len(exact)],exact,atol=2e-6,rtol=0) for i in matches),'Authored interaction frames were changed or dropped'
        if action=='avoid':
            box=app.environment['boxes'][0]
            penetration=[i for i,p in enumerate(frames[:,0,:2]) if np.all(np.abs(local_xy(p,box))<np.array(box['size'][:2])/2+.25)]
            assert not penetration,('detour cuts obstacle',len(penetration))
        path=folder/(case+'.mbstudio.json');app.save_project(path)
        saved=frames.copy();app.load_project(path)
        assert np.array_equal(saved,app.timeline_cpu)
        assert app.environment['boxes'][0]['action']==action
        assert any(getattr(e,'scene_generated',False) for e in app.pose_entries)
        app.scene_plan_stale=False
        for frame in (0,len(frames)//2,len(frames)-1):
            app.timeline.sample(frame/30,app.current_pose,stream=app.engine.stream);app.render()
        np.savez_compressed(folder/(case+'.npz'),poses=frames)
        from .studio_motion_review import review_motion
        ref=app.export_payload()['reference'];review=review_motion(frames,app.skeleton._np_parent_indices,list(app.skeleton.joint_names),30,reference=ref)
        (folder/(case+'.review.json')).write_text(json.dumps(review,indent=2),encoding='utf8')
        reports.append(dict(action=action,speed=speed,variation=variation,planning_seconds=planning_seconds,generation_seconds=app.generation_seconds,targets=planned,frames=len(frames),seconds=len(frames)/30,independent_sources=True,exact_interactions=len(exact_clips),authored_frames_preserved=True,project_roundtrip=True,curve_sha256=review['curve_sha256']))
    (folder/'verification.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
