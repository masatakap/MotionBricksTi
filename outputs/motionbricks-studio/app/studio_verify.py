"""Integration check using the actual SOMA model, Studio state, and FBX exporter."""
from pathlib import Path
import json
import time
import numpy as np
from scipy.spatial.transform import Rotation
import warp as wp
from .studio_data import fk,solve_ik
from .studio_export import export_fbx


def verify(app,folder):
    folder=Path(folder).resolve()
    folder.mkdir(parents=True,exist_ok=True)
    j=app.skeleton.joint_index('LeftForeArm')
    original=app.entry.preview_pose.numpy().copy()
    pose=original.copy()
    pose[j,3:]=(Rotation.from_quat(pose[j,3:])*Rotation.from_euler('x',25,degrees=True)).as_quat()
    app.edit_pose(pose,continuous=False)
    app.refresh_poses()
    assert np.allclose(app.entry.preview_pose.numpy(),pose,atol=1e-5)
    app.history()
    assert np.allclose(app.entry.preview_pose.numpy(),original,atol=1e-5)
    app.history(redo=True)
    assert np.allclose(app.entry.preview_pose.numpy(),pose,atol=1e-5)
    app.mirror_selected_pose()
    assert np.allclose(app.entry.preview_pose.numpy()[0],pose[0],atol=1e-5)
    app.history()
    assert np.allclose(app.entry.preview_pose.numpy(),pose,atol=1e-5)
    app.pose_name='Integration Test Pose'
    app.save_pose(folder/'test.pose.json')
    app.use_library_file(folder/'test.pose.json',register=False)
    assert np.allclose(app.entry.preview_pose.numpy(),pose,atol=1e-5)
    hand=app.skeleton.joint_index('LeftHand')
    world=fk(pose,app.skeleton._np_parent_indices)
    goal=world[hand,:3]+np.array([.04,.02,.03])
    ik=solve_ik(pose,app.skeleton._np_parent_indices,hand,goal)
    ik_error=float(np.linalg.norm(fk(ik,app.skeleton._np_parent_indices)[hand,:3]-goal))
    assert ik_error<np.linalg.norm(world[hand,:3]-goal)
    assert np.allclose(ik[:, :3],pose[:, :3])
    app.save_project(folder/'test.mbstudio.json')
    app.load_project(folder/'test.mbstudio.json')
    assert np.allclose(app.entry.preview_pose.numpy(),pose,atol=1e-5)
    app.start_generation()
    rendered=0
    while app.busy:
        app.step(.016)
        app.render()
        rendered+=1
        if app.error:
            raise RuntimeError(app.error)
        if rendered>20000:
            raise RuntimeError('Generation did not complete.')
        time.sleep(.001)
    assert app.timeline_cpu is not None
    final=app.timeline_cpu[-1]
    p_error=float(np.max(np.abs(final[:,:3]-pose[:,:3])))
    q_error=float(np.max(1-np.abs(np.sum(final[:,3:]*pose[:,3:],axis=-1))))
    assert p_error<1e-4 and q_error<1e-4,(p_error,q_error)
    chained=app.generation_snapshot()
    next_window=chained[-1][0].copy()
    next_window[:,0,0]+=.4
    chained.append((next_window,1,8,14,6,0.))
    chained_motion,_=app.generate_snapshot(chained)
    assert len(chained_motion)>len(app.timeline_cpu)
    assert np.allclose(chained_motion[-7:],chained_motion[-1],atol=1e-5)
    assert np.allclose(chained_motion[-1,:,:3],next_window[0,:,:3],atol=1e-4)
    app.duplicate_target(1)
    assert len(app.pose_entries)==3
    assert np.allclose(app.entry.preview_pose.numpy(),pose,atol=1e-5)
    app.entry.manual_window[0,1,0]+=.01
    assert not np.array_equal(app.entry.manual_window,app.pose_entries[1].manual_window)
    app.entry.manual_window[0,1,0]-=.01
    app.reset_bone_rotation()
    reference=app.skeleton.reference_local_transforms.numpy()
    assert np.allclose(app.entry.preview_pose.numpy()[j,3:],reference[j,3:],atol=1e-5)
    app.history()
    app.remove_target()
    app.selected_index=1
    app.entry.duration_seconds=2.5
    app.save_project(folder/'timed.mbstudio.json')
    app.load_project(folder/'timed.mbstudio.json')
    assert app.entry.duration_seconds==2.5
    app.start_generation()
    while app.busy:
        app.step(.016);app.render()
        if app.error:raise RuntimeError(app.error)
        time.sleep(.001)
    assert len(app.timeline_cpu)==76
    assert abs(app.timeline.duration-2.5)<1e-5
    assert np.allclose(app.timeline_cpu[-1,:,:3],pose[:,:3],atol=1e-4)
    app.timeline_time=0.;app.preview_speed=2.
    before=app.timeline_cpu.copy()
    app.step(.1)
    assert abs(app.timeline_time-.2)<1e-5
    assert np.array_equal(app.timeline_cpu,before)
    payload=app.export_payload()
    app.preview_speed=1.
    assert abs(app.transport_duration-2.5)<1e-5
    app.seek_transport(.8,pause=True)
    app.step(.1)
    assert abs(app.timeline_time-.8)<1e-5
    app.toggle_transport();app.step(.1)
    assert abs(app.timeline_time-.9)<1e-5
    app.stop_transport()
    assert app.timeline_time==0. and not app.preview_playing
    import wave
    audio_path=folder/'audio-test.wav'
    with wave.open(str(audio_path),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(44100)
        wav.writeframes(b'\0\0'*44100*2)
    app.audio.load(audio_path)
    assert abs(app.transport_duration-2.)<.02
    app.audio.seek(.4);app.audio_sync=True
    app.step(.016);app.render()
    assert abs(app.timeline_time-.4)<.02
    app.audio.seek(1.2);app.step(.016)
    assert abs(app.timeline_time-1.2)<.02
    app.audio.pause();app.step(.2)
    assert abs(app.timeline_time-1.2)<.02
    from .studio_video import export_video
    export_video(app,folder/'reference.mp4',include_audio=True)
    import imageio_ffmpeg
    video=imageio_ffmpeg.read_frames(str(folder/'reference.mp4'),pix_fmt='rgb24')
    metadata=next(video)
    assert abs(metadata['duration']-2.5)<.1,metadata
    first=np.frombuffer(next(video),dtype=np.uint8).copy()
    assert first.std()>5
    last=first
    for frame in video:last=np.frombuffer(frame,dtype=np.uint8).copy()
    assert np.mean(np.abs(first.astype(float)-last.astype(float)))>.05
    from PIL import Image
    Image.fromarray(first.reshape(metadata['size'][1],metadata['size'][0],3)).save(folder/'reference-first.png')
    app.audio_sync=False;app.audio.close()
    np.savez_compressed(folder/'export_snapshot.npz',**payload)
    export_fbx(payload,folder/'test_motion.fbx')
    export_fbx(payload,folder/'test_inplace.fbx',inplace=True,include_mesh=False)
    from .studio_locales import LANGUAGES
    for _,language in LANGUAGES:
        app.set_language(language)
        app.show_manual=True
        app.show_licenses=True
        app.license_index=5
        app.render();app.render()
        app.manual_search='VMD'
        app.render()
    app.show_manual=False
    app.show_licenses=False
    result=dict(joints=app.skeleton.num_joints,frames=len(app.timeline_cpu),
                generation_seconds=app.generation_seconds,rendered_frames_during_generation=rendered,
                animation_duration_seconds=app.timeline.duration,
                reference_video_duration_seconds=metadata['duration'],reference_video_size=metadata['size'],
                final_position_error=p_error,final_quaternion_error=q_error,ik_position_error=ik_error,
                checks=['pose edit persists','undo and redo','pose save/load','project save/load',
                        'IK keeps bone lengths','actual SOMA generation','viewport during generation',
                        'target endpoint match','multi-target chaining','hold pose interval',
                        'independent target duplication','bone rest reset and undo','2.5-second retiming',
                        'duration setting save/load','preview speed leaves export unchanged',
                        'audio seek and pause synchronization','current-camera MP4 rendering with audio',
                        'mirror pose preserves root and supports undo','motion-only shared transport',
                        'five-language UI and searchable manual rendering',
                        'bundled FBX SDK exporter with skin','in-place FBX without mesh',
                        'five-language Autodesk attribution and license viewer'])
    (folder/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('STUDIO_VERIFICATION '+json.dumps(result))
    from .studio_verify_motion import verify_authored_motion
    verify_authored_motion(app,folder)
    from .studio_verify_ue import verify_ue_bridge
    verify_ue_bridge(app,folder)

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
