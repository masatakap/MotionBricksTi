"""Persistent Studio recovery preferences."""
import json
from pathlib import Path


def load_autosave_enabled(path):
    try:
        value=json.loads(Path(path).read_text(encoding='utf-8')).get('autosave_enabled',True)
        return value if isinstance(value,bool) else True
    except (OSError,ValueError,AttributeError):return True


def save_autosave_enabled(path,enabled):
    path=Path(path)
    try:data=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):data={}
    if not isinstance(data,dict):data={}
    data['autosave_enabled']=bool(enabled)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
