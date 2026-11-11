"""Studio localization with stable ImGui identities across language changes."""
import json
from pathlib import Path
import re
from .studio_locales import LANGUAGES,TABLES
from .studio_motion_i18n import TRANSLATIONS as MOTION_TRANSLATIONS
from .studio_ue_i18n import TRANSLATIONS as UE_TRANSLATIONS
from .studio_scene_i18n import TRANSLATIONS as SCENE_TRANSLATIONS

JA = {
 'Help':'ヘルプ', 'User Guide':'説明書', 'Guide search':'説明書を検索', 'Close':'閉じる',
 'No matching sections.':'一致する説明がありません。', 'Tokens to Generate':'生成するトークン数',
 'Mirror Pose':'ポーズを左右反転',
 'Swap left and right, preserving position and facing. Undo is available.':'位置と向きを保ち、左右のポーズを反転します。Undoで取り消せます。',
 'Playback Timeline':'再生タイムライン', 'Playback Time':'再生位置', 'Motion duration':'モーションの尺',
 'Stop':'停止', 'Generate motion or load music to use the timeline.':'モーションを生成するか音楽を読み込むとシークできます。',
 'Export':'書き出し',
 'Choose MMD target PMX or PMD...':'MMDの対象モデル（PMXまたはPMD）を選択...',
 'PMX or PMD model':'PMXまたはPMDモデル',
 'Choose MMD target model':'MMDの対象モデルを選択', 'PMX model':'PMXモデル',
 'Export MMD VMD...':'MMD向けVMDを書き出す...', 'Export MMD VMD':'MMD向けVMDを書き出す',
 'VMD motion':'VMDモーション', 'Exporting VMD...':'VMDを書き出しています...',
 'VMD uses target PMX or PMD proportions and FK bones. Leg IK is disabled.':'VMDは対象PMXまたはPMDの体格に合わせたFK方式です。脚IKは無効化します。',
 'Export Reference MP4...':'現在のカメラでMP4を書き出す...',
 'Export Reference MP4':'リファレンスMP4を書き出す', 'MP4 video':'MP4動画',
 'Include music in MP4':'MP4に音楽を含める',
 'Drag a pose row to reorder. The first row is the start pose.':'ポーズの行をドラッグして並べ替えます。先頭の行が開始ポーズです。',
 'Music Timeline':'音楽タイムライン', 'Load Music...':'音を読み込む...',
 'Play Audio':'音楽を再生', 'Pause Audio':'音楽を一時停止', 'Stop Audio':'音楽を停止',
 'Audio Time':'音楽の再生位置', 'Sync motion to audio':'音楽にモーションを同期',
 'Load an MP3 or WAV file, then play or drag the timeline to seek.':'MP3またはWAVを読み込み、再生またはタイムラインをドラッグしてシークできます。',
 'Delete Saved Pose':'保存ポーズを削除',
 'Moves the saved pose to deleted_poses. Targets keep their copied data.':'保存ポーズをdeleted_posesへ移動します。配置済みターゲットのデータは保持します。',
 'Project':'プロジェクト', 'View':'表示', 'Open...':'開く...', 'Save':'保存',
 'Save As...':'名前を付けて保存...', 'Recover Autosave':'自動保存から復旧',
 'Autosave (every 15 minutes)':'自動保存（15分ごと）',
 'Frame character':'キャラクターを画面に収める', 'Viewer options':'表示オプション',
 'Motion & Pose Library':'モーション・ポーズ ライブラリ', 'Targets & Bone Editor':'ターゲット・ボーン編集',
 'Search':'検索', 'Import BVH...':'BVHを取り込む...', 'Import NPZ/BVH...':'NPZ/BVHを取り込む...', 'Import Motion...':'動作を取り込む...', 'Load Pose...':'ポーズを読み込む...',
 'Refresh Library':'ライブラリを更新',
 'Double-click a motion to load it into the selected target.':'モーションをダブルクリックすると、選択中のターゲットに読み込みます。',
 'Load Selected into Target':'選択した素材をターゲットに読み込む', 'Source frame (s)':'元モーションの時刻（秒）',
 'Extract Frame as Editable Pose':'このフレームを編集用ポーズにする',
 'Independent pose / saved motion window':'独立した編集ポーズ／保存済みポーズ',
 'Pose name':'ポーズ名', 'Save Pose As...':'新規ポーズとして保存...',
 'Orbit: right drag. Pan XY: middle drag. Zoom: wheel. Left click selects a joint.':
 '右ドラッグ：回転／中ドラッグ：画面XY移動／ホイール：ズーム／左クリック：関節選択',
 '+ Target':'＋ ターゲット', 'Remove':'削除', 'Name':'名前', 'Edit Bones':'ボーンを編集',
 'Undo':'元に戻す', 'Redo':'やり直す', 'Placement':'配置', 'Translation:':'位置：', 'Rotation:':'回転：',
 'Tool':'操作', 'Rotate Bone (FK)':'ボーン回転（FK）', 'Move Joint (IK)':'関節を移動（IK）',
 'Find bone':'ボーン検索', 'Local rotation':'ローカル回転', 'Reset Bone':'選択ボーンをリセット',
 'Restore only this bone rotation to the skeleton rest pose. Undo is available.':
 '選択ボーンの回転だけを骨格の基準姿勢へ戻します。Undoで取り消せます。',
 'Drag the joint gizmo. IK preserves bone lengths; best on hands / feet.':
 '関節のギズモをドラッグします。骨の長さを保ちます。手・足での操作に適しています。',
 'Generation Settings':'動作の生成設定', 'Tokens to Generate:':'生成するトークン数：',
 'Target poses':'目標の連続ポーズ数', 'Hold frames':'到達後に保持するフレーム数',
 'Transition duration (s)':'この区間の尺（秒）', '0 = automatic. Duration is baked into the generated motion and FBX.':
 '0は自動。指定した尺は生成結果とFBXにも反映されます。',
 'Large duration changes can cause foot sliding or slow-motion movement.':
 '尺を大きく変えると、足滑りやスローモーション感が出る場合があります。',
 'Generate Motion':'モーションを生成', 'Pause':'一時停止', 'Play':'再生', 'Loop':'ループ',
 'Show target poses':'目標ポーズを表示', 'Show generated motion':'生成結果を表示', 'Time':'再生位置',
 'Preview speed':'確認用の再生速度', 'Preview speed does not change FBX duration.':
 '確認用の速度です。FBXの尺は変わりません。',
 'Targets changed. Generate again to update this preview.':'ターゲットが変更されています。再生成すると反映されます。',
 'Capture Playback as New Target':'表示中の姿勢を新しいターゲットにする',
 'In-place (remove XY travel)':'その場で再生（水平方向の移動を除去）', 'Include preview mesh':'プレビュー用メッシュを含める',
 'Export FBX...':'FBXを書き出す...', 'Working...':'処理中...', 'Studio Error':'エラー', 'OK':'OK',
 'Copy and Add':'コピーして追加', 'Copy':'コピー', 'English':'English', 'Japanese':'日本語',
 'Reset':'リセット', 'Reset All':'すべてリセット', 'Lock':'固定', 'Unlock':'固定解除',
 'Select a motion, choose a frame, then edit a bone.':'モーションとフレームを選び、ボーンを編集してください。',
 'Edited pose. Save Pose registers it in your library.':'ポーズを編集しました。「新規ポーズとして保存」で登録できます。',
 'Generating motion... You can still orbit the camera.':'モーションを生成しています。カメラは引き続き操作できます。',
 'Exporting FBX in the background...':'FBXを書き出しています...',
 'Preparing motion generation...':'モーション生成を準備しています...',
 'Open Project':'プロジェクトを開く', 'Save Project':'プロジェクトを保存', 'Save Project As':'名前を付けて保存',
 'Import SOMA motion':'SOMAモーションを読み込む', 'Load Pose':'ポーズを読み込む', 'Save New Pose':'新規ポーズを保存',
 'Export FBX':'FBXを書き出す', 'Studio poses':'Studioポーズ',
 'Studio projects':'Studioプロジェクト', 'SOMA BVH motion':'SOMA BVHモーション', 'FBX animation':'FBXアニメーション',
 'Hips':'骨盤', 'Spine1':'上半身1', 'Spine2':'上半身2', 'Chest':'胸', 'Neck1':'首1', 'Neck2':'首2', 'Head':'頭',
 'HeadEnd':'頭の先端', 'LeftShoulder':'左肩', 'RightShoulder':'右肩', 'LeftArm':'左上腕', 'RightArm':'右上腕',
 'LeftForeArm':'左前腕', 'RightForeArm':'右前腕', 'LeftHand':'左手', 'RightHand':'右手',
 'LeftLeg':'左太腿', 'RightLeg':'右太腿', 'LeftShin':'左すね', 'RightShin':'右すね',
 'LeftFoot':'左足', 'RightFoot':'右足', 'LeftToeBase':'左つま先', 'RightToeBase':'右つま先',
 'LeftToeEnd':'左つま先の先端', 'RightToeEnd':'右つま先の先端',
}


