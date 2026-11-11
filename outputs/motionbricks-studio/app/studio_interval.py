"""Per-interval motion conditions, phased locomotion and bounded one-shot actions."""
import copy,math
import numpy as np
from scipy.spatial.transform import Rotation
from .studio_motion_data import sample_track
from .studio_data import root_transform,retime_motion

MODES=('auto','pose','move','action')
CONTINUOUS=('walk','jog','run','skip','crouch','combat','injured','zombie','prop_')


def settings(track):
    start,end=default_range(track)
    if not isinstance(track.get('interval',{}),dict):raise ValueError('Invalid interval motion settings')
    return dict(dict(mode='auto',start=start,end=end,speed=0.,repeats=1,automatic_phase=True,stop=False),**track.get('interval',{}))


def default_range(track):
    """Detect sitting/standing events; retain margins on both sides."""
    end=track['last_frame'];role=track.get('role_id') or track.get('provenance',{}).get('role_id')
    if role not in ('sit_down','stand_up'):return 0,end
    z=np.interp(np.arange(end+1),[k['frame'] for k in track['keys']],[k['pose'][0][2] for k in track['keys']])
    amplitude=abs(float(z[-1]-z[0]))
    if amplitude<.15:return 0,end
    progress=(z-z[0])/(z[-1]-z[0]);start=np.where(progress>.08)[0];finish=np.where(progress>.95)[0]
    if not len(start) or not len(finish):return 0,end
    return max(0,int(start[0])-6),min(end,max(int(start[0])+3,int(finish[0])+6))


def validate_settings(track):
    s=settings(track)
    if s['mode'] not in MODES:raise ValueError('Invalid interval motion mode')
    if type(s['start']) is not int or type(s['end']) is not int or not 0<=s['start']<=s['end']<=track['last_frame'] or s['end']-s['start']<3:raise ValueError('Interval motion range needs at least four frames')
    if not np.isfinite(s['speed']) or not 0<=s['speed']<=12:raise ValueError('Invalid interval motion speed')
    if type(s['repeats']) is not int or not 1<=s['repeats']<=100:raise ValueError('Invalid action repeat count')
    if type(s['automatic_phase']) is not bool:raise ValueError('Invalid automatic phase setting')
    if type(s['stop']) is not bool:raise ValueError('Invalid interval stop setting')
    return s


def mode(track):
    if not track or track.get('playback') in ('full_clip','scene_exact'):return 'pose'
    s=settings(track)
    if s['mode']!='auto':return s['mode']
    role=str(track.get('role_id') or track.get('provenance',{}).get('role_id','')).lower()
    # Only identifiable motion clips are enabled automatically. Hand-authored
    # poses and dances keep their explicit playback controls.
    if track.get('genre')=='dance':return 'pose'
    if role:
        return 'move' if role.startswith(CONTINUOUS) else 'action'
    if track.get('origin') in ('generated','imported'):
        name=(str(track.get('display_name',''))+' '+str(track.get('seed_source',''))).lower()
        if any(word in name for word in ('dance','ダンス','舞蹈')):return 'pose'
        if any(word in name for word in ('walk','jog','run','zombie','crouch','combat','歩行','歩く','走る','ゾンビ')):return 'move'
    return 'pose'


def payload(track,names=None):
    if mode(track)!='move':return None
    s=validate_settings(track)
    return dict(track=copy.deepcopy(track),settings=s,names=list(names) if names is not None else None)


