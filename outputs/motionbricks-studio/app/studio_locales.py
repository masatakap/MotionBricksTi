"""Spanish, French and Simplified Chinese interface translations."""
LANGUAGES=(('日本語','ja'),('English','en'),('Español','es'),('Français','fr'),('简体中文','zh'))

ROWS='''
Help|Ayuda|Aide|帮助
User Guide|Manual de uso|Guide d’utilisation|使用说明
Guide search|Buscar en el manual|Rechercher dans le guide|搜索说明
Close|Cerrar|Fermer|关闭
No matching sections.|No hay secciones coincidentes.|Aucune section correspondante.|没有匹配的章节。
Mirror Pose|Reflejar pose|Inverser la pose|左右镜像姿势
Swap left and right, preserving position and facing. Undo is available.|Intercambia izquierda y derecha sin cambiar la posición ni la orientación. Se puede deshacer.|Inverse gauche et droite sans changer la position ni l’orientation. Annulation possible.|交换左右姿势，保持位置和朝向不变。可以撤销。
Playback Timeline|Línea de tiempo|Chronologie de lecture|播放时间轴
Playback Time|Posición|Position de lecture|播放位置
Motion duration|Duración del movimiento|Durée du mouvement|动作时长
Stop|Detener|Arrêter|停止
Generate motion or load music to use the timeline.|Genere un movimiento o cargue música para usar la línea de tiempo.|Générez un mouvement ou chargez de la musique pour utiliser la chronologie.|生成动作或加载音乐后即可使用时间轴。
Export|Exportar|Exporter|导出
Choose MMD target PMX or PMD...|Elegir modelo MMD (PMX o PMD)...|Choisir un modèle MMD (PMX ou PMD)...|选择MMD目标模型（PMX或PMD）...
PMX or PMD model|Modelo PMX o PMD|Modèle PMX ou PMD|PMX或PMD模型
Choose MMD target model|Elegir modelo de destino MMD|Choisir le modèle cible MMD|选择MMD目标模型
PMX model|Modelo PMX|Modèle PMX|PMX模型
Export MMD VMD...|Exportar VMD para MMD...|Exporter un VMD pour MMD...|导出MMD的VMD...
Export MMD VMD|Exportar VMD para MMD|Exporter un VMD pour MMD|导出MMD的VMD
VMD motion|Movimiento VMD|Mouvement VMD|VMD动作
Exporting VMD...|Exportando VMD...|Exportation du VMD...|正在导出VMD...
VMD uses target PMX or PMD proportions and FK bones. Leg IK is disabled.|VMD usa las proporciones del PMX o PMD y huesos FK. Se desactiva la IK de las piernas.|Le VMD utilise les proportions du PMX ou PMD et des os FK. L’IK des jambes est désactivée.|VMD按目标PMX或PMD的比例转换为FK骨骼，并禁用腿部IK。
Export Reference MP4...|Exportar MP4 con esta cámara...|Exporter un MP4 avec cette caméra...|按当前相机导出参考MP4...
Export Reference MP4|Exportar MP4 de referencia|Exporter un MP4 de référence|导出参考MP4
MP4 video|Vídeo MP4|Vidéo MP4|MP4视频
Include music in MP4|Incluir música en el MP4|Inclure la musique dans le MP4|在MP4中包含音乐
Drag a pose row to reorder. The first row is the start pose.|Arrastre las filas para reordenarlas. La primera es la pose inicial.|Faites glisser les lignes pour les réordonner. La première est la pose de départ.|拖动姿势行可调整顺序。第一行是起始姿势。
Music Timeline|Línea de tiempo musical|Chronologie musicale|音乐时间轴
Load Music...|Cargar música...|Charger une musique...|加载音乐...
Play Audio|Reproducir audio|Lire l’audio|播放音频
Pause Audio|Pausar audio|Mettre l’audio en pause|暂停音频
Stop Audio|Detener audio|Arrêter l’audio|停止音频
Audio Time|Posición del audio|Position audio|音频位置
Sync motion to audio|Sincronizar con el audio|Synchroniser avec l’audio|动作与音频同步
Load an MP3 or WAV file, then play or drag the timeline to seek.|Cargue un MP3 o WAV; reproduzca o arrastre la línea de tiempo para cambiar de posición.|Chargez un MP3 ou WAV, puis lancez la lecture ou déplacez le curseur de la chronologie.|加载MP3或WAV后，可以播放或拖动时间轴定位。
Delete Saved Pose|Eliminar pose guardada|Supprimer la pose enregistrée|删除已保存姿势
Moves the saved pose to deleted_poses. Targets keep their copied data.|Mueve la pose a deleted_poses. Los destinos conservan sus datos.|Déplace la pose vers deleted_poses. Les cibles conservent leurs données.|将姿势文件移至deleted_poses。已放置目标的数据会保留。
Project|Proyecto|Projet|项目
View|Vista|Affichage|视图
Open...|Abrir...|Ouvrir...|打开...
Save|Guardar|Enregistrer|保存
Save As...|Guardar como...|Enregistrer sous...|另存为...
Recover Autosave|Recuperar autoguardado|Récupérer la sauvegarde auto|恢复自动保存
Autosave (every 15 minutes)|Autoguardado (cada 15 minutos)|Sauvegarde automatique (toutes les 15 minutes)|自动保存（每15分钟）
Frame character|Encuadrar personaje|Cadrer le personnage|将角色置于视野中
Viewer options|Opciones de vista|Options d’affichage|视图选项
Motion & Pose Library|Biblioteca de movimientos y poses|Bibliothèque de mouvements et poses|动作与姿势库
Targets & Bone Editor|Destinos y editor de huesos|Cibles et éditeur d’os|目标与骨骼编辑器
Search|Buscar|Rechercher|搜索
Import BVH...|Importar BVH...|Importer un BVH...|导入BVH...
Load Pose...|Cargar pose...|Charger une pose...|加载姿势...
Import NPZ/BVH...|Importar NPZ/BVH...|Importer NPZ/BVH...|导入NPZ/BVH...
Import Motion...|Importar movimiento...|Importer un mouvement...|导入动作...
Refresh Library|Actualizar biblioteca|Actualiser la bibliothèque|刷新资源库
Double-click a motion to load it into the selected target.|Haga doble clic en un movimiento para cargarlo en el destino seleccionado.|Double-cliquez sur un mouvement pour le charger dans la cible sélectionnée.|双击动作可将其加载到所选目标中。
Load Selected into Target|Cargar selección en el destino|Charger la sélection dans la cible|将所选资源加载到目标
Source frame (s)|Tiempo de origen (s)|Temps source (s)|源动作时间（秒）
Extract Frame as Editable Pose|Extraer pose editable|Extraire une pose modifiable|提取当前帧为可编辑姿势
Independent pose / saved motion window|Pose independiente / poses guardadas|Pose indépendante / poses enregistrées|独立姿势／已保存姿势
Pose name|Nombre de la pose|Nom de la pose|姿势名称
Save Pose As...|Guardar pose como...|Enregistrer la pose sous...|另存为新姿势...
Orbit: right drag. Pan XY: middle drag. Zoom: wheel. Left click selects a joint.|Botón derecho: orbitar. Central: desplazar XY. Rueda: zoom. Clic izquierdo: seleccionar articulación.|Glisser à droite : orbite. Bouton central : déplacement XY. Molette : zoom. Clic gauche : articulation.|右键拖动：旋转；中键拖动：画面XY平移；滚轮：缩放；左键：选择关节。
+ Target|+ Destino|+ Cible|＋目标
Remove|Quitar|Retirer|移除
Name|Nombre|Nom|名称
Edit Bones|Editar huesos|Modifier les os|编辑骨骼
Undo|Deshacer|Annuler|撤销
Redo|Rehacer|Rétablir|重做
Placement|Colocación|Placement|放置
Translation:|Posición:|Position :|位置：
Rotation:|Rotación:|Rotation :|旋转：
Tool|Herramienta|Outil|工具
Rotate Bone (FK)|Rotar hueso (FK)|Rotation d’os (FK)|骨骼旋转（FK）
Move Joint (IK)|Mover articulación (IK)|Déplacer l’articulation (IK)|移动关节（IK）
Find bone|Buscar hueso|Rechercher un os|搜索骨骼
Local rotation|Rotación local|Rotation locale|局部旋转
Reset Bone|Restablecer hueso|Réinitialiser l’os|重置所选骨骼
Restore only this bone rotation to the skeleton rest pose. Undo is available.|Restaura solo la rotación de este hueso a la pose de referencia. Se puede deshacer.|Rétablit uniquement la rotation de cet os selon la pose de référence. Annulation possible.|仅将所选骨骼旋转恢复到骨架基准姿势。可以撤销。
Drag the joint gizmo. IK preserves bone lengths; best on hands / feet.|Arrastre el manipulador. La IK conserva las longitudes; funciona mejor en manos y pies.|Faites glisser le manipulateur. L’IK préserve la longueur des os ; idéale pour les mains et pieds.|拖动关节操作器。IK保持骨骼长度，适合操作手部和脚部。
Generation Settings|Ajustes de generación|Paramètres de génération|动作生成设置
Tokens to Generate:|Tokens a generar:|Jetons à générer :|生成标记数：
Tokens to Generate|Tokens a generar|Jetons à générer|生成标记数
Target poses|Poses de destino|Poses cibles|连续目标姿势数
Hold frames|Fotogramas de espera|Images de maintien|到达后保持帧数
Transition duration (s)|Duración del tramo (s)|Durée du segment (s)|此段时长（秒）
0 = automatic. Duration is baked into the generated motion and FBX.|0 = automático. La duración se aplica al movimiento generado y al FBX.|0 = automatique. La durée est intégrée au mouvement généré et au FBX.|0表示自动。指定时长将应用于生成动作和FBX。
Large duration changes can cause foot sliding or slow-motion movement.|Los cambios grandes de duración pueden causar deslizamiento de pies o cámara lenta.|Un changement important de durée peut entraîner un glissement des pieds ou un effet de ralenti.|大幅改变时长可能导致脚部滑动或慢动作效果。
Generate Motion|Generar movimiento|Générer le mouvement|生成动作
Pause|Pausa|Pause|暂停
Play|Reproducir|Lire|播放
Loop|Bucle|Boucle|循环
Show target poses|Mostrar destinos|Afficher les poses cibles|显示目标姿势
Show generated motion|Mostrar movimiento generado|Afficher le mouvement généré|显示生成动作
Time|Posición|Position|播放位置
Preview speed|Velocidad de vista previa|Vitesse d’aperçu|预览速度
Preview speed does not change FBX duration.|La velocidad de vista previa no cambia la duración del FBX.|La vitesse d’aperçu ne modifie pas la durée du FBX.|预览速度不会改变FBX的时长。
Targets changed. Generate again to update this preview.|Los destinos han cambiado. Vuelva a generar para actualizar la vista previa.|Les cibles ont changé. Régénérez pour actualiser l’aperçu.|目标已更改。请重新生成以更新预览。
Capture Playback as New Target|Capturar pose como nuevo destino|Capturer la pose comme nouvelle cible|将当前姿势捕获为新目标
In-place (remove XY travel)|En el sitio (sin desplazamiento XY)|Sur place (sans déplacement XY)|原地播放（移除水平位移）
Include preview mesh|Incluir malla de vista previa|Inclure le maillage d’aperçu|包含预览网格
Export FBX...|Exportar FBX...|Exporter un FBX...|导出FBX...
Working...|Procesando...|Traitement en cours...|处理中...
Studio Error|Error|Erreur|错误
OK|Aceptar|OK|确定
Copy and Add|Copiar y añadir|Copier et ajouter|复制并添加
Copy|Copia|Copie|副本
English|English|English|English
Japanese|日本語|日本語|日本語
Reset|Restablecer|Réinitialiser|重置
Reset All|Restablecer todo|Tout réinitialiser|全部重置
Lock|Bloquear|Verrouiller|锁定
Unlock|Desbloquear|Déverrouiller|解锁
Select a motion, choose a frame, then edit a bone.|Seleccione un movimiento y un fotograma; después, edite un hueso.|Sélectionnez un mouvement et une image, puis modifiez un os.|选择动作和帧，然后编辑骨骼。
Edited pose. Save Pose registers it in your library.|Pose editada. Guárdela para registrarla en la biblioteca.|Pose modifiée. Enregistrez-la pour l’ajouter à la bibliothèque.|姿势已编辑。保存后会加入资源库。
Generating motion... You can still orbit the camera.|Generando movimiento... Puede seguir moviendo la cámara.|Génération du mouvement... Vous pouvez toujours déplacer la caméra.|正在生成动作，仍可操作相机。
Exporting FBX in the background...|Exportando FBX en segundo plano...|Exportation du FBX en arrière-plan...|正在后台导出FBX...
Preparing motion generation...|Preparando la generación...|Préparation de la génération...|正在准备动作生成...
Open Project|Abrir proyecto|Ouvrir un projet|打开项目
Save Project|Guardar proyecto|Enregistrer le projet|保存项目
Save Project As|Guardar proyecto como|Enregistrer le projet sous|项目另存为
Import SOMA motion|Importar movimiento SOMA|Importer un mouvement SOMA|导入SOMA动作
Load Pose|Cargar pose|Charger une pose|加载姿势
Save New Pose|Guardar nueva pose|Enregistrer une nouvelle pose|保存新姿势
Export FBX|Exportar FBX|Exporter un FBX|导出FBX
Studio poses|Poses de Studio|Poses Studio|Studio姿势
Studio projects|Proyectos de Studio|Projets Studio|Studio项目
SOMA BVH motion|Movimiento BVH de SOMA|Mouvement BVH SOMA|SOMA的BVH动作
FBX animation|Animación FBX|Animation FBX|FBX动画
Start|Inicio|Départ|起始
Target|Destino|Cible|目标
Loaded |Cargado: |Chargé : |已加载：
Saved pose: |Pose guardada: |Pose enregistrée : |已保存姿势：
Saved project: |Proyecto guardado: |Projet enregistré : |已保存项目：
Opened project: |Proyecto abierto: |Projet ouvert : |已打开项目：
Exported: |Exportado: |Exporté : |已导出：
Raw frames: |Fotogramas originales: |Images brutes : |原始帧数：
Pose moved to deleted_poses: |Pose movida a deleted_poses: |Pose déplacée vers deleted_poses : |姿势已移至deleted_poses：
[POSE] |[POSE] |[POSE] |[姿势] 
[MOTION] |[MOVIMIENTO] |[MOUVEMENT] |[动作] 
  * unsaved|  * sin guardar|  * non enregistré|  ＊未保存
'''