JA.update(MOTION_TRANSLATIONS['ja'])
JA.update(UE_TRANSLATIONS['ja'])
JA.update(SCENE_TRANSLATIONS['ja'])
for _code in TABLES:TABLES[_code].update(UE_TRANSLATIONS[_code])
for _code in TABLES:TABLES[_code].update(SCENE_TRANSLATIONS[_code])


_REFRESH_LABELS={
 'Import':('読み込み','Importar','Importer','导入'),
 '+ Add Target':('＋ターゲット追加','＋ Añadir destino','＋ Ajouter une cible','＋ 添加目标'),
 'Install UE Bridge...':('UE連携プラグインを導入...','Instalar puente UE...','Installer la liaison UE...','安装UE联动插件...'),
}
for _key,_values in _REFRESH_LABELS.items():
    JA[_key]=_values[0]
    for _code,_value in zip(('es','fr','zh'),_values[1:]):TABLES[_code][_key]=_value

def text(value, language):
    if not isinstance(value,str) or language=='en': return value
    if language in TABLES:
        table=TABLES[language]
        if value in table:return table[value]
        for prefix in ('Loaded ','Saved pose: ','Saved project: ','Opened project: ','Exported: ',
                       'Raw frames: ','Pose moved to deleted_poses: ','[POSE] ','[MOTION] '):
            if value.startswith(prefix):return table[prefix]+value[len(prefix):]
        if re.fullmatch(r'Target \d+',value):return table['Target']+' '+value.split()[-1]
        match=re.fullmatch(r'(\d+) frames generated in ([\d.]+) s',value)
        if match:
            return {'es':f'{match[1]} fotogramas generados en {match[2]} s',
                    'fr':f'{match[1]} images générées en {match[2]} s',
                    'zh':f'已生成{match[1]}帧，耗时{match[2]}秒'}[language]
        match=re.fullmatch(r'(\d+) frames \| 30 fps',value)
        if match:return {'es':f'{match[1]} fotogramas | 30 fps','fr':f'{match[1]} images | 30 fps',
                         'zh':f'{match[1]}帧｜30fps'}[language]
        return value.replace('  * unsaved',table['  * unsaved'])
    if language!='ja':return value
    if value in JA: return JA[value]
    for prefix,translated in [('Loaded ','読み込み：'),('Saved pose: ','ポーズを保存：'),
                              ('Saved project: ','プロジェクトを保存：'),('Opened project: ','プロジェクトを開きました：'),
                              ('Exported: ','書き出しました：'),('Raw frames: ','生成フレーム数：'),
                              ('Pose moved to deleted_poses: ','ポーズを退避しました：')]:
        if value.startswith(prefix): return translated+value[len(prefix):]
    if value=='Start': return '開始'
    if re.fullmatch(r'Target \d+',value): return value.replace('Target','目標')
    match=re.fullmatch(r'(\d+) frames generated in ([\d.]+) s',value)
    if match: return f'{match[1]}フレームを{match[2]}秒で生成しました'
    match=re.fullmatch(r'(\d+) frames \| 30 fps',value)
    if match: return f'{match[1]}フレーム｜30fps'
    if value.startswith('[POSE] '): return '[ポーズ] '+value[7:]
    if value.startswith('[MOTION] '): return '[動作] '+value[9:]
    return value.replace('  * unsaved','  ＊未保存')