def action_frames(track,names=None):
    s=validate_settings(track)
    p=np.stack([sample_track(track,i) for i in range(s['start'],s['end']+1)])
    if s['repeats']==1:return p
    from .studio_scene_kimodo import bridge
    body={'Hips','Spine1','Spine2','Chest'}|{side+bone for side in ('Left','Right') for bone in ('Arm','ForeArm','Leg','Shin','Foot')}
    joints=[i for i,n in enumerate(names or []) if n in body] or list(range(len(p[0])))
    dot=np.abs(np.sum(p[0,joints,3:]*p[-1,joints,3:],axis=-1))
    if np.degrees(2*np.arccos(np.clip(dot,0,1))).max()>60:
        raise ValueError('Action endpoints do not form a repeatable cycle. Add a reset action or change the range / 開始・終了姿勢が違うため繰り返せません。立つ等の戻り動作を追加するか、使用範囲を調整してください。')
    parts=[p];previous=p
    for _ in range(s['repeats']-1):
        rel=(Rotation.from_quat(previous[-1,0,3:])*Rotation.from_quat(p[0,0,3:]).inv()).as_matrix()
        yaw=Rotation.from_euler('z',math.atan2(rel[1,0],rel[0,0]))
        shift=previous[-1,0,:2]-yaw.apply(p[0,0,:3])[:2]
        following=root_transform(p,np.r_[shift,0.,yaw.as_quat()])
        parts.extend((bridge(previous[-1],following[0]),following));previous=following
    return np.concatenate(parts)


def profile(spec):
    """Select a repeatable phase using body pose, velocity and foot phase.

    This only selects source conditions. No source curve is rewritten or
    concatenated at a loop seam in the generated animation.
    """
    t=spec['track'];s=spec['settings'];a,b=s['start'],s['end']
    keys=t['keys']
    p=np.stack([key['pose'] for key in keys[a:b+1]]) if len(keys)==t['last_frame']+1 else np.stack([sample_track(t,i) for i in range(a,b+1)])
    root=p[:,0,:3];velocity=np.diff(root[:,:2],axis=0)*30
    speed=float(np.median(np.linalg.norm(velocity,axis=1)))
    travel=root[-1,:2]-root[0,:2]
    if np.linalg.norm(travel)<.05:
        travel=np.mean(velocity,axis=0)
    if np.linalg.norm(travel)<.01:travel=np.array([0.,-1.])
    direction=travel/np.linalg.norm(travel)
    # Prefer body/leg phase rather than high-frequency captured finger noise.
    q=p[:,:,3:]
    names=spec.get('names')
    if names:
        body={'Hips','Spine1','Spine2','Chest','Head'}|{side+bone for side in ('Left','Right') for bone in ('Shoulder','Arm','ForeArm','Hand','Leg','Shin','Foot','ToeBase')}
        joints=[i for i,name in enumerate(names) if name in body]
    else:joints=list(range(len(q[0])))
    contacts=np.asarray(t.get('provenance',{}).get('foot_contacts',[]))
    if contacts.ndim==2 and len(contacts)==t['last_frame']+1:contacts=contacts[a:b+1]
    else:contacts=None
    best=None
    if s['automatic_phase'] and len(p)>=25:
        body_q=q[:,joints]
        for length in range(18,min(76,len(p)-4)):
            starts=np.arange(0,len(p)-length-3,2)
            ends=starts+length
            dot=np.abs(np.sum(body_q[starts]*body_q[ends],axis=-1))
            angle=2*np.arccos(np.clip(dot,0,1))
            dv=velocity[starts]-velocity[ends]
            scores=np.mean(angle**2,axis=1)+4*(root[starts,2]-root[ends,2])**2+.015*np.sum(dv**2,axis=1)
            if contacts is not None:scores+=.4*np.mean(contacts[starts]!=contacts[ends],axis=1)
            if t.get('import_adjustment',{}).get('purpose')=='move' and speed>.25:
                # A static tail is a good pose match but a poor gait cycle.
                endpoint_speed=np.minimum(np.linalg.norm(velocity[starts],axis=1),np.linalg.norm(velocity[ends],axis=1))
                scores+=np.maximum(0,.65-endpoint_speed/speed)**2
            index=int(np.argmin(scores));score=float(scores[index])
            if best is None or score<best[0]:best=(score,int(starts[index]),int(ends[index]))
    if best is not None:_,lo,hi=best
    else:
        lo=int(np.clip(t['sample_frame']-a,0,len(p)-4));hi=max(lo+1,len(p)-3)
    return dict(poses=p,start=lo,end=hi,speed=float(s['speed'] or max(.25,min(6.,speed))),source_speed=max(.25,speed),track=t,range_origin=a,direction=direction,joints=joints,phase_score=None if best is None else best[0],source_range=[a+lo,a+hi],frame_count=len(p))