TABLES={code:{} for code in ('es','fr','zh')}
from .studio_motion_i18n import TRANSLATIONS as MOTION_TRANSLATIONS
for _code in TABLES:TABLES[_code].update(MOTION_TRANSLATIONS[_code])
for row in ROWS.strip('\n').splitlines():
    en,es,fr,zh=row.split('|')
    for code,value in [('es',es),('fr',fr),('zh',zh)]:TABLES[code][en]=value
for code,value in [('es','Idiomas / Languages'),('fr','Langues / Languages'),('zh','语言 / Languages')]:
    TABLES[code]['Languages / 言語']=value

PARTS={
 'Hips':('Pelvis','Bassin','骨盆'),'Spine1':('Columna 1','Colonne 1','脊柱1'),
 'Spine2':('Columna 2','Colonne 2','脊柱2'),'Chest':('Pecho','Poitrine','胸部'),
 'Neck1':('Cuello 1','Cou 1','颈部1'),'Neck2':('Cuello 2','Cou 2','颈部2'),
 'Head':('Cabeza','Tête','头部'),'HeadEnd':('Extremo de cabeza','Extrémité de tête','头部末端'),
 'Shoulder':('Hombro','Épaule','肩部'),'Arm':('Brazo','Bras','上臂'),
 'ForeArm':('Antebrazo','Avant-bras','前臂'),'Hand':('Mano','Main','手部'),
 'Leg':('Muslo','Cuisse','大腿'),'Shin':('Pantorrilla','Jambe','小腿'),
 'Foot':('Pie','Pied','脚部'),'ToeBase':('Dedos del pie','Orteils','脚趾'),
 'ToeEnd':('Extremo de dedos','Extrémité des orteils','脚趾末端')}
for name,values in PARTS.items():
    for col,code in enumerate(('es','fr','zh')):
        if name in ('Hips','Spine1','Spine2','Chest','Neck1','Neck2','Head','HeadEnd'):
            TABLES[code][name]=values[col]
        else:
            for side,es,fr,zh in [('Left','Izq.','Gauche','左'),('Right','Der.','Droite','右')]:
                TABLES[code][side+name]=({'es':es,'fr':fr,'zh':zh}[code]+('' if code=='zh' else ' ')+values[col]).strip()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
