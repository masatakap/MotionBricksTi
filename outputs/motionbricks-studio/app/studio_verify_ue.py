"""GPU app-side bridge and full generated-project recovery verification."""
import json,gzip
from pathlib import Path
import numpy as np
from .studio_data import read_extras
from .studio_ue_pose import atomic_json


def verify_ue_bridge(app,folder):
    app.preview_playing=False
    frames=app.timeline_cpu.copy()
    app.save_project(folder/'ue-generated-project.mbstudio.json')
    app.load_project(folder/'ue-generated-project.mbstudio.json')
    np.testing.assert_array_equal(frames,app.timeline_cpu)
    assert app.timeline is not None and not app.preview_playing
    extras=read_extras(folder/'ue-generated-project.mbstudio.json')
    assert extras['generated_motion']['fps']==30
    app.connect_ue();app.show_generated=False
    sent=app.entry.preview_pose.numpy().copy()
    original=app.entry;count=len(app.pose_entries)
    app.step_ue_bridge()
    packet=json.loads((app.ue_directory()/'frame.json').read_text())
    assert packet['connected'] and len(packet['pose'])==app.skeleton.num_joints
    request=app.ue_pose_request
    atomic_json(app.ue_directory()/'response.json',dict(schema=request['schema'],version=1,
        request_id=request['request_id'],soma_component=request['pose'],mapping={n:n for n in request['names']}))
    app.receive_ue_pose(True)
    assert len(app.pose_entries)==count+1 and app.entry is not original
    np.testing.assert_allclose(app.entry.preview_pose.numpy(),sent,atol=1e-5)
    app.timeline_stale=False;app.audio.path=None
    app.bake_to_ue()
    with gzip.open(app.ue_directory()/'bake.json.gz','rt',encoding='utf-8') as stream:bake=json.load(stream)
    assert len(bake['frames'])==len(frames) and bake['fps']==30
    app.disconnect_ue()
    assert not json.loads((app.ue_directory()/'frame.json').read_text())['connected']
    result=dict(generated_frames_preserved=len(frames),pose_exchange=True,full_frame_bake=True,
                new_target_does_not_replace_source=True,coordinate_roundtrip_error=float(np.max(abs(app.entry.preview_pose.numpy()-sent))))
    (folder/'ue-app-verification.json').write_text(json.dumps(result,indent=2))
    print('STUDIO_UE_APP_VERIFICATION '+json.dumps(result))

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
