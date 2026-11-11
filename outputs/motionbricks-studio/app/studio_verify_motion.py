"""Actual-GPU authoring checks, invoked by the Studio integration verifier."""
import copy
import json
import numpy as np
from scipy.spatial.transform import Rotation
from .studio_data import root_transform,read_document
from .studio_motion_data import sample_track,conditioning_window
from .studio_locales import LANGUAGES


def verify_authored_motion(app,folder):
    app.new_authored_motion()
    e=app.entry;track=e.motion_track
    assert track['origin']=='reference' and not track['seed_source'] and str(e.path)=='authored-reference'
    reference=root_transform(app.skeleton.reference_local_transforms.numpy(),np.asarray(app.model_to_runtime))
    np.testing.assert_allclose(track['keys'][0]['pose'],reference)
    app.motion_frame=30.;app.update_motion_preview()
    pose=e.preview_pose.numpy();pose[0,0]+=.6
    j=app.skeleton.joint_index('LeftForeArm')
    pose[j,3:]=(Rotation.from_quat(pose[j,3:])*Rotation.from_euler('x',40,degrees=True)).as_quat()
    app.edit_pose(pose,continuous=False)
    assert e.num_poses_to_use==4
    initial=track['keys'][0]['pose'].copy();end=track['keys'][-1]['pose'].copy()
    app.motion_frame=15.;app.update_motion_preview()
    pose=e.preview_pose.numpy();pose[j,3:]=(Rotation.from_quat(pose[j,3:])*Rotation.from_euler('y',15,degrees=True)).as_quat()
    app.edit_pose(pose,continuous=False)
    assert len(e.motion_track['keys'])==3
    np.testing.assert_array_equal(e.motion_track['keys'][0]['pose'],initial)
    np.testing.assert_array_equal(e.motion_track['keys'][-1]['pose'],end)
    app.history();assert len(e.motion_track['keys'])==2
    app.history(redo=True);assert len(e.motion_track['keys'])==3
    track=e.motion_track;track['sample_frame']=15;app.changed()
    conditioning=app.canonical_window(e).copy()
    assert not np.allclose(conditioning[0],conditioning[-1])
    app.pose_name='Authored Reference Motion'
    path=folder/'authored.motion.json';app.save_authored_motion(path)
    app.use_library_file(path,register=False)
    np.testing.assert_allclose(app.canonical_window(app.entry),conditioning,atol=1e-6)
    app.save_pose(folder/'authored-static.pose.json')
    static=read_document(folder/'authored-static.pose.json',app.skeleton,'pose')[0]
    assert static['motion_track'] is None and static['num_poses']==1
    assert np.allclose(static['window'],static['window'][0])
    app.save_project(folder/'authored-project.mbstudio.json');app.load_project(folder/'authored-project.mbstudio.json')
    app.selected_index=next(i for i,e in enumerate(app.pose_entries) if getattr(e,'motion_track',None) is not None)
    app.open_motion_editor();track=app.entry.motion_track
    np.testing.assert_allclose(conditioning_window(track,0),conditioning,atol=1e-6)
    app.motion_frame=0.;app.motion_playing=True;app.step_motion_editor(.5)
    assert app.motion_frame==15.
    expected=root_transform(sample_track(track,15),np.asarray(app.entry.placement))
    np.testing.assert_allclose(app.entry.preview_pose.numpy(),expected,atol=1e-6)
    app.motion_playing=False;app.step_motion_editor(.5);assert app.motion_frame==15.
    original=app.entry;app.duplicate_target(app.selected_index)
    app.entry.motion_track['keys'][0]['pose'][0,0]+=1
    assert not np.array_equal(original.motion_track['keys'][0]['pose'],app.entry.motion_track['keys'][0]['pose'])
    app.remove_target();app.selected_index=app.pose_entries.index(original);app.open_motion_editor()
    for _,language in LANGUAGES:
        app.set_language(language);app.motion_frame=15.;app.update_motion_preview();app.render();app.render()
    context=copy.deepcopy(track);context['sample_frame']=3
    generated,_=app.generate_snapshot([(conditioning_window(context,3),4,8,14,0,0.),
                                      (conditioning_window(track,0),4,8,14,0,0.)])
    assert np.isfinite(generated).all() and len(generated)>4
    result=dict(keys=len(track['keys']),duration_seconds=track['last_frame']/30,conditioning_poses=4,
                generated_frames=len(generated),seed='skeleton reference pose',source_clip_copied=False,
                checks=['autokey preserves other times','undo/redo restores complete track',
                        'motion gzip save/load','static snapshot is separate','project recovery keeps all keys',
                        'duplicate owns independent keys','play/pause/seek matches interpolated pose',
                        'all five editor languages render','generation accepts hand-authored four-pose windows'])
    (folder/'authored-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('AUTHORED_MOTION_VERIFICATION '+json.dumps(result))

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
