"""External motion inspection, editable correspondence, and candidate import UI."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from .studio_external_motion import read_source,suggested_mapping,convert,save_candidate
from .studio_data import root_transform
from .studio_import_adjustment import PURPOSES,suggested_purpose,suggested_range,suggest_cycle
from .studio_kimodo import convert_npz,save_import
import numpy as np

LABELS={
'title':('Import motion (NPZ / FBX / BVH)','動作の取り込み（NPZ / FBX / BVH）','Importar movimiento (NPZ / FBX / BVH)','Importer un mouvement (NPZ / FBX / BVH)','导入动作（NPZ / FBX / BVH）'),
'file':('Select NPZ / FBX / BVH...','NPZ / FBX / BVHを選択...','Seleccionar NPZ / FBX / BVH...','Choisir NPZ / FBX / BVH...','选择NPZ / FBX / BVH...'),
'back':('Edit bone mapping again','ボーン対応を見直す','Volver a editar huesos','Revoir les correspondances','返回骨骼映射'),
'unit':('BVH metres per unit','BVHの1単位あたりのm','BVH: metros por unidad','BVH : mètres par unité','BVH每单位米数'),
'up':('BVH up axis','BVHの上方向','Eje vertical BVH','Axe vertical BVH','BVH向上轴'),
'read':('Read and inspect','読み込み・診断','Leer e inspeccionar','Lire et inspecter','读取并检查'),
'waiting':('Reading...','読み込み中...','Leyendo...','Lecture...','正在读取...'),
'reference':('Neutral reference frame','中立姿勢のフレーム','Fotograma neutro','Image neutre','中立姿势帧'),
'reference_hint':('-1 uses the bind/offset pose. Otherwise specify an actual neutral T-pose frame.','-1はバインド／オフセット姿勢を使用します。それ以外は、実際の中立T姿勢があるフレームを指定します。','-1 usa la pose de enlace. En otro caso, indique un fotograma de pose T neutra real.','-1 utilise la pose de liaison. Sinon, indiquez une image réelle de pose T neutre.','-1使用绑定／偏移姿势。否则请指定实际中立T姿势所在帧。'),
'yaw':('Facing correction (degrees)','正面の補正（度）','Corrección frontal (grados)','Correction avant (degrés)','朝向修正（度）'),
'name':('Motion name','動作名','Nombre','Nom','动作名称'),
'prepare':('Adjust as motion','動作として調整','Ajustar como movimiento','Ajuster le mouvement','调整动作'),
'save':('Save to library','ライブラリへ登録','Guardar en biblioteca','Enregistrer dans la bibliothèque','保存到动作库'),
'usage':('How to use this motion','動作の用途','Uso del movimiento','Utilisation du mouvement','动作用途'),
'move':('Locomotion along the route','経路に沿って繰り返す移動','Desplazamiento por la ruta','Déplacement le long du trajet','沿路径循环移动'),
'transit':('Pass an obstacle','障害物を通過する動作','Atravesar un obstáculo','Franchissement d’obstacle','通过障碍物'),
'action':('Play once at the target','ターゲットで一度だけ再生','Reproducir una vez en el destino','Lire une fois sur la cible','在目标处播放一次'),
'full':('Always play the full clip','最初から最後まで必ず再生','Reproducir el clip completo','Lire le clip en entier','始终播放完整片段'),
'pose':('Use as a pose target','ポーズの目標として使う','Usar como pose objetivo','Utiliser comme pose cible','用作目标姿势'),
'start':('First frame','使用開始フレーム','Primer fotograma','Première image','起始帧'),
'end':('Last frame','使用終了フレーム','Último fotograma','Dernière image','结束帧'),
'cycle':('Suggest walking cycle','歩行周期を提案','Sugerir ciclo de marcha','Proposer un cycle de marche','建议步态周期'),
'no_cycle':('No cycle found in this range. Check the range or choose another purpose.','この範囲では周期を提案できません。使用範囲や用途を見直してください。','Sin ciclo para este intervalo. Revise el intervalo o el uso.','Aucun cycle détecté. Revoyez la plage ou l’utilisation.','此范围未检测到周期。请检查范围或用途。'),
'source_preview':('Preview in place','その場でプレビュー','Previsualizar en el sitio','Aperçu sur place','原地预览'),
'play':('Loop preview','ループ再生','Reproducir en bucle','Lecture en boucle','循环预览'),
'continue':('Continue after clearance (remove stop tail when safe)','通過後も移動を続ける（安全な区間で停止部分をカット）','Continuar después de superar el obstáculo si es seguro','Poursuivre après le franchissement si possible','安全通过后继续移动（可行时裁去停止段）'),
'transit_hint':('In Environment, select this saved motion for the box and choose Jump or Duck. Clearance is checked against the placed box.','登録後、環境画面でボックスにこの動作を指定し、ジャンプかくぐりを選びます。配置したボックスとモデルの干渉を確認します。','En Entorno, asigne el movimiento a la caja y elija Salto o Agacharse. Se comprueba el espacio disponible.','Dans Environnement, affectez le mouvement à la boîte et choisissez Sauter ou Se baisser. Le dégagement est vérifié.','在环境中给方块指定此动作并选择跳跃或低身通过。放置后会检查碰撞。'),
'draft_hint':('Only usage settings are saved. All converted frames are retained. Preview shows the source, with horizontal translation removed.','用途と使用範囲を設定します。変換済みの全フレームを保持します。プレビューでは水平移動を除いた素材を確認できます。','Se conservan todos los fotogramas convertidos. La vista previa elimina el desplazamiento horizontal.','Toutes les images converties sont conservées. L’aperçu retire le déplacement horizontal.','保留转换后的全部帧。预览时移除水平位移。'),
'preview':('Load candidate for preview','候補を読み込んで確認','Cargar candidato para revisar','Charger le candidat pour vérification','加载候选以预览'),
'profile_save':('Save bone mapping...','ボーン対応を保存...','Guardar correspondencias...','Enregistrer les correspondances...','保存骨骼映射...'),
'profile_load':('Load bone mapping...','ボーン対応を読み込む...','Cargar correspondencias...','Charger les correspondances...','加载骨骼映射...'),
'note':('Map source bones to SOMA roles. Check the neutral pose, axes and limb twist. The first action frame is not automatically treated as neutral. No contact correction or smoothing is applied. The original file is preserved.','SOMAの役割に元のボーンを対応付けます。中立姿勢・軸・手足のねじりを確認してください。先頭の動作姿勢を自動で中立扱いにはしません。接地補正・平滑化は行わず、元ファイルを保持します。','Asigne huesos a los roles SOMA. Revise pose neutra, ejes y torsión. El primer fotograma no se considera neutro automáticamente. Sin corrección de contacto ni suavizado; se conserva el original.','Affectez les os aux rôles SOMA. Vérifiez pose neutre, axes et torsion. La première image n’est pas automatiquement neutre. Sans correction de contact ni lissage ; original préservé.','将源骨骼对应到SOMA角色。检查中立姿势、轴向及四肢扭转。不会自动将动作首帧视为中立姿势。不进行接触修正或平滑，并保留原文件。')}


def label(key,language):return LABELS[key][('en','ja','es','fr','zh').index(language if language in ('en','ja','es','fr','zh') else 'en')]


class ExternalPanel:
    def __init__(self):
        self.open=False;self.path=None;self.unit=.01;self.up=0;self.data=None;self.mapping={};self.future=None;self.error=None;self.name='';self.reference_frame=-1;self.yaw=0.
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='external-motion');self.job='read';self.saved_path=None
        self.draft=None;self.preview=False;self.playing=False;self.cycle=None;self.checked_cycle=False

    def choose(self,path,skeleton,reference):
        if self.future is not None:return
        self.path=Path(path);self.name=self.path.stem;self.open=True
        self.data=self.draft=self.saved_path=self.error=None
        self.preview=self.playing=False
        if self.path.suffix.lower()=='.npz':
            self.name='Kimodo_'+self.name
            self.prepare(skeleton,reference)

    def read(self):
        if self.path and self.future is None:
            self.data=None;self.saved_path=None;self.error=None;self.job='read';self.future=self.pool.submit(read_source,self.path,unit=self.unit,up=('Y','Z')[self.up])
    def poll(self,names):
        if self.future is not None and self.future.done():
            try:
                result=self.future.result()
                if self.job=='save':return result[0]
                if self.job=='prepare':
                    self.draft,self.purpose,limits,cycle=result
                    self.continue_after=True
                    self.set_range(*limits)
                    self.cycle=cycle;self.checked_cycle=self.purpose=='move'
                elif self.job=='cycle':
                    self.cycle=result;self.checked_cycle=True
                    if result:self.cursor=float(result[0])
                else:
                    self.data=result;self.mapping=suggested_mapping(self.data['names'],names);self.reference_frame=-1
            except Exception as exc:self.error=str(exc)
            finally:self.future=None
        return None
    def set_range(self,start,end):
        self.start,self.end=start,end
        self.cursor=float(start);self.cycle=None;self.checked_cycle=False

    def prepare(self,skeleton,reference):
        self.job='prepare';self.error=None
        self.future=self.pool.submit(prepare_draft,self.path,self.data,self.mapping.copy(),skeleton,reference,self.reference_frame,self.yaw)

    def propose_cycle(self,names):
        self.job='cycle';self.error=None
        self.future=self.pool.submit(suggest_cycle,*self.draft,names,self.start,self.end)

    def import_candidate(self,skeleton,reference,folder):
        if self.draft is None or self.future is not None:return
        self.job='save';self.error=None
        options=dict(name=self.name,converted=self.draft,adjustment=(self.purpose,self.start,self.end,self.continue_after))
        if self.path.suffix.lower()=='.npz':
            self.future=self.pool.submit(save_import,self.path,skeleton,reference,folder,**options)
        else:
            self.future=self.pool.submit(save_candidate,self.data,self.mapping.copy(),skeleton,reference,folder,**options)

    def advance(self,delta):
        if self.open and self.preview and self.playing:
            start,end=(self.cycle[0],self.cycle[1]-1) if self.cycle else (self.start,self.end)
            self.cursor=start+(self.cursor-start+delta*30)%(end-start+1)

    def preview_pose(self):
        if self.open and self.preview and self.draft is not None:
            pose=self.draft[0][int(self.cursor)].copy()
            pose[0,:2]=0
            return pose
    def save_mapping(self,path):
        from pathlib import Path
        Path(path).write_text(json.dumps(dict(schema='studio-human-import-profile-v1',names=self.data['names'],coordinate=self.data['coordinate'],mapping=self.mapping,unit=self.unit,up=self.up,reference_frame=self.reference_frame,yaw=self.yaw),ensure_ascii=False,indent=2),encoding='utf8')
    def load_mapping(self,path):
        from pathlib import Path
        data=json.loads(Path(path).read_text(encoding='utf8'))
        if data.get('schema')!='studio-human-import-profile-v1' or data.get('names')!=self.data['names']:raise ValueError('Bone mapping belongs to another source skeleton')
        if data.get('coordinate')!=self.data['coordinate']:raise ValueError('Source axes/units differ. Read the file with the profile settings first.')
        mapping=data.get('mapping')
        if not isinstance(mapping,dict) or any(not isinstance(k,str) or v not in self.data['names'] for k,v in mapping.items()):raise ValueError('Invalid bone mapping profile')
        import math
        if not math.isfinite(float(data['yaw'])):raise ValueError('Invalid profile facing correction')
        self.mapping=data['mapping'];self.reference_frame=int(data['reference_frame']);self.yaw=float(data['yaw'])


def prepare_draft(path,data,mapping,skeleton,reference,reference_frame,yaw):
    if path.suffix.lower()=='.npz':
        converted=convert_npz(path,skeleton,reference)
    else:
        converted=convert(data,mapping,skeleton,reference,reference_frame=reference_frame,yaw=yaw)
    purpose=suggested_purpose(path.stem)
    limits=suggested_range(converted[0],purpose)
    cycle=suggest_cycle(*converted,skeleton.joint_names,*limits) if purpose=='move' else None
    return converted,purpose,limits,cycle


def poll_external(app):
    panel=app.external_panel;path=panel.poll(app.skeleton.joint_names)
    if path:
        try:app._scan_library();panel.saved_path=path
        except Exception as exc:panel.error=str(exc)


def draw_external(app,ui):
    panel=app.external_panel
    if not panel.open:return
    lang=app.language
    ui.set_next_window_size(ui.ImVec2(575,615),ui.Cond_.first_use_ever)
    visible,panel.open=ui.begin(label('prepare' if panel.draft is not None or panel.path and panel.path.suffix.lower()=='.npz' else 'title',lang)+'###external_import',panel.open)
    position=ui.get_window_pos();size=ui.get_window_size();panel.ui_bounds=(position.x,position.y,size.x,size.y)
    try:
        if not visible:return
        waiting=panel.future is not None
        npz=panel.path is not None and panel.path.suffix.lower()=='.npz'
        def reference():return root_transform(app.skeleton.reference_local_transforms.numpy(),np.asarray(app.model_to_runtime))
        ui.begin_disabled(waiting)
        if ui.button(label('file',lang)):app.pending='external_file'
        ui.text_wrapped(str(panel.path or '—'))
        if not npz and panel.draft is None:
            _,panel.unit=ui.input_float(label('unit',lang),panel.unit,.001,.01,'%.5f')
            _,panel.up=ui.combo(label('up',lang),panel.up,['Y','Z'])
            ui.begin_disabled(not panel.path)
            if ui.button(label('read',lang)):panel.read()
            ui.end_disabled()
        ui.end_disabled()
        if waiting:ui.text_wrapped(label('waiting',lang))
        if panel.error:ui.text_wrapped(panel.error)
        if panel.saved_path:
            ui.text_wrapped(str(panel.saved_path))
            ui.begin_disabled(app.busy)
            if ui.button(label('preview',lang)):
                try:app.use_library_file(panel.saved_path);panel.open=False
                except Exception as exc:panel.error=str(exc)
            ui.end_disabled()
        if panel.draft is not None:
            ui.begin_disabled(waiting)
            if panel.data and ui.button(label('back',lang)):
                panel.draft=panel.saved_path=None;panel.preview=panel.playing=False
                ui.end_disabled()
                return
            _,panel.name=ui.input_text(label('name',lang),panel.name)
            changed,index=ui.combo(label('usage',lang),PURPOSES.index(panel.purpose),[label(p,lang) for p in PURPOSES])
            last=len(panel.draft[0])-1
            if changed:
                panel.purpose=PURPOSES[index]
                panel.set_range(*suggested_range(panel.draft[0],panel.purpose))
            if panel.purpose!='full':
                changed,start=ui.slider_int(label('start',lang),panel.start,0,panel.end-3)
                edited,end=ui.slider_int(label('end',lang),panel.end,start+3,last)
                if changed or edited:panel.set_range(start,end)
            ui.text(f'{panel.end-panel.start+1} / {last+1} frames | {(panel.end-panel.start)/30:.2f} s | 30 fps')
            if panel.purpose=='move':
                if ui.button(label('cycle',lang)):panel.propose_cycle(app.skeleton.joint_names)
                if panel.cycle:
                    lo,hi=panel.cycle
                    ui.text(f'{lo}–{hi} | {(hi-lo)/30:.2f} s')
                elif panel.checked_cycle:ui.text_wrapped(label('no_cycle',lang))
            elif panel.purpose=='transit':
                _,panel.continue_after=ui.checkbox(label('continue',lang),panel.continue_after)
                ui.text_wrapped(label('transit_hint',lang))
            _,panel.preview=ui.checkbox(label('source_preview',lang),panel.preview)
            if panel.preview:
                ui.same_line()
                _,panel.playing=ui.checkbox(label('play',lang),panel.playing)
                moved,frame=ui.slider_int('##import_preview_frame',int(panel.cursor),panel.start,panel.end)
                if moved:panel.cursor=float(frame);panel.playing=False
            ui.text_wrapped(label('draft_hint',lang))
            ui.begin_disabled(app.busy)
            if ui.button(label('save',lang)):
                try:panel.import_candidate(app.skeleton,reference(),app.user_directory/'poses')
                except Exception as exc:panel.error=str(exc)
            ui.end_disabled()
            ui.end_disabled()
        elif panel.data:
            ui.begin_disabled(waiting)
            data=panel.data;ui.text_wrapped(f"{len(data['names'])} bones | {len(data['world'])} frames | {data['source_fps']:.4g} source fps | {data['coordinate']}")
            _,panel.name=ui.input_text(label('name',lang),panel.name)
            _,panel.reference_frame=ui.input_int(label('reference',lang),panel.reference_frame)
            ui.text_wrapped(label('reference_hint',lang))
            _,panel.yaw=ui.input_float(label('yaw',lang),panel.yaw)
            ui.text_wrapped(label('note',lang))
            ui.begin_child('source_bone_mapping',ui.ImVec2(0,230),child_flags=ui.ChildFlags_.borders)
            try:
                options=['—']+data['names']
                for name in app.skeleton.joint_names:
                    current=panel.mapping.get(name);index=options.index(current) if current in options else 0
                    changed,index=ui.combo(name+'###import_'+name,index,options)
                    if changed:
                        if index:panel.mapping[name]=options[index]
                        else:panel.mapping.pop(name,None)
            finally:ui.end_child()
            if ui.button(label('profile_save',lang)):app.pending='external_profile_save'
            ui.same_line()
            if ui.button(label('profile_load',lang)):app.pending='external_profile_load'
            ui.begin_disabled(app.busy)
            if ui.button(label('prepare',lang)):
                try:
                    panel.prepare(app.skeleton,reference())
                except Exception as exc:panel.error=str(exc)
            ui.end_disabled()
            ui.end_disabled()
    finally:ui.end()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
