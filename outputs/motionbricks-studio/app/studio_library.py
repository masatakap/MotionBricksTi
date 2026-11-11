"""Small, portable genre index. Never decode dense motion files in the UI loop."""
from pathlib import Path
import json
from uuid import uuid4

GENRES=(
 ('locomotion','Walking / Running','歩行・走行','Caminar / Correr','Marche / Course','行走／跑步'),
 ('crouch','Crouching','しゃがみ','Agacharse','Accroupissement','蹲姿'),
 ('obstacles','Obstacles','障害物','Obstáculos','Obstacles','障碍物'),
 ('idle','Idle / Warm-up','待機・準備動作','Repos / Calentamiento','Repos / Échauffement','待机／热身'),
 ('seated','Sitting / Standing up','座る・立つ','Sentarse / Levantarse','S’asseoir / Se relever','坐下／起立'),
 ('combat','Combat / Props','戦闘・道具','Combate / Objetos','Combat / Accessoires','战斗／道具'),
 ('acting','Acting / Special walks','演技・特殊歩行','Actuación / Marchas especiales','Jeu / Marches spéciales','表演／特殊步态'),
 ('dance','Dance','ダンス','Baile','Danse','舞蹈'),
 ('hands','Hands / Fingers','手・指','Manos / Dedos','Mains / Doigts','手／手指'),
 ('other','Uncategorized / Other','未分類・その他','Sin categoría / Otros','Sans catégorie / Autres','未分类／其他'),
)
IDS=tuple(row[0] for row in GENRES)
LANGUAGES=('en','ja','es','fr','zh')
LABELS={
 'all':('All genres','すべてのジャンル','Todos los géneros','Tous les genres','所有类别'),
 'genre':('Genre','カテゴリ','Género','Genre','类别'),
 'assign':('Selected item genre','選択項目のジャンル','Género del elemento','Genre de la sélection','所选项目类别'),
 'auto':('Automatic','自動分類','Automático','Automatique','自动分类'),
 'empty':('No items match this genre/search.','このジャンル・検索条件に該当する項目はありません。','Ningún elemento coincide con el género o la búsqueda.','Aucun élément ne correspond au genre ou à la recherche.','没有符合类别或搜索条件的项目。'),
 'new':('+ New genre','＋新規ジャンル','+ Nuevo género','+ Nouveau genre','＋新建类别'),
 'name':('Genre name','ジャンル名','Nombre del género','Nom du genre','类别名称'),
 'create':('Create','作成','Crear','Créer','创建'),
 'cancel':('Cancel','キャンセル','Cancelar','Annuler','取消'),
 'delete_genre':('Delete genre…','ジャンルを削除…','Eliminar género…','Supprimer le genre…','删除类别…'),
 'delete':('Delete','削除','Eliminar','Supprimer','删除'),
 'confirm_delete':('Delete “{name}”? Its items will return to automatic classification. The motion and pose files will be kept.','「{name}」を削除しますか？ 含まれる素材は自動分類に戻ります。モーションやポーズのファイルは残ります。','¿Eliminar «{name}»? Sus elementos volverán a la clasificación automática y se conservarán los archivos.','Supprimer « {name} » ? Ses éléments seront reclassés automatiquement et leurs fichiers seront conservés.','删除“{name}”？其中的素材将恢复自动分类，动作和姿势文件会保留。'),
 'invalid':('Enter a genre name.','ジャンル名を入力してください。','Introduzca un nombre.','Saisissez un nom de genre.','请输入类别名称。'),
 'duplicate':('This genre name is already in use.','同じ名前のジャンルがすでにあります。','Ese nombre ya está en uso.','Ce nom de genre est déjà utilisé.','此类别名称已存在。'),
}

def label(ident,language='en'):
    i=LANGUAGES.index(language) if language in LANGUAGES else 0
    if ident in LABELS:return LABELS[ident][i]
    return next(row[1+i] for row in GENRES if row[0]==ident)