def phase_window(p,seconds,point,direction):
    rate=p['speed']/p['source_speed']
    frame=p['start']+(seconds*30*rate) % max(1,p['end']-p['start'])
    if abs(rate-1)<1e-6:
        frame=min(int(frame+1e-6),len(p['poses'])-4);w=p['poses'][frame:frame+4].copy()
    else:
        frame=max(0,min(frame,len(p['poses'])-1-3*rate))
        w=np.stack([sample_track(p['track'],p['range_origin']+frame+i*rate) for i in range(4)])
    angle=math.atan2(direction[1],direction[0])-math.atan2(p['direction'][1],p['direction'][0])
    yaw=Rotation.from_euler('z',angle);old=w[0,0,:2].copy()
    w[:,0,:2]-=old
    w=root_transform(w,np.r_[point,0.,yaw.as_quat()])
    # Keep the clip's phase and pose but adapt ground speed to the interval.
    # The source may veer sideways (notably generated Kimodo clips). Its
    # instantaneous root heading must not steer the requested straight route.
    w[:,0,:2]=np.asarray(point)+np.arange(4)[:,None]/30*p['speed']*direction
    return w


def match_phase(p,context,direction):
    """Match the incoming four poses instead of restarting at each waypoint."""
    joints=[j for j in p['joints'] if j!=0] or list(range(1,len(context[0])))
    if not joints:return 0.
    rate=p['speed']/p['source_speed'];best=None
    for frame in range(p['start'],p['end']):
        seconds=(frame-p['start'])/(30*rate)
        w=phase_window(p,seconds-3/30,context[-1,0,:2],direction)
        dot=np.abs(np.sum(w[:,joints,3:]*context[:,joints,3:],axis=-1))
        angles=2*np.arccos(np.clip(dot,0,1))
        score=float(np.mean(angles**2*np.array([1.,1.,2.,3.])[:,None]))
        if best is None or score<best[0]:best=(score,seconds)
    return best[1] if best else 0.


