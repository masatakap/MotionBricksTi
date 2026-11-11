"""SOMA finger-only presets, independent of wrist and body motion."""
import json

import numpy as np


SUFFIX = '.handpose.json'
FINGERS = ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky')
LANGUAGES = ('en', 'ja', 'es', 'fr', 'zh')
SIDES = {
    'Left': ('Left', '左手', 'Izquierda', 'Main gauche', '左手'),
    'Right': ('Right', '右手', 'Derecha', 'Main droite', '右手'),
}
GESTURES = {
    'Fist': ('Fist', 'グー', 'Puño', 'Poing', '握拳'),
    'Scissors': ('Scissors', 'チョキ', 'Tijeras', 'Ciseaux', '剪刀手'),
    'Open': ('Open', 'パー', 'Abierta', 'Ouverte', '张开'),
    'HalfOpen': ('Half-open', '半開き', 'Semiabierta', 'Mi-ouverte', '半张开'),
}


def finger_bones(side):
    return tuple(f'{side}Hand{finger}{i}' for finger in FINGERS
                 for i in range(1, 4 if finger == 'Thumb' else 5))


def display_name(path, language):
    name = path.name[:-len(SUFFIX)]
    side, _, gesture = name.removeprefix('Hand_Pose_').partition('_')
    if side not in SIDES or gesture not in GESTURES:
        return name
    index = LANGUAGES.index(language) if language in LANGUAGES else 0
    return f'{SIDES[side][index]} · {GESTURES[gesture][index]}'


def read_hand_pose(path, joint_names):
    data = json.loads(path.read_text(encoding='utf8'))
    if not isinstance(data, dict) or data.get('schema') != 'motionbricks-soma-hand-pose-v1':
        raise ValueError('Invalid SOMA hand pose')
    side = data.get('side')
    if side not in ('Left', 'Right'):
        raise ValueError('Invalid hand pose side')
    bones = finger_bones(side)
    rotations = data.get('local_rotations')
    if not isinstance(rotations, dict) or set(rotations) != set(bones):
        raise ValueError('Incomplete or invalid finger bone set')
    index = {name: i for i, name in enumerate(joint_names)}
    if any(bone not in index for bone in bones):
        raise ValueError('This skeleton does not have the required SOMA finger bones')
    values = np.asarray([rotations[bone] for bone in bones], dtype=np.float32)
    if values.shape != (len(bones), 4) or not np.isfinite(values).all():
        raise ValueError('Invalid finger rotations')
    norm = np.linalg.norm(values, axis=1, keepdims=True)
    if np.any(np.abs(norm - 1) > .01):
        raise ValueError('Invalid finger quaternion norm')
    return [index[bone] for bone in bones], values / norm

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
