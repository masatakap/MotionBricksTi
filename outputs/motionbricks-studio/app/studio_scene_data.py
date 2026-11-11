"""CPU scene geometry and conservative planar routing, in Studio meters/Z-up."""
import copy,heapq,math,uuid
import numpy as np

ACTIONS=('auto','avoid','jump_0_5m','jump_0_75m','avoidance','sit')
PRESETS={
    'jump_0_5m':([.6,.6,.5],.25),
    'jump_0_75m':([2.,.3,.75],.375),
    'avoidance':([.5,.5,1.],1.95),
    'sit':([.4,.4,.4],.2),
    'avoid':([1.,1.,2.],1.),
}

def new_box(action='avoid',position=(0,-3,0)):
    size,z=PRESETS[action]
    p=list(position);p[2]+=z
    return dict(id=uuid.uuid4().hex,name=action,position=p,size=list(size),yaw=0.,action=action,sequence=0,hold=2.,enabled=True)

def validate_scene(value):
    if not isinstance(value,dict) or value.get('version',1)!=1:raise ValueError('Unsupported environment document')
    result=dict(version=1,boxes=[],radius=float(value.get('radius',.35)),speed=value.get('speed','walk'))
    if not math.isfinite(result['radius']) or not .1<=result['radius']<=2:raise ValueError('Invalid character clearance')
    if result['speed'] not in ('walk','run'):raise ValueError('Invalid locomotion mode')
    ids=set()
    for raw in value.get('boxes',[]):
        box=copy.deepcopy(raw)
        for field in ('position','size'):
            a=np.asarray(box[field],dtype=float)
            if a.shape!=(3,) or not np.isfinite(a).all():raise ValueError('Invalid box '+field)
            box[field]=a.tolist()
        if min(box['size'])<=.001:raise ValueError('Box dimensions must be positive')
        if box['action'] not in ACTIONS:raise ValueError('Invalid object action')
        for key,default in [('yaw',0.),('hold',2.)]:
            box[key]=float(box.get(key,default))
            if not math.isfinite(box[key]):raise ValueError('Invalid box setting')
        if not 0<=box['hold']<=30:raise ValueError('Hold must be between 0 and 30 seconds')
        box['id']=str(box['id']);box['name']=str(box.get('name','Object'))[:256]
        if box['id'] in ids:raise ValueError('Duplicate object id')
        ids.add(box['id']);box['sequence']=max(0,int(box.get('sequence',0)));box['enabled']=bool(box.get('enabled',True))
        result['boxes'].append(box)
    return result

def rotation(box):
    a=math.radians(box['yaw']);return np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])

def ray_box_hit(origin,direction,box):
    """Ray/solid OBB intersection in Studio meters; yaw rotates the XY axes."""
    origin=np.asarray(origin,dtype=float)-box['position'];direction=np.asarray(direction,dtype=float).copy()
    origin[:2]=origin[:2]@rotation(box);direction[:2]=direction[:2]@rotation(box)
    near,far=0.,float('inf')
    for a,d,h in zip(origin,direction,np.asarray(box['size'])/2):
        if abs(d)<1e-10:
            if abs(a)>h:return None
        else:
            lo,hi=sorted(((-h-a)/d,(h-a)/d));near=max(near,lo);far=min(far,hi)
            if near>far:return None
    return near if far>=0 else None

def local_xy(point,box):return (np.asarray(point)[:2]-box['position'][:2])@rotation(box)

def segment_hit(start,end,box,radius=0.):
    """First intersection with an inflated oriented rectangle, or None."""
    a=local_xy(start,box);b=local_xy(end,box);d=b-a;half=np.array(box['size'][:2])/2+radius
    lo,hi=0.,1.
    for j in range(2):
        if abs(d[j])<1e-10:
            if abs(a[j])>=half[j]-1e-8:return None
        else:
            v=sorted(((-half[j]-a[j])/d[j],(half[j]-a[j])/d[j]));lo=max(lo,v[0]);hi=min(hi,v[1])
            if lo>=hi-1e-8:return None
    return lo if hi>1e-8 and lo<1-1e-8 else None

def corners(box,radius):
    half=np.array(box['size'][:2])/2+radius+.01
    return [np.array([x,y])@rotation(box).T+box['position'][:2] for x,y in [(-half[0],-half[1]),(-half[0],half[1]),(half[0],half[1]),(half[0],-half[1])]]