def generate_interval(infer,context,destination,spec,*,destination_spec=None,num=4,hold=0,duration=0.,stop=False):
    """Repeated short inference, carrying actual output as the next context."""
    p=profile(spec);other=profile(destination_spec) if destination_spec else None
    origin=context[-1,0,:2].copy();goal=destination[0,0,:2].copy();vector=goal-origin;distance=float(np.linalg.norm(vector))
    if distance<.05:return None,None
    direction=vector/distance
    phase=match_phase(p,context,direction);other_phase=match_phase(other,context,direction) if other is not None else 0.
    first=phase_window(p,phase,origin,direction)
    relative=(Rotation.from_quat(first[0,0,3:])*Rotation.from_quat(context[-1,0,3:]).inv()).as_matrix()
    turn_degrees=abs(math.degrees(math.atan2(relative[1,0],relative[0,0])))
    # Ordinary route corners turn while walking. Only a near reversal needs
    # an explicit stationary alignment (e.g. backward locomotion).
    turn_seconds=min(.9,max(.6,turn_degrees/180)) if turn_degrees>135 else 0.
    if duration>0:turn_seconds=min(turn_seconds,duration*.3)
    if duration>0 and round(duration*30)<3:raise ValueError('Continuous movement needs at least 0.1 seconds / 継続移動の尺は0.1秒以上にしてください。')
    total_seconds=(round(duration*30)-round(turn_seconds*30))/30 if duration>0 else distance/p['speed']
    if duration>0:
        if distance/total_seconds>12:raise ValueError('Increase the interval duration / 移動距離に対して区間の尺を長くしてください。')
        p['speed']=distance/total_seconds
        if other is not None:other['speed']=p['speed']
        phase=match_phase(p,context,direction)
        if other is not None:other_phase=match_phase(other,context,direction)
    # Generate whole gait cycles where possible. Fixed 0.8s cuts repeatedly
    # split a walking cycle in half and make the model correct the same foot.
    cycle_seconds=(p['end']-p['start'])/30*p['source_speed']/p['speed']
    step_seconds=max(.55,min(1.6,cycle_seconds))
    if total_seconds/step_seconds>2001:raise ValueError('Split this very long route into more targets.')
    ends=list(np.arange(step_seconds,total_seconds-.35,step_seconds))+[total_seconds]
    count=len(ends)
    if count>2000:raise ValueError('Split this very long route into more targets.')
    chunks=[];events=[];seconds=0.
    if turn_seconds:
        first[:,0,:2]=origin
        turning=infer(context,first,1,turn_seconds)
        turning=retime_motion(turning,max(4,round(turn_seconds*30)+1))
        chunks.append(turning);context=turning[-4:];seconds=(len(turning)-1)/30
        phase=match_phase(p,context,direction)-seconds
        if other is not None:other_phase=match_phase(other,context,direction)-seconds
        events.append(dict(part=0,parts=count,alignment_turn_degrees=turn_degrees,frames=len(turning),target_poses=1,source_range=p['source_range']))
    previous_end=0.
    for index,end_seconds in enumerate(ends,1):
        last=index==count;fraction=end_seconds/total_seconds;point=origin+vector*fraction
        active=other if other is not None and fraction>=.8 else p
        segment_seconds=end_seconds-previous_end
        window=phase_window(active,(other_phase if active is other else phase)+seconds+segment_seconds,point,direction)
        # Arrival to an action/pose is a separate final transition. Identical
        # moving clips keep their phase instead of snapping to the same pose.
        if last and (other is None or stop or hold or num==1):window=destination.copy()
        target_num=1 if last and (stop or hold or num==1) else 4
        frames=infer(context,window,target_num,segment_seconds)
        end=round(end_seconds*30);begin=round(previous_end*30);previous_end=end_seconds
        frames=retime_motion(frames,max(4,end-begin+1))
        if len(frames)<4:raise ValueError('Continuous generation needs at least four output frames')
        seconds+=(len(frames)-1)/30
        chunks.append(frames if not chunks else frames[1:]);context=frames[-4:]
        events.append(dict(part=index,parts=count,source_range=active['source_range'],target_xy=point.tolist(),target_poses=target_num,frames=len(frames)))
    return np.concatenate(chunks),dict(parts=events,source_range=p['source_range'],speed_m_s=p['speed'],phase_score=p['phase_score'],seconds=seconds)


LABELS={
'ja':('区間での動作','自動','ポーズ条件のみ','この動作で移動を続ける','到着後に動作を実行','使用開始フレーム','使用終了フレーム','移動速度 m/s（0=自動）','実行回数','周期を自動選択','移動中は開始側の動作を維持し、到着前に次の動作へ切り替えます。保持時間を指定した地点では停止します。'),
'en':('Interval motion','Automatic','Pose conditions only','Continue this motion while moving','Perform action on arrival','First source frame','Last source frame','Speed m/s (0=auto)','Action repeats','Select cycle automatically','Keep the departure motion while travelling; switch near arrival. Hold frames stop the character.'),
'es':('Movimiento del tramo','Automático','Solo condiciones de pose','Mantener movimiento al desplazarse','Acción al llegar','Primer fotograma','Último fotograma','Velocidad m/s (0=auto)','Repeticiones','Seleccionar ciclo automáticamente','Mantiene el movimiento de salida y cambia al llegar. Los fotogramas de espera detienen al personaje.'),
'fr':('Mouvement du trajet','Automatique','Conditions de pose seules','Conserver ce mouvement en déplacement','Action à l’arrivée','Première image','Dernière image','Vitesse m/s (0=auto)','Répétitions','Choisir le cycle automatiquement','Conserve le mouvement de départ et change près de l’arrivée. Le maintien arrête le personnage.'),
'zh':('区间动作','自动','仅姿势条件','移动时持续此动作','到达后执行动作','起始帧','结束帧','速度 m/s（0=自动）','执行次数','自动选择周期','移动中保持出发动作，在接近目标时切换。设置停留帧会停止角色。')}