def infer_genre(path):
    name=Path(path).name.casefold()
    def has(*words):return any(w in name for w in words)
    if has('dance','masataka_bad_code','bad_code','ダンス','舞蹈'):return 'dance'
    if has('vault','jump','duck','bend_down','avoidance','障害','くぐ','乗り越','跳び越'):return 'obstacles'
    if has('sit_down','stand_up','seated','sit_cycle','sit_on_chair','座る','座り','座位','椅子','立ち上'):return 'seated'
    if has('finger','hand_pose','handpose','grip','fist','scissors','手指','指ポーズ','握り','グー','チョキ','パー'):return 'hands'
    if has('combat','armed','gun','prop_walk','戦闘','構え','銃','道具'):return 'combat'
    if has('injured','limp','hold_torso','zombie','負傷','かば','ゾンビ'):return 'acting'
    if has('crouch','しゃが','蹲'):return 'crouch'
    if has('idle','look_around','looking_around','legs_relax','neck_warmup','warm_up_neck','待機','見回','ほぐ','準備'):return 'idle'
    if has('walk','jog','run','skip','歩','走','スキップ'):return 'locomotion'
    return 'other'

def motion_name(path):
    """Display the action name without compound storage extensions."""
    name=Path(path).name
    for suffix in ('.motion.json','.pose.json'):
        if name.endswith(suffix):return name[:-len(suffix)]
    return Path(path).stem

class LibraryGenres:
    def __init__(self,root,path):
        self.root=Path(root).resolve();self.path=Path(path);self.custom={};self.overrides={};self.active='all';self._keys={};self._inferred={}
        try:
            d=json.loads(self.path.read_text(encoding='utf8'))
            if d.get('version') in (1,2):
                if d['version']==2 and isinstance(d.get('custom'),dict):
                    self.custom={k:v for k,v in d['custom'].items() if k.startswith('custom:') and isinstance(v,str) and v.strip()}
                ids=set(self.ids)
                if isinstance(d.get('overrides'),dict):
                    self.overrides={k:v for k,v in d['overrides'].items() if isinstance(v,str) and v in ids}
                active=d.get('active')
                if isinstance(active,str) and active in ids:self.active=active
        except (OSError,ValueError,TypeError,AttributeError):pass

    @property
    def ids(self):
        return (*IDS,*self.custom)

    def caption(self,ident,language):
        return self.custom[ident] if ident in self.custom else label(ident,language)

    def name_error(self,name):
        name=name.strip().casefold()
        if not name or '##' in name:return 'invalid'
        reserved=(text for row in (*GENRES,('all',*LABELS['all']),('auto',*LABELS['auto'])) for text in row[1:])
        if any(text.casefold()==name for text in reserved) or any(text.casefold()==name for text in self.custom.values()):
            return 'duplicate'
        return None

    def create(self,name):
        error=self.name_error(name)
        if error:raise ValueError(error)
        ident='custom:'+uuid4().hex
        self.custom[ident]=name.strip()
        try:self.save()
        except OSError:
            del self.custom[ident]
            raise
        return ident

    def remove(self,ident):
        if ident not in self.custom:raise ValueError('Only custom library genres can be deleted')
        previous=self.custom,self.overrides,self.active
        self.custom={key:name for key,name in self.custom.items() if key!=ident}
        self.overrides={key:genre for key,genre in self.overrides.items() if genre!=ident}
        if self.active==ident:self.active='all'
        try:self.save()
        except OSError:
            self.custom,self.overrides,self.active=previous
            raise

    def key(self,path):
        raw=str(path)
        if raw in self._keys:return self._keys[raw]
        p=Path(path).resolve()
        result=p.relative_to(self.root).as_posix() if p.is_relative_to(self.root) else p.as_posix()
        self._keys[raw]=result
        return result

    def genre(self,path):
        key=self.key(path)
        if key in self.overrides:return self.overrides[key]
        if key not in self._inferred:self._inferred[key]=infer_genre(path)
        return self._inferred[key]

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(dict(version=2,active=self.active,custom=self.custom,overrides=self.overrides),ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(self.path)

    def assign(self,path,genre):
        if genre is not None and genre not in IDS and genre not in self.custom:raise ValueError('Unknown library genre')
        key=self.key(path);old=self.overrides.get(key)
        if genre is None:self.overrides.pop(key,None)
        else:self.overrides[key]=genre
        try:self.save()
        except OSError:
            if old is None:self.overrides.pop(key,None)
            else:self.overrides[key]=old
            raise

    def filter(self,files,query=''):
        query=query.casefold()
        return [i for i,p in enumerate(files) if (self.active=='all' or self.genre(p)==self.active) and query in str(p).casefold()]

    def counts(self,files):
        result=dict.fromkeys(self.ids,0)
        for path in files:result[self.genre(path)]+=1
        return result

def keep_visible_selection(files,selected,indices):
    return selected if 0<=selected<len(files) and selected in indices else (indices[0] if indices else -1)

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
