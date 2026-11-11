"""Plan default interactions on CPU; apply results on the UI thread only."""
from types import SimpleNamespace
import copy,time
import numpy as np
from .studio_scene import SceneAuthoring


class ArraySnapshot:
    def __init__(self,values):self.values=np.asarray(values).copy()
    def numpy(self):return self.values


class CPUPlanner(SceneAuthoring):
    def _scene_entry(self,**values):return {'stage':values}
    def changed(self,*args):pass
    def scene_base_signature(self):return self.source_signature


def snapshot(app,generate):
    bases=[]
    for entry in app.pose_entries:
        if not getattr(entry,'scene_generated',False):
            bases.append(SimpleNamespace(id=entry.id,scene_generated=False,sampled_poses=ArraySnapshot(entry.sampled_poses.numpy())))
    return dict(base=bases,environment=copy.deepcopy(app.environment),signature=app.scene_base_signature(),revision=getattr(app,'_autosave_revision',0),generate=generate,
                skeleton=SimpleNamespace(joint_names=list(app.skeleton.joint_names),_np_parent_indices=app.skeleton._np_parent_indices.copy(),num_joints=app.skeleton.num_joints),language=app.language)


def _compute(data):
    started=time.perf_counter();planner=CPUPlanner();planner.pose_entries=data['base'];planner.environment=data['environment'];planner.skeleton=data['skeleton'];planner.language=data['language'];planner.selected_index=0;planner.source_signature=data['signature']
    planner.plan_environment()
    return dict(plan=planner.pose_entries,environment=data['environment'],signature=data['signature'],revision=data['revision'],generate=data['generate'],seconds=time.perf_counter()-started)


def compute(data):
    """A native planner failure must never terminate the open editor."""
    from concurrent.futures import ProcessPoolExecutor
    from concurrent.futures.process import BrokenProcessPool
    from multiprocessing import get_context
    from .studio_launcher import scene_worker_init
    started=time.perf_counter()
    try:
        with ProcessPoolExecutor(max_workers=1,mp_context=get_context('spawn'),initializer=scene_worker_init) as worker:
            result=worker.submit(_compute,data).result()
    except BrokenProcessPool as exc:
        raise RuntimeError('Obstacle calculation stopped unexpectedly. Your targets and generated animation have been retained. Details: user_data/scene-worker.log / 障害物の計算プロセスが異常終了しました。ターゲットと生成済みモーションは保持されています。') from exc
    result['seconds']=time.perf_counter()-started
    return result


def apply(app,result):
    if app.scene_base_signature()!=result['signature'] or app.environment!=result['environment'] or getattr(app,'_autosave_revision',0)!=result['revision']:
        app.status='Scene changed during planning. Rebuild the environment route / 計算中に編集されたため、環境経路を再構築してください。';return False
    base={e.id:e for e in app.pose_entries if not getattr(e,'scene_generated',False)};planned=[]
    for item in result['plan']:
        planned.append(app._scene_entry(**item['stage']) if isinstance(item,dict) else base[item.id])
    app.pose_entries=planned;app.selected_index=min(app.selected_index,len(planned)-1);app.changed('Environment route ready / 環境経路を作成しました。')
    app.scene_plan_stale=False;app.scene_plan_signature=app.scene_base_signature()
    if result['generate']:app.start_generation()
    return True

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