def draw_controls(app,ui):
    t=getattr(app.entry,'motion_track',None)
    if not t or t.get('playback') in ('full_clip','scene_exact') or t.get('genre')=='dance':return
    labels=LABELS.get(app.language,LABELS['en']);s=settings(t)
    if not ui.collapsing_header(labels[0]+'###interval_motion'):return
    changed,index=ui.combo(labels[0]+'###interval_mode',MODES.index(s['mode']),list(labels[1:5]))
    dirty=changed;s['mode']=MODES[index]
    effective=mode(dict(t,interval=s,display_name=getattr(app.entry,'name','')))
    if effective!='pose':
        for key,label in (('start',labels[5]),('end',labels[6])):
            changed,value=ui.input_int(label+'###interval_'+key,s[key]);dirty|=changed;s[key]=max(0,min(t['last_frame'],value))
    if s['end']-s['start']<3:s['start']=max(0,min(s['start'],t['last_frame']-3));s['end']=max(s['start']+3,s['end'])
    if effective=='move':
        changed,s['speed']=ui.slider_float(labels[7]+'###interval_speed',s['speed'],0.,6.);dirty|=changed
        changed,s['automatic_phase']=ui.checkbox(labels[9]+'###interval_phase',s['automatic_phase']);dirty|=changed
    if effective=='action':
        changed,value=ui.input_int(labels[8]+'###interval_repeats',s['repeats']);s['repeats']=max(1,min(100,value));dirty|=changed
    stop_label={'ja':'この地点で停止','en':'Stop at this target','es':'Detenerse en este destino','fr':'S’arrêter à cette cible','zh':'在此目标停止'}.get(app.language,'Stop at this target')
    changed,s['stop']=ui.checkbox(stop_label+'###interval_stop',s['stop']);dirty|=changed
    ui.text_wrapped(labels[10])
    ui.text_unformatted(labels[2 if effective=='pose' else 3 if effective=='move' else 4])
    if dirty:app.remember();t['interval']=s;app.changed()