def route(start,end,boxes,radius=.35):
    """Visibility graph around all boxes; fail rather than route through a solid."""
    start=np.asarray(start,dtype=float)[:2];end=np.asarray(end,dtype=float)[:2]
    blockers=[b for b in boxes if b.get('enabled',True) and b['position'][2]-b['size'][2]/2<1.8]
    for point in (start,end):
        if any(np.all(np.abs(local_xy(point,b))<np.array(b['size'][:2])/2+radius-1e-5) for b in blockers):
            raise ValueError('Start or target is inside an obstacle clearance area. Move the target or object.')
    nodes=[start,end]+[p for b in blockers for p in corners(b,radius)]
    distances={0:0.};previous={};queue=[(0.,0)]
    while queue:
        distance,i=heapq.heappop(queue)
        if distance>distances[i]+1e-8:continue
        if i==1:break
        for j,p in enumerate(nodes):
            if i==j or any(segment_hit(nodes[i],p,b,radius) is not None for b in blockers):continue
            cost=distance+float(np.linalg.norm(nodes[i]-p))
            if cost<distances.get(j,float('inf')):
                distances[j]=cost;previous[j]=i;heapq.heappush(queue,(cost,j))
    if 1 not in distances:raise ValueError('No route around these objects was found')
    ids=[1]
    while ids[-1]!=0:ids.append(previous[ids[-1]])
    return [nodes[i] for i in reversed(ids)]

def choose_action(box,direction=None,language='en'):
    action=box['action'];height=box['size'][2];bottom=box['position'][2]-height/2
    if str(box.get('asset','')).endswith('.motion.json'):
        if action=='auto':return 'avoidance' if bottom>.1 else 'jump_0_5m'
        return action
    if direction is not None:
        heading=np.asarray(direction,dtype=float)[:2]
        heading=heading/max(float(np.linalg.norm(heading)),1e-10)
        depth=float(np.dot(np.abs(heading@rotation(box)),box['size'][:2]))
        limit=.6 if height<.65 else .3
        if depth>limit+1e-6 and (action.startswith('jump') or action=='auto' and bottom<.08):
            if action=='auto':return 'avoid'
            raise ValueError('Obstacle is too deep along the approach direction for this jump sample. Rotate it or use Auto/Avoid.')
    if action=='auto':
        if abs(bottom)<.08 and .4<=height<=.6 and max(box['size'][:2])<=.8:return 'jump_0_5m'
        if abs(bottom)<.08 and .65<=height<=.85 and min(box['size'][:2])<=.5:return 'jump_0_75m'
        if 1.4<=bottom<=1.6 and min(box['size'][:2])<=.7 and (direction is None or depth<=.7):return 'avoidance'
        return 'avoid'
    if action.startswith('jump'):
        nominal=.5 if action=='jump_0_5m' else .75
        if abs(bottom)>.08 or abs(height-nominal)>.15:
            if language=='ja':
                raise ValueError(f'「{box["name"]}」は地面に置いた高さ {nominal:.2f} m の障害物用の動作です。\n現在：物体の高さ {height:.3f} m、底面Z {bottom:.3f} m、上面Z {bottom+height:.3f} m。\n「位置」は物体の中心です。地面に置くには位置Zを {height/2:.3f} m にするか、「地面に配置」を押してください。\n物体の高さも異なる場合は、対応する動作か「自動／迂回」を選んでください。')
            raise ValueError('Jump sample height does not match this object. Use Auto/Avoid or a matching preset.')
    if action=='avoidance' and (not 1.4<=bottom<=1.65 or direction is not None and depth>.7):raise ValueError('Independent duck motion needs overhead clearance of 1.40–1.65 m and depth at most 0.70 m. Use Auto/Avoid for other sizes.')
    if action=='sit' and not .3<=box['position'][2]+height/2<=.55:raise ValueError('Seat sample requires a seat height of 0.3–0.55 m')
    return action

def approach_error(name,current,end,entry,exit,direction,language='en'):
    """Report additional approach/exit space in meters along the actual route."""
    before=max(0.,-float(np.dot(np.asarray(entry)[:2]-np.asarray(current)[:2],direction))+.25)
    after=max(0.,-float(np.dot(np.asarray(end)[:2]-np.asarray(exit)[:2],direction))+.25)
    messages={
        'ja':f'「{name}」の前後の距離が不足しています。\n進入側にあと {before:.2f} m、退出側にあと {after:.2f} m の余裕を確保してください。\n直前・次のターゲット、または障害物の位置を調整してから再生成してください。',
        'en':f'Not enough approach/exit space for {name}.\nAllow {before:.2f} m more before and {after:.2f} m more after the obstacle.\nAdjust the adjacent targets or the object position, then generate again.',
        'es':f'Falta espacio antes/después de {name}.\nAñada {before:.2f} m antes y {after:.2f} m después del obstáculo.\nAjuste los objetivos vecinos o el objeto y vuelva a generar.',
        'fr':f'Espace insuffisant avant/après {name}.\nAjoutez {before:.2f} m avant et {after:.2f} m après l’obstacle.\nDéplacez les cibles voisines ou l’objet, puis relancez la génération.',
        'zh':f'「{name}」前后空间不足。\n请在进入侧额外预留 {before:.2f} 米、离开侧额外预留 {after:.2f} 米。\n调整相邻目标或障碍物位置后重新生成。',
    }
    return messages.get(language,messages['en'])

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
