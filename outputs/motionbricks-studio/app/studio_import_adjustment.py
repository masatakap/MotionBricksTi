"""Select how a converted motion participates in Studio without editing its keys."""
import numpy as np

from .studio_interval import profile, validate_settings


PURPOSES = ('move', 'transit', 'action', 'full', 'pose')


def suggested_purpose(name):
    from .studio_library import infer_genre

    name = name.casefold()
    if infer_genre(name) == 'dance':
        return 'full'
    if any(word in name for word in ('vault', 'jump', 'duck_under', '飛び越', 'くぐ')):
        return 'transit'
    if any(word in name for word in ('walk', 'run', 'jog', 'crouch', 'zombie', 'strafe', '歩行', '歩く', '走る')):
        return 'move'
    return 'action'


def suggested_range(poses, purpose):
    last = len(poses) - 1
    if purpose != 'move' or last < 28:
        return 0, last
    speed = np.linalg.norm(np.diff(poses[:, 0, :2], axis=0), axis=1) * 30
    smoothed = np.convolve(np.pad(speed, 3, mode='edge'), np.ones(7) / 7, mode='valid')
    moving = np.flatnonzero(smoothed >= max(.2, .6 * np.quantile(smoothed, .75)))
    if len(moving) and moving[-1] - moving[0] >= 25:
        return int(moving[0]), min(last, int(moving[-1]) + 1)
    return 0, last


def apply_adjustment(track, adjustment):
    if adjustment is None:
        return
    purpose, start, end, continue_after = adjustment
    if purpose not in PURPOSES or type(continue_after) is not bool:
        raise ValueError('Invalid motion import purpose')
    if purpose == 'full':
        start, end = 0, track['last_frame']
    interval = dict(mode='pose' if purpose in ('pose', 'full') else 'action' if purpose == 'transit' else purpose,
                    start=start, end=end)
    track.update(interval=interval, sample_frame=start, playback='full_clip' if purpose == 'full' else 'conditioning',
                 import_adjustment=dict(purpose=purpose, continue_after=continue_after))
    validate_settings(track)


def suggest_cycle(poses, metadata, names, start, end):
    track = dict(last_frame=len(poses) - 1, provenance=metadata,
                 keys=[dict(frame=i, pose=pose) for i, pose in enumerate(poses)])
    apply_adjustment(track, ('move', start, end, True))
    result = profile(dict(track=track, settings=validate_settings(track), names=names))
    return result['source_range'] if result['phase_score'] is not None else None


def initial_placement(track):
    offset = -np.asarray(track['keys'][track['sample_frame']]['pose'][0][:2])
    return [float(offset[0]), float(offset[1]), 0, 0, 0, 0, 1]

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