GUIDES={
'ja':('区間の動作を維持する・単発動作を実行する','全尺再生OFFの動作には「区間での動作」が使えます。自動では歩行・走行・しゃがみ・戦闘・負傷・ゾンビ等を移動動作として扱い、開始側の動作を次地点まで短い生成の繰り返しで維持します。次地点で別の移動動作を選ぶと、到着前に切り替えます。\n\n「ポーズ条件のみ」は従来の姿勢条件です。移動系以外は自動で到着後に指定範囲の動作を1回実行します。「使用開始／終了フレーム」「実行回数」で範囲と回数を変更できます。座る・立つは骨盤の動きから使用区間を自動選択します。素材ファイル自体は切り詰めません。\n\n動作編集、または右のターゲット編集で「区間での動作」を開いて設定してください。移動速度0は素材から推定します。周期の自動選択は身体の姿勢・速度・足の接触を使い、指の揺れで選びません。「この地点で停止」または保持時間の指定で、到着時だけ停止条件を使います。途中の目標は動作条件を保ちます。区間の尺を指定した場合は、その尺を移動区間全体へ配分します。\n\n全尺再生ONは従来どおりクリップを一度そのまま再生する指定です。ダンスはそのまま使えます。設定はプロジェクトと保存動作へ保持され、Undo/Redoも使えます。更新前の生成結果は自動上書きしません。既存プロジェクトは読み込み後「モーションを生成」で新しい処理を適用してください。生成結果の自然さ・接地はモデルと素材により確認が必要です。'),
'en':('Continuous interval motion and one-shot actions','With entire-motion playback OFF, open Interval motion in the target or motion editor. Automatic keeps walking, running, crouching, combat, injured and zombie styles throughout the route by repeated short generation. A different movement at the next target switches near arrival.\n\nPose conditions only restores endpoint conditioning. Other automatic roles perform the selected action range on arrival. Choose first/last frames and repeat count; sitting/standing ranges are detected from pelvis movement without trimming library files. Speed 0 estimates source speed. Automatic cycle selection uses body pose, velocity and foot contacts, excluding finger noise. Stop at this target or hold frames stops only on arrival. Transition duration applies to the whole interval.\n\nEntire-motion ON and dances keep their existing playback. Settings support project/motion saving and Undo/Redo. Existing generated results stay intact; regenerate an opened project to apply the new behavior. Inspect naturalness and ground contact on the actual model.'),
'es':('Movimiento continuo y acciones únicas','Con reproducción completa OFF, abra Movimiento del tramo en el editor. Automático conserva caminar, correr, agacharse, combate, lesión y zombi mediante generaciones cortas repetidas. Cambia al movimiento siguiente cerca de la llegada.\n\nSolo condiciones de pose restaura el método anterior. Otros roles ejecutan el rango elegido al llegar: seleccione fotogramas y repeticiones. Sentarse y levantarse detectan su rango por la pelvis; no recortan el archivo. Velocidad 0 usa la del original. El ciclo usa cuerpo, velocidad y contactos de pies, excluyendo ruido de dedos. Detenerse o esperar solo afecta a la llegada. La duración se reparte por todo el tramo.\n\nLa reproducción completa y los bailes se conservan. Los ajustes se guardan y admiten deshacer. Regenere proyectos existentes para aplicar los cambios. Compruebe calidad y contacto en el modelo real.'),
'fr':('Mouvement continu et actions ponctuelles','Avec lecture intégrale OFF, ouvrez Mouvement du trajet. Automatique conserve marche, course, accroupissement, combat, blessure et zombie par générations courtes répétées. Le mouvement suivant intervient près de l’arrivée.\n\nConditions de pose seules rétablit l’ancien mode. Les autres rôles exécutent la plage choisie à l’arrivée : réglez images et répétitions. Les plages assise/relevé sont détectées par le bassin sans couper les fichiers. Vitesse 0 utilise celle de la source. Le cycle se base sur corps, vitesse et contacts des pieds, sans bruit des doigts. Arrêt ou maintien s’applique seulement à l’arrivée. La durée couvre le trajet entier.\n\nLa lecture intégrale et les danses sont conservées. Les réglages sont enregistrés et annulables. Régénérez les projets existants. Vérifiez qualité et contact sur le modèle réel.'),
'zh':('持续区间动作与单次动作','完整播放OFF时，在目标或动作编辑器中展开“区间动作”。自动模式通过重复生成短区间，保持步行、跑步、蹲行、战斗、受伤或僵尸动作，并在接近目标时切换到下一个移动动作。\n\n“仅姿势条件”使用原来的端点条件方式。其他自动角色在到达后执行指定区间，可调整起止帧与次数。坐下和站起根据骨盆运动自动选取区间，不裁剪原始文件。速度0使用素材估计值。自动周期依据身体、速度及脚部接触，不使用手指抖动。停止选项或停留帧仅在到达时停止，区间时长分配到整个移动过程。\n\n完整播放和舞蹈保持原有方式。设置支持保存与撤销。已有生成结果不覆盖，打开旧项目后需重新生成。请在实际模型上检查自然度和接地。')}

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