class LocalizedUI:
    """Translate visible widget strings without changing IDs, user data, or file names."""
    LABEL_METHODS={'begin','begin_menu','button','input_text','checkbox','collapsing_header',
                   'slider_float','slider_int','drag_float3','drag_float','input_float','input_float3','input_int','combo',
                   'selectable','open_popup','begin_popup_modal','menu_item'}
    TEXT_METHODS={'text_unformatted','text_wrapped','set_tooltip','text'}

    def __init__(self,ui,language): self.ui,self.language=ui,language

    def label(self,value):
        if not isinstance(value,str) or value.startswith('##'): return value
        visible=value.split('##',1)[0]
        ident=value.split('###',1)[1] if '###' in value else value
        return text(visible,self.language)+'###'+ident

    def __getattr__(self,name):
        attr=getattr(self.ui,name)
        if name in self.LABEL_METHODS:
            def call(*args,**kwargs):
                args=list(args)
                if args: args[0]=self.label(args[0])
                if name=='combo' and len(args)>2 and isinstance(args[2],list):
                    args[2]=[text(item,self.language) for item in args[2]]
                return attr(*args,**kwargs)
            return call
        if name in self.TEXT_METHODS:
            return lambda value,*a,**kw: attr(text(value,self.language),*a,**kw)
        return attr


def load_language(path):
    try:
        value=json.loads(Path(path).read_text(encoding='utf-8')).get('language','ja')
        return value if value in {code for _,code in LANGUAGES} else 'ja'
    except (OSError,ValueError,AttributeError): return 'ja'


def save_language(path,language):
    path=Path(path)
    try: data=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError): data={}
    if not isinstance(data,dict): data={}
    data['language']=language
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)


def install_font(ui):
    folder=Path(__file__).with_name('fonts')
    # ImGui 1.92 separates the rendered base size from the font's loading size.
    ui.get_style().font_size_base=19.
    atlas=ui.get_io().fonts
    fonts={}
    for code,first,second in [('default','NotoSansJP-Regular.otf','NotoSansSC-Regular.otf'),
                              ('zh','NotoSansSC-Regular.otf','NotoSansJP-Regular.otf')]:
        fonts[code]=atlas.add_font_from_file_ttf(str(folder/'Inter.ttf'),19.)
        for filename in (first,second):
            config=ui.ImFontConfig();config.merge_mode=True
            atlas.add_font_from_file_ttf(str(folder/filename),19.,config)
    ui.get_io().font_default=fonts['default']
    return fonts

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
