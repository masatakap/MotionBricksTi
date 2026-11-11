"""Offline, searchable user guide in every supported UI language."""
TOPICS=('workflow','pose','library','timing','playback','saving','fbx','vmd','mp4','requirements')
GUIDES={
'ja':[
('基本の制作手順', 'ターゲット一覧で開始・目標ポーズを選び、左のライブラリから素材を読み込みます。元モーションの時刻を選び、必要なら「このフレームを編集用ポーズにする」を押します。ポーズの順序と配置を整え、「モーションを生成」を実行してください。生成結果は再生タイムラインで確認し、「書き出し」メニューから保存できます。'),
('カメラ・ボーン編集・左右反転', '右ドラッグでカメラを回転、中ボタンドラッグで画面の水平・垂直方向へ移動、ホイールでズームします。左クリックで関節を選び、ギズモまたはローカル回転の数値で編集します。FKは骨の回転、簡易IKは親関節を回して手足を目標へ近づける操作です。リセットは選択ボーンの回転を骨格の基準姿勢へ戻します。「ポーズを左右反転」は位置と身体の向きを保って左右を交換します。編集・反転はUndo/Redo、Ctrl+Z/Ctrl+Yで戻せます。'),
('ライブラリ・ターゲットの管理', 'モーション素材をダブルクリックすると選択中のターゲットへ読み込みます。外部BVHはSOMA互換の骨格・関節名・単位が必要です。右クリックの「コピーして追加」で独立したターゲットを複製できます。行をドラッグし、別の行の上半分・下半分へドロップすると前・後ろへ移動します。先頭が開始ポーズです。名前は入力欄または行のダブルクリックで変更できます。「保存ポーズを削除」はファイルをuser_data/deleted_posesへ退避します。復元はそのファイルを読み込んでください。配置済みターゲットは保持します。'),
('生成する動きの尺・保持時間', '生成設定の「この区間の尺」は直前のポーズから選択した目標へ到達するまでの秒数です。0は自動、指定は最大60秒。変更後に再生成するとFBX・VMD・MP4にも反映されます。30fpsのフレーム単位へ丸めます。「到達後に保持するフレーム数」はその尺に追加されます。目標の連続ポーズ数1は静止目標、4はモーションの速度を含む接続に使います。大幅な尺変更では足滑りやスローモーション感が出ることがあります。'),
('再生タイムライン・音との同期', '音を読み込んでいない状態では生成したモーションの尺で再生・一時停止・停止・シークできます。MP3またはWAVを読み込むと音の尺に切り替わり、音と姿勢が連動します。一時停止中のシークはその姿勢で停止し、停止ボタンは先頭へ戻します。音がモーションより長い場合は最後の姿勢を保持します。音がない時は確認用の再生速度とループを使えます。確認用の速度は書き出しデータを変えません。音は現在のセッションで使用し、再起動後は読み込み直してください。'),
('保存・可逆圧縮・自動復旧', 'ポーズは.pose.json、プロジェクトは.mbstudio.jsonで保存します。中身は数値を丸めないgzip可逆圧縮で、従来の非圧縮JSONも読み込めます。通常のテキストエディターでは圧縮ファイルを直接編集できません。Ctrl+Sでプロジェクトを保存できます。プロジェクトにはポーズ・順序・配置・生成設定を保持しますが、生成済みモーションも保存します。音源ファイルは別途読み込みます。編集内容は約5秒ごとに自動保存し、「プロジェクト → 自動保存から復旧」で開けます。ポーズ数500件・32MBの固定制限は撤廃済みですが、メモリとGPU容量による実際の限界はあります。'),
('FBX書き出し', '生成後に「書き出し → FBXを書き出す」を選びます。30fpsの骨格アニメーションをベイクし、RootMotionボーンへ水平移動と旋回を分けます。「その場で再生」は水平移動を除きます。プレビューメッシュを含めれば、UE側でSOMAのSkeletal MeshとSkeletonを作成できます。Mannyなど別骨格へ移すにはIK Rig/IK Retargeterによる対応付けが必要です。'),
('MMD向けVMD・PMXまたはPMD', '実際に動かすPMXまたはPMDを「書き出し」メニューから選択し、生成済みモーションをVMDへ書き出します。対象モデルの骨格・基準姿勢・体格に合わせたFK変換です。センターへ移動を記録し、FKと競合しないよう先頭フレームでIKを無効化します。対応は標準的な日本語ボーン名、PMX 2.0/2.1、PMD 1.0です。特殊な付与回転を含む対象階層などは未対応です。表情・カメラ・物理や足接地IKの再計算は含みません。変換内容は.vmd.report.jsonにも保存します。モデルごとの見た目の調整が必要な場合があります。'),
('現在のカメラでリファレンスMP4', 'モーション生成後、カメラの位置・向き・ズームを整え、「書き出し → 現在のカメラでMP4」を選びます。先頭から終端まで、現在の描画解像度・30fpsで書き出します。操作パネル・ターゲット・編集ギズモは入りません。音楽を含める設定では、短い音源の残りは無音、長い音源はモーションの尺で切ります。書き出し中はウィンドウサイズを変えないでください。進行フレーム数はタイトルバーへ表示し、終了後は再生位置と表示設定を戻します。'),
('動作環境・言語・対応範囲', '対応するNVIDIA GPUとドライバーが必要です。初回はTensorRTエンジンの構築に時間がかかり、次回以降はキャッシュを利用します。内部の生成骨格はSOMAです。UE連携ではモデル別の骨格変換、環境機能では境界ボックスを使う経路配置に対応します。任意形状への全身接触や表情生成は対象外です。表示言語はLanguagesメニューで日本語・English・Español・Français・简体中文から選び、次回起動にも保持します。モーション素材の利用条件はアプリ本体と別です。同梱サンプルは評価用途の条件を確認してください。公式の元デモはLaunch Original MotionBricks.cmdから開けます。TiはNVIDIA公式製品ではない独自拡張です。'),
],
'en':[
('Basic workflow', 'Select a start or target pose in the target list, then load a clip from the library. Choose its source time and optionally extract an editable static pose. Arrange the targets and their placement, then generate motion. Inspect the result on the playback timeline and save it from the Export menu.'),
('Camera, bones and pose mirroring', 'Right-drag orbits the camera; middle-drag pans horizontally and vertically; the wheel zooms. Left-click a joint and use the gizmo or local rotation values. FK rotates bones; simple IK rotates ancestors to bring hands or feet toward a goal. Reset restores only the selected bone rotation to the skeleton rest pose. Mirror Pose swaps left and right while preserving root position and facing. Undo/Redo and Ctrl+Z/Ctrl+Y restore edits and mirroring.'),
('Library and target management', 'Double-click a library item to load it into the selected target. External BVH needs a SOMA-compatible skeleton, names and units. Right-click a target and choose Copy and Add for an independent copy. Drag a row onto the upper or lower half of another row to move it before or after that row. The first row is the start pose. Rename through the name field or a double-click. Delete Saved Pose moves the file to user_data/deleted_poses; load that file to recover it. Placed targets keep their data.'),
('Transition duration and holds', 'Transition duration specifies seconds from the previous pose to the selected target. Zero is automatic; explicit durations support up to 60 seconds. Regenerate after changing it; the result affects FBX, VMD and MP4. Times are rounded to 30 fps frame boundaries. Hold frames adds time after arrival. One target pose specifies a static goal; four can retain motion velocity at a transition. Large timing changes can cause foot sliding or a slow-motion appearance.'),
('Playback timeline and music synchronization', 'Without music, playback, pause, stop and seeking use the generated motion duration. Loading MP3 or WAV switches the timeline to the music duration and links audio with pose display. Seeking while paused holds that pose; Stop returns to the beginning. After the motion ends, longer music holds the last pose. With no music, preview speed and looping are available. Preview speed does not change exported data. Audio is used in the current session and must be loaded again after restarting.'),
('Saving, lossless compression and recovery', 'Save poses as .pose.json and projects as .mbstudio.json. Both use lossless gzip compression without rounding numbers; legacy plain JSON still loads. Compressed files cannot be edited directly in a text editor. Ctrl+S saves the project. Projects retain poses, order, placement and generation settings, and generated motion; audio files must be loaded separately. Edits autosave about every five seconds; use Project > Recover Autosave. The fixed 500-pose and 32 MB limits have been removed, while RAM and GPU memory still impose practical limits.'),
('FBX export', 'After generation, choose Export > Export FBX. Animation is baked at 30 fps, with horizontal travel and turning separated into RootMotion. In-place removes horizontal travel. Including the preview mesh lets UE create a SOMA Skeletal Mesh and Skeleton. Other skeletons, such as Manny, require mapping through IK Rig/IK Retargeter.'),
('MMD VMD with PMX or PMD', 'Choose the actual target PMX or PMD from Export, then export the generated motion as VMD. FK conversion uses that model’s hierarchy, rest pose and proportions. Movement goes to the center bone; IK is disabled at frame zero to avoid conflicting with FK. Supported targets use standard Japanese bone names, PMX 2.0/2.1 or PMD 1.0. Special inherited transforms in the driven hierarchy are unsupported. Facial expressions, camera, physics and foot-contact IK reconstruction are excluded. A .vmd.report.json records the conversion. Individual models may need visual adjustment.'),
('Reference MP4 from the current camera', 'Set camera position, orientation and zoom, then choose Export > Export Reference MP4. It renders the entire motion at the current viewport resolution and 30 fps. Panels, target previews and editing gizmos are excluded. Optional music is padded with silence when shorter or trimmed when longer than the motion. Keep the window size fixed while exporting. Progress appears in the title bar; playback position and display settings are restored afterward.'),
('Requirements, languages and scope', 'A supported NVIDIA GPU and driver are required. Initial TensorRT engine preparation can take time; later launches use its cache. Generation uses SOMA. The UE bridge supports calibrated skeleton conversion and the environment planner uses bounding boxes for routing. General full-body contact solving and facial generation are outside its scope. Choose Japanese, English, Spanish, French or Simplified Chinese from Languages; the choice persists. Motion assets have separate terms; bundled samples are subject to evaluation-use conditions. Launch Original MotionBricks.cmd opens the original official demo. Ti is an independent extension, not an official NVIDIA product.'),
],
'es':[
('Flujo de trabajo básico', 'Seleccione la pose inicial o un destino y cargue un clip desde la biblioteca. Elija el tiempo de origen y, si lo necesita, extraiga una pose estática editable. Ordene y coloque los destinos; después, genere el movimiento. Revise el resultado en la línea de tiempo y guárdelo desde Exportar.'),
('Cámara, huesos y reflejo de poses', 'Arrastre con el botón derecho para orbitar, con el central para desplazar y use la rueda para acercar. Seleccione una articulación con el botón izquierdo y edite el manipulador o la rotación local. FK rota huesos; la IK sencilla rota sus antecesores para acercar manos o pies al objetivo. Restablecer devuelve la rotación del hueso seleccionado a la pose de referencia. Reflejar pose intercambia izquierda y derecha sin cambiar la posición ni la orientación del cuerpo. Deshacer/Rehacer y Ctrl+Z/Ctrl+Y permiten recuperar la edición anterior.'),
('Biblioteca y gestión de destinos', 'Haga doble clic en un recurso para cargarlo en el destino seleccionado. El BVH externo debe tener esqueleto, nombres y unidades compatibles con SOMA. Copiar y añadir, en el menú contextual, crea una copia independiente. Arrastre una fila a la mitad superior o inferior de otra para colocarla antes o después. La primera fila es la pose inicial. Cambie el nombre en su campo o con doble clic. Eliminar pose guardada mueve el archivo a user_data/deleted_poses; cárguelo para recuperarlo. Los destinos ya colocados conservan sus datos.'),
('Duración de transiciones y esperas', 'La duración del tramo indica los segundos desde la pose anterior hasta el destino seleccionado. Cero es automático; el máximo explícito es 60 segundos. Regenere tras cambiarla: afecta al FBX, VMD y MP4. El tiempo se redondea a fotogramas de 30 fps. Los fotogramas de espera se añaden al llegar. Una pose de destino define un objetivo estático; cuatro pueden conservar la velocidad de un clip. Los cambios grandes pueden producir deslizamiento de pies o un aspecto de cámara lenta.'),
('Línea de tiempo y música', 'Sin música, reproducir, pausar, detener y buscar usan la duración del movimiento generado. Al cargar MP3 o WAV, se usa la duración de la música y el sonido queda ligado a la pose. Si busca estando en pausa, la pose se mantiene en ese instante; Detener vuelve al inicio. Si la música es más larga, se mantiene la última pose al terminar el movimiento. Sin música puede usar velocidad de vista previa y bucle. Esa velocidad no cambia la exportación. Debe volver a cargar el audio después de reiniciar.'),
('Guardado, compresión sin pérdidas y recuperación', 'Guarde poses como .pose.json y proyectos como .mbstudio.json. Usan gzip sin pérdidas y sin redondear los números; también se leen los JSON antiguos sin comprimir. Los archivos comprimidos no se editan directamente como texto. Ctrl+S guarda el proyecto. Se conservan poses, orden, colocación y ajustes, también el movimiento generado; el audio se carga por separado. Hay autoguardado aproximadamente cada cinco segundos; use Proyecto > Recuperar autoguardado. Se quitaron los límites fijos de 500 poses y 32 MB; la RAM y la memoria de la GPU siguen limitando la capacidad real.'),
('Exportar FBX', 'Después de generar, elija Exportar > Exportar FBX. La animación se hornea a 30 fps; el desplazamiento horizontal y el giro se separan en RootMotion. En el sitio elimina el desplazamiento horizontal. Incluir la malla permite crear en UE un Skeletal Mesh y un Skeleton de SOMA. Otros esqueletos, como Manny, requieren correspondencias mediante IK Rig/IK Retargeter.'),
('VMD para MMD con PMX o PMD', 'Seleccione en Exportar el PMX o PMD que vaya a animar y exporte el movimiento generado a VMD. La conversión FK usa su jerarquía, pose de referencia y proporciones. El desplazamiento va al hueso central y la IK se desactiva en el fotograma cero. Se admiten nombres japoneses estándar, PMX 2.0/2.1 y PMD 1.0. No se admiten ciertas transformaciones heredadas en la cadena animada. No se exportan expresiones, cámara, física ni reconstrucción de IK de contacto. El archivo .vmd.report.json registra la conversión. Cada modelo puede necesitar ajustes visuales.'),
('MP4 de referencia con la cámara actual', 'Ajuste la posición, orientación y zoom de la cámara; después, elija Exportar > Exportar MP4 con esta cámara. Se renderiza todo el movimiento a la resolución actual y 30 fps, sin paneles, destinos ni manipuladores. La música opcional se rellena con silencio si es corta o se recorta si es larga. No cambie el tamaño de la ventana durante la exportación. El título muestra el progreso; al finalizar se recuperan la posición de reproducción y los ajustes de vista.'),
('Requisitos, idiomas y alcance', 'Se requiere una GPU NVIDIA compatible y su controlador. La primera preparación de TensorRT puede tardar; después se usa la caché. La generación utiliza SOMA. El puente UE admite conversión de esqueleto calibrada y el entorno planifica rutas con cajas. No incluye contacto completo general ni generación facial. El menú de idiomas ofrece japonés, inglés, español, francés y chino simplificado; la selección se conserva. Los recursos de movimiento tienen licencias separadas; revise las condiciones de evaluación de las muestras incluidas. Launch Original MotionBricks.cmd abre la demostración oficial original. Ti es una extensión independiente, no un producto oficial de NVIDIA.'),
],
'fr':[
('Procédure de création', 'Sélectionnez la pose de départ ou une cible, puis chargez un clip depuis la bibliothèque. Choisissez le temps source et, si nécessaire, extrayez une pose statique modifiable. Réglez l’ordre et le placement des cibles, puis générez le mouvement. Vérifiez le résultat dans la chronologie et enregistrez-le depuis Exporter.'),
('Caméra, os et inversion de pose', 'Glissez avec le bouton droit pour orbiter, avec le bouton central pour déplacer la caméra et utilisez la molette pour zoomer. Sélectionnez une articulation avec le bouton gauche et modifiez le manipulateur ou la rotation locale. La FK fait tourner les os ; l’IK simple tourne les parents pour rapprocher une main ou un pied d’un point. Réinitialiser rétablit la rotation de l’os sélectionné selon la pose de référence. Inverser la pose échange gauche et droite en conservant la position et l’orientation du corps. Annuler/Rétablir et Ctrl+Z/Ctrl+Y restaurent les modifications.'),
('Bibliothèque et gestion des cibles', 'Double-cliquez sur un élément pour le charger dans la cible sélectionnée. Un BVH externe doit avoir un squelette, des noms et des unités compatibles avec SOMA. Copier et ajouter, dans le menu contextuel, crée une copie indépendante. Glissez une ligne dans la moitié supérieure ou inférieure d’une autre pour la placer avant ou après. La première ligne est la pose de départ. Renommez dans le champ ou par double-clic. Supprimer la pose enregistrée déplace le fichier vers user_data/deleted_poses ; rechargez-le pour le récupérer. Les cibles déjà placées conservent leurs données.'),
('Durée des transitions et maintien', 'La durée du segment indique le temps entre la pose précédente et la cible sélectionnée. Zéro signifie automatique ; la durée explicite maximale est de 60 secondes. Régénérez après modification : la durée est appliquée aux FBX, VMD et MP4. Elle est arrondie à une image à 30 fps. Les images de maintien s’ajoutent après l’arrivée. Une pose cible définit un objectif statique ; quatre peuvent conserver la vitesse du clip. De grands changements peuvent provoquer un glissement des pieds ou un effet de ralenti.'),
('Chronologie et synchronisation musicale', 'Sans musique, lecture, pause, arrêt et déplacement temporel utilisent la durée du mouvement généré. Charger un MP3 ou WAV bascule vers la durée de la musique et lie le son à la pose affichée. Un déplacement en pause maintient la pose à cet instant ; Arrêter revient au début. Si la musique est plus longue, la dernière pose est maintenue après la fin du mouvement. Sans musique, la vitesse d’aperçu et la boucle sont disponibles. Cette vitesse ne modifie pas les exports. Rechargez l’audio après un redémarrage.'),
('Enregistrement, compression sans perte et récupération', 'Les poses utilisent .pose.json et les projets .mbstudio.json. La compression gzip est sans perte, sans arrondir les nombres ; les anciens JSON non compressés restent lisibles. Les fichiers compressés ne sont pas directement modifiables dans un éditeur de texte. Ctrl+S enregistre le projet. Il conserve poses, ordre, placement et paramètres, ainsi que le mouvement généré ; l’audio se charge séparément. Une sauvegarde automatique a lieu environ toutes les cinq secondes ; utilisez Projet > Récupérer la sauvegarde auto. Les limites fixes de 500 poses et 32 Mo sont supprimées ; la RAM et la mémoire GPU restent des limites pratiques.'),
('Export FBX', 'Après génération, choisissez Exporter > Exporter un FBX. L’animation est calculée à 30 fps ; déplacement horizontal et rotation sont séparés dans RootMotion. Sur place supprime le déplacement horizontal. Inclure le maillage permet à UE de créer un Skeletal Mesh et un Skeleton SOMA. Un autre squelette, comme Manny, nécessite une correspondance via IK Rig/IK Retargeter.'),
('VMD pour MMD avec PMX ou PMD', 'Sélectionnez dans Exporter le PMX ou PMD à animer, puis exportez le mouvement généré en VMD. La conversion FK utilise sa hiérarchie, sa pose de référence et ses proportions. Le déplacement va dans l’os central ; l’IK est désactivée à l’image zéro. Les noms japonais standard, PMX 2.0/2.1 et PMD 1.0 sont pris en charge. Certaines transformations héritées dans la chaîne animée ne le sont pas. Expressions, caméra, physique et reconstruction de l’IK de contact sont exclues. Le fichier .vmd.report.json décrit la conversion. Un ajustement visuel par modèle peut être nécessaire.'),
('MP4 de référence depuis la caméra actuelle', 'Réglez position, orientation et zoom de la caméra, puis choisissez Exporter > Exporter un MP4 avec cette caméra. Le mouvement entier est rendu à la résolution actuelle et à 30 fps, sans panneaux, poses cibles ni manipulateurs. La musique facultative est complétée par du silence si elle est courte, ou coupée si elle est longue. Ne redimensionnez pas la fenêtre pendant l’export. La progression apparaît dans le titre ; la position de lecture et les réglages d’affichage sont ensuite rétablis.'),
('Configuration, langues et limites', 'Une carte NVIDIA compatible et son pilote sont nécessaires. La première préparation TensorRT peut prendre du temps ; les démarrages suivants utilisent le cache. La génération utilise SOMA. Le pont UE permet une conversion calibrée du squelette et le parcours utilise des boîtes. Le contact intégral général et les expressions faciales ne sont pas pris en charge. Le menu des langues propose japonais, anglais, espagnol, français et chinois simplifié ; le choix est conservé. Les mouvements ont leurs propres licences ; vérifiez les conditions d’évaluation des exemples fournis. Launch Original MotionBricks.cmd ouvre la démo officielle d’origine. Ti est une extension indépendante, pas un produit officiel NVIDIA.'),
],
'zh':[
('基本制作流程', '在目标列表中选择起始或目标姿势，再从左侧资源库加载动作。选择源动作时间，需要时提取为可编辑的静态姿势。调整目标顺序和放置位置，然后生成动作。在播放时间轴中检查结果，最后通过“导出”菜单保存。'),
('相机、骨骼编辑与左右镜像', '右键拖动旋转相机，中键拖动在画面水平和垂直方向平移，滚轮缩放。左键选择关节，通过操作器或局部旋转数值编辑。FK旋转骨骼；简易IK旋转父关节，使手脚接近目标点。重置仅恢复所选骨骼的基准旋转。左右镜像交换左右姿势，保持根部位置和身体朝向不变。编辑和镜像均可通过撤销／重做或Ctrl+Z／Ctrl+Y恢复。'),
('资源库与目标管理', '双击资源可将其加载到所选目标。外部BVH需要兼容SOMA的骨架、名称和单位。右键菜单的“复制并添加”会创建独立副本。将一行拖到另一行的上半部分或下半部分，可移至其前面或后面。第一行是起始姿势。使用名称输入框或双击行可重命名。“删除已保存姿势”会将文件移至user_data/deleted_poses，重新加载该文件即可恢复。已放置的目标保留自身数据。'),
('过渡时长与保持帧', '此段时长表示从前一个姿势到所选目标的秒数。0为自动，显式时长最多60秒。修改后需要重新生成，结果会应用于FBX、VMD和MP4，并按30fps的帧间隔取整。保持帧数会在到达目标后额外增加时间。连续目标姿势数为1时使用静态目标，为4时可保留片段速度进行衔接。大幅改变时长可能造成脚部滑动或慢动作效果。'),
('播放时间轴与音乐同步', '没有音乐时，播放、暂停、停止和定位使用生成动作的时长。加载MP3或WAV后，时间轴切换为音乐时长，音频与姿势显示联动。暂停中定位会停留在对应姿势；停止会返回起点。音乐比动作长时，动作结束后保持最后一个姿势。没有音乐时可使用预览速度和循环，预览速度不会改变导出数据。音频仅用于当前会话，重启后需要重新加载。'),
('保存、无损压缩与自动恢复', '姿势保存为.pose.json，项目保存为.mbstudio.json。均使用不舍入数值的gzip无损压缩，也能读取旧版未压缩JSON。压缩文件不能直接用普通文本编辑器修改。Ctrl+S保存项目。项目保留姿势、顺序、放置和生成设置，并保存生成动作；音频文件需要另行加载。编辑内容约每5秒自动保存，可通过“项目 → 恢复自动保存”打开。固定的500姿势和32MB限制已移除，但实际容量仍受内存和显存限制。'),
('导出FBX', '生成后选择“导出 → 导出FBX”。骨骼动画按30fps烘焙，水平位移和转向分离到RootMotion骨骼。“原地播放”会移除水平位移。包含预览网格后，UE可创建SOMA的Skeletal Mesh和Skeleton。转换到Manny等其他骨架时，需要使用IK Rig／IK Retargeter建立对应关系。'),
('MMD的VMD与PMX或PMD', '通过“导出”选择实际要驱动的PMX或PMD，再导出生成动作的VMD。FK转换参考目标模型的层级、基准姿势和比例。位移写入中心骨骼，并在第0帧禁用IK以避免与FK冲突。支持标准日文骨骼名、PMX 2.0／2.1和PMD 1.0。驱动链中的某些附加继承变换不受支持。不导出表情、相机、物理，也不会重算脚部接触IK。转换信息同时写入.vmd.report.json。不同模型可能需要额外调整外观。'),
('按当前相机导出参考MP4', '调整相机位置、朝向和缩放，再选择“导出 → 按当前相机导出参考MP4”。按当前视图分辨率和30fps输出完整动作，不包含操作面板、目标预览或编辑操作器。可选的音乐短于动作时补静音，长于动作时按动作时长截断。导出过程中不要改变窗口大小。标题栏显示进度，完成后恢复播放位置和显示设置。'),
('运行要求、语言与功能范围', '需要受支持的NVIDIA显卡及驱动。首次准备TensorRT引擎可能较慢，之后会使用缓存。内部动作生成使用SOMA。UE桥接支持校准后的骨架转换，环境功能使用边界方块规划路径。不包含通用全身接触求解或表情生成。语言菜单可选择日语、英语、西班牙语、法语和简体中文，并记住下次启动的选择。动作素材的许可与应用本体不同；请确认附带示例的评估用途条件。Launch Original MotionBricks.cmd可打开原版官方演示。Ti是独立扩展，并非NVIDIA官方产品。'),
]}


TOPICS=TOPICS+('authoring',)
AUTHORING_GUIDES={
 'ja':('自作動作のキー編集と登録','左の「新規動作（基準姿勢から）」は、収録クリップをコピーせず骨格の基準姿勢から新しいターゲットを作ります。「現在のポーズから動作を作成」は現在表示中の姿勢を種にするため、その素材の利用条件を引き継ぎます。編集画面で動作名・尺を指定し、編集するフレームを選んで右側のボーン編集やギズモを操作するとキーが自動追加されます。先頭と終端は最初からキーがあり、ほかのキーを保ったまま編集できます。キー一覧で時刻へ移動し、中間のキーは削除できます。動作内のルート位置は全身の移動、右側の配置は動作全体を置く位置です。キー間は位置の線形補間と回転の最短経路補間で再生します。Undo/Redoはキーを含む編集を戻します。「この時刻の連続4姿勢を使う」で生成条件の時刻を選びます。30fpsの4姿勢は0.1秒で、端では4姿勢全体を動作内へ寄せます。開始ポーズはその時刻へ入る動き、目標は出る動きを使います。「動作を名前を付けて保存」で.motion.jsonへ可逆圧縮保存し、ライブラリに［動作］として表示します。全キー・尺・生成条件を保持し、再読込後も編集できます。「新規ポーズとして保存」は表示中の静止姿勢だけを保存します。全尺再生がOFFの場合、モーション生成に渡すのは選んだ4姿勢であり、作った動作全体をそのまま再生する保証ではありません。公開用素材の入替・初期標準データの変更は別途行ってください。'),
 'en':('Authoring and saving your own motion','New Motion (Rest Pose) creates a target from the skeleton reference pose without copying a bundled motion clip. Motion from Current Pose uses the displayed pose and retains its source terms. Set a name and duration, select an editing frame, then edit bones or the gizmo to add a key automatically. First and last keys exist initially; other keys remain intact. Select keys to seek and delete interior keys when needed. Motion root position moves the body within the clip; Placement positions the whole clip in the scene. Preview interpolates translations linearly and rotations along the shortest path. Undo/Redo restores complete key edits. Use This Time (4 Poses) selects the conditioning time: four poses at 30 fps span 0.1 seconds, with the complete window moved inward at clip boundaries. Start uses incoming motion; targets use outgoing motion. Save Motion As writes a losslessly compressed .motion.json, shown as MOTION in the library, preserving all keys, duration and conditioning settings for later editing. Save Pose As saves only the displayed static pose. With entire-motion playback OFF, generation uses the selected four poses, not the entire authored clip verbatim. Replacing release assets and startup defaults is a separate step.'),
 'es':('Crear y guardar movimientos propios','Nuevo movimiento (pose de referencia) crea un destino sin copiar clips incluidos. Movimiento desde la pose actual conserva las condiciones de su fuente. Indique nombre y duración, elija un fotograma y edite huesos para añadir claves automáticamente sin perder las demás. Las claves inicial y final existen desde el principio; puede eliminar claves intermedias. La posición raíz mueve el cuerpo dentro del clip; Colocación sitúa todo el movimiento. La reproducción interpola posición y rotación por el camino más corto. Deshacer/Rehacer restaura las claves. Usar este instante (4 poses) elige una ventana de 0,1 segundos a 30 fps; se desplaza hacia dentro en los extremos. El inicio usa movimiento entrante y los destinos saliente. Guardar movimiento como crea un .motion.json comprimido sin pérdidas, mostrado como MOVIMIENTO, con claves, duración y condiciones editables. Guardar pose conserva solo la pose estática visible. Con la reproducción completa desactivada, la generación utiliza cuatro poses elegidas, no reproduce necesariamente todo el clip. Sustituir recursos y valores iniciales para publicar es un paso separado.'),
 'fr':('Créer et enregistrer ses mouvements','Nouveau mouvement (pose de référence) crée une cible sans copier les clips fournis. Mouvement depuis la pose actuelle conserve les conditions de sa source. Choisissez nom, durée et image, puis modifiez les os : une clé est ajoutée automatiquement en conservant les autres. Les clés de début et de fin existent au départ ; les clés intermédiaires peuvent être supprimées. La position racine déplace le corps dans le clip, Placement situe le clip entier. La lecture interpole les positions et les rotations selon le chemin le plus court. Annuler/Rétablir restaure les clés. Utiliser cet instant (4 poses) choisit une fenêtre de 0,1 seconde à 30 fps, déplacée vers l’intérieur aux extrémités. Le départ utilise le mouvement entrant, les cibles le sortant. Enregistrer le mouvement sous crée un .motion.json sans perte, classé MOUVEMENT, conservant clés, durée et conditions pour les modifier ensuite. Enregistrer une pose ne conserve que la pose statique affichée. Lorsque la lecture intégrale est désactivée, la génération reçoit quatre poses, pas le clip entier à reproduire exactement. Le remplacement des ressources et réglages de démarrage pour publication reste une étape séparée.'),
 'zh':('制作和保存自己的动作','“新建动作（基准姿势）”从骨架基准姿势创建新目标，不复制附带动作片段。“从当前姿势创建动作”采用当前显示的姿势，仍适用原素材条款。设置动作名称、时长，选择编辑帧，再编辑骨骼或操作器，会自动添加关键帧并保留其他关键帧。开始和结束处已有关键帧，可删除中间关键帧。动作根骨位置控制片段内的全身移动，“放置”控制整个动作在场景中的位置。播放使用位置线性插值和旋转最短路径插值，撤销／重做可恢复关键帧编辑。“使用此时刻（连续4姿势）”选择生成条件：30fps的4姿势跨越0.1秒，在边界处会将整个窗口移入片段内。起始姿势采用进入该时刻的动作，目标采用离开该时刻的动作。动作另存为.motion.json，使用无损压缩，库中显示为“动作”，保存全部关键帧、时长及条件时刻，重新加载后可继续编辑。保存姿势仅保存当前静态姿势。关闭完整播放时，生成接收选中的4姿势，不保证逐帧复现整个片段。发布资源替换和默认启动数据仍需另行修改。'),
}
for _language,_section in AUTHORING_GUIDES.items():GUIDES[_language].append(_section)

FBX_NOTES={
 'ja':'UE 5.7.2で読み込みを検証済みです。FBX専用の形式ではなく、UnityなどのFBX対応ソフトへの受け渡しも想定していますが、それらでの実機検証は未実施です。読み込み先により座標軸・単位・RootMotion設定の調整が必要な場合があります。',
 'en':'Import is verified in UE 5.7.2. This is a standard FBX file intended for exchange with other FBX-compatible applications, including Unity, which have not yet been tested. Axis, unit and RootMotion settings may require adjustment in the destination application.',
 'es':'La importación se verificó en UE 5.7.2. Es un FBX estándar para aplicaciones compatibles, incluido Unity; estas otras aplicaciones aún no se han probado. Puede ser necesario ajustar ejes, unidades y RootMotion.',
 'fr':'Import vérifié dans UE 5.7.2. Ce FBX standard est destiné aux logiciels compatibles, dont Unity ; ces autres logiciels ne sont pas encore testés. Les axes, unités et réglages RootMotion peuvent nécessiter un ajustement.',
 'zh':'已在UE 5.7.2中验证导入。此文件采用标准FBX格式，也面向Unity等兼容FBX的软件，但尚未在这些软件中进行实机验证。可能需要在目标软件中调整坐标轴、单位和RootMotion设置。',
}
for _language,_note in FBX_NOTES.items():
    _title,_body=GUIDES[_language][6]
    GUIDES[_language][6]=(_title,_body+' '+_note)


from .studio_ue_guide import GUIDE as UE_GUIDE,PLAYBACK_GUIDE as UE_PLAYBACK_GUIDE
TOPICS=TOPICS+('ue_bridge',)
for _language,_section in UE_GUIDE.items():GUIDES[_language].append(_section)

TOPICS=TOPICS+('ue_sequencer_playback',)
for _language,_section in UE_PLAYBACK_GUIDE.items():GUIDES[_language].append(_section)

from .studio_kimodo_link import label as kimodo_label
TOPICS=TOPICS+('kimodo_connection',)
for _language in GUIDES:
    GUIDES[_language].append((kimodo_label('title',_language),'\n\n'.join(kimodo_label(_key,_language) for _key in ('about','folder_hint','setup_order','check','start','workflow','conditions'))))

from .studio_external_panel import label as external_label
TOPICS=TOPICS+('external_fbx_bvh_import',)
for _language in GUIDES:
    GUIDES[_language].append((external_label('title',_language),'\n\n'.join(external_label(_key,_language) for _key in ('file','read','note','reference_hint','prepare','usage','draft_hint','cycle','transit_hint','save'))))

from .studio_scene_guide import GUIDE as SCENE_GUIDE
TOPICS=TOPICS+('environment',)
for _language,_section in SCENE_GUIDE.items():GUIDES[_language].append(_section)

TOPICS=TOPICS+('full_motion',)
FULL_MOTION_GUIDE={
'ja':('動作を最初から最後まで流す','全フレーム入りの動作をターゲットへ読み込み、「最初から最後まで必ず流す」をONにして「モーションを生成」を押します。配置位置まで移動してから動作を最初から最後まで再生し、その終了姿勢から次のターゲットへ移行します。先頭行をONにした場合は、その動作から開始します。動作が1件だけでも生成できます。OFFは従来の連続4姿勢を条件にした生成です。ONでは動作の途中の時刻を選んでも全体を省略しません。区間の尺と早めの遷移設定は到達までの移動に使い、全動作の末尾は切りません。保持フレームは動作の終了後に追加します。設定はプロジェクトと動作ファイルに保存され、ボーン編集と取り消しも使えます。音楽なしで生成結果の全尺を確認でき、FBX等にも全動作を含めて書き出せます。'),
'en':('Play an entire motion','Load a full motion into a target, turn Always Play Entire Motion ON, then Generate Motion. Travel reaches its first pose, every frame plays, and the final pose becomes the context for the next target. A first-row full motion starts immediately; a single full motion can also generate a timeline. OFF retains four-pose conditioning. Selecting another editing time does not trim a full motion. Duration and early transition settings affect the approach only; hold frames follow the complete motion. The setting is saved in projects and motion files. Verify the full timeline without music; exported animation includes the entire motion.'),
'es':('Reproducir un movimiento completo','Cargue un movimiento completo en un destino, active Reproducir movimiento completo y genere. Se llega a la primera pose, se reproducen todos los fotogramas y se continúa hacia el siguiente destino desde la pose final. En la primera fila comienza directamente; también funciona con un solo movimiento. Desactivado conserva las cuatro poses de condición. La duración y el recorte anticipado afectan solo al acercamiento; la espera sigue al movimiento completo. La opción se guarda en proyectos y movimientos. Revise toda la línea de tiempo sin música; la exportación incluye el movimiento completo.'),
'fr':('Lire un mouvement entier','Chargez un mouvement complet dans une cible, activez Lire tout le mouvement puis générez. Le personnage rejoint la première pose, lit toutes les images et poursuit vers la cible suivante depuis la pose finale. Une première ligne complète commence directement ; un seul mouvement peut produire une animation. Désactivé conserve les quatre poses de conditionnement. La durée et la transition anticipée concernent seulement l’approche ; l’attente suit le mouvement complet. Le réglage est enregistré. Vérifiez toute la durée sans musique ; l’export inclut le mouvement entier.'),
'zh':('从头到尾播放动作','将完整动作载入目标，开启“从头到尾完整播放”，然后生成。角色先到达初始姿势，再播放所有帧，最后从结束姿势衔接下一目标。首行动作会直接开始，只有一条完整动作也可生成时间线。关闭时仍使用连续4姿势作为条件。过渡时长与提前切换只影响到达前的移动，等待帧在完整动作结束后追加。设置保存在项目和动作文件中。请在无音乐时检查完整时间线；导出包含整个动作。')}
for _language,_section in FULL_MOTION_GUIDE.items():GUIDES[_language].append(_section)

TOPICS=TOPICS+('library_genres',)
LIBRARY_GUIDE={
'ja':('ライブラリのジャンル分け','ライブラリ上部の「カテゴリ」で一覧を絞り込みます。括弧内はジャンル全体の登録数で、検索も併用できます。自動分類はファイル名をもとに行い、名前から判別できないものは「未分類・その他」に入ります。項目を選び、ライブラリ上部の「選択項目のジャンル」で変更すると保存されます。「自動分類」に戻すこともできます。分類設定はlibrary_categories.jsonへ保存し、動作ファイルやキーは書き換えません。ジャンル変更は既存ターゲットや障害物用動作の割り当てを変更しません。該当項目がない場合は読み込みを無効にして、非表示の項目を誤って読み込まないようにしています。'),
'en':('Library genres','Use Genre above the library to narrow the list. Counts show all registered items in each genre; search works together with the genre filter. Automatic classification uses file names. Unknown names appear under Uncategorized / Other. Select an item and change Selected item genre above the list to save an override, or choose Automatic to reset it. The small library_categories.json index stores classifications without rewriting motion files or keys. Changing a genre does not replace existing targets or assign obstacle source clips. An empty filter disables loading so hidden items cannot be loaded by mistake.'),
'es':('Géneros de la biblioteca','Use Género para filtrar la biblioteca y combine el filtro con la búsqueda. Los números indican los elementos registrados de cada género. La clasificación automática usa nombres de archivo; los desconocidos aparecen en Sin categoría / Otros. Seleccione un elemento y cambie su género encima de la lista; Automático restaura la clasificación. Los ajustes se guardan en library_categories.json sin modificar claves ni archivos de movimiento. El género no sustituye destinos ni fuentes de obstáculos. Cuando no hay resultados, se desactiva la carga para evitar cargar elementos ocultos.'),
'fr':('Genres de la bibliothèque','Choisissez un genre au-dessus de la bibliothèque et combinez ce filtre avec la recherche. Les nombres indiquent les éléments enregistrés par genre. Le classement automatique utilise les noms de fichiers ; les noms inconnus vont dans Sans catégorie / Autres. Sélectionnez un élément et changez son genre au-dessus de la liste, ou choisissez Automatique. Le fichier library_categories.json conserve ce classement sans modifier les mouvements ni leurs clés. Le genre ne remplace pas les cibles ni les sources des obstacles. Sans résultat, le chargement est désactivé pour éviter de charger un élément masqué.'),
'zh':('动作库类别','在动作库上方选择类别，可与搜索同时使用。括号中的数字表示该类别的全部已登记项目数。自动分类根据文件名判断，无法识别的名称归入“未分类／其他”。选择项目后，在列表上方修改“所选项目类别”即可保存，也可选择自动分类恢复默认。分类保存在library_categories.json中，不改写动作文件或关键帧。更改类别不会替换已放置的目标，也不会自动设置障碍物动作来源。没有匹配结果时会禁用加载，避免误加载隐藏项目。')}
_CUSTOM_GENRES={
    'ja':'「＋新規ジャンル」で好きな名前の分類を追加できます。新しく保存・取り込みした素材や既存の素材を選び、ライブラリ上部の「選択項目のジャンル」から移動先を指定します。新しい素材が見えない場合は「すべてのジャンル」を表示してください。ジャンルを移動しても再生方式は素材の設定に従います。',
    'en':'Use + New genre to add a category. Select a new or existing item and move it using Selected item genre above the list. Switch to All genres if a newly saved or imported item is hidden. Moving an item preserves its playback behavior.',
    'es':'Use + Nuevo género para crear una categoría. Seleccione un elemento nuevo o existente y muévalo con Género del elemento. Si un elemento nuevo está oculto, elija Todos los géneros. El cambio de género conserva el modo de reproducción.',
    'fr':'Utilisez + Nouveau genre pour créer une catégorie. Sélectionnez un élément nouveau ou existant, puis déplacez-le avec Genre de la sélection. Affichez Tous les genres si un nouvel élément est masqué. Le mode de lecture est conservé.',
    'zh':'点击“＋新建类别”可创建类别。选择新建、导入或现有素材，然后在列表上方用“所选项目类别”移动。找不到新素材时请查看“所有类别”。移动类别会保留播放方式。'}
_DELETE_GENRE={
    'ja':'自作ジャンルを「カテゴリ」で選び、「ジャンルを削除…」を押すと削除できます。中の素材は自動分類に戻り、ファイルは残ります。',
    'en':'Select a custom genre in the filter and choose Delete genre. Its items return to automatic classification and their files are kept.',
    'es':'Seleccione un género propio en el filtro y pulse Eliminar género. Los elementos vuelven a la clasificación automática y sus archivos se conservan.',
    'fr':'Sélectionnez un genre personnalisé dans le filtre et choisissez Supprimer le genre. Les éléments sont reclassés automatiquement et leurs fichiers sont conservés.',
    'zh':'在类别筛选中选择自定义类别，然后点击“删除类别”。其中的素材会恢复自动分类，文件会保留。'}
for _language,(_title,_body) in LIBRARY_GUIDE.items():
    GUIDES[_language].append((_title,_body+'\n\n'+_CUSTOM_GENRES[_language]+'\n\n'+_DELETE_GENRE[_language]))

TOPICS=TOPICS+('hand_presets',)
_HAND_PRESETS={
    'ja':('左右の手ポーズ','ターゲットを選び、ライブラリの「カテゴリ」で「手・指」を表示します。左手・右手それぞれのグー、チョキ、パー、半開きをダブルクリックすると、選んだ側の指に適用します。動作編集中は現在のフレームにキーを設定します。'),
    'en':('Hand pose presets','Select a target and choose Hands / Fingers in the library. Double-click a left or right Fist, Scissors, Open or Half-open pose to apply it to that hand. In the motion editor this sets a key on the current frame.'),
    'es':('Poses de manos','Seleccione un objetivo y filtre por Manos / Dedos. Haga doble clic en una pose de la izquierda o derecha para aplicarla. En el editor se guarda una clave en el fotograma actual.'),
    'fr':('Poses de mains','Sélectionnez une cible et filtrez par Mains / Doigts. Double-cliquez sur une pose de main gauche ou droite pour l’appliquer. Dans l’éditeur, une clé est créée à l’image actuelle.'),
    'zh':('左右手预设','选择目标，在动作库中筛选“手／手指”。双击左手或右手预设即可应用。每只手都有握拳、剪刀手、张开和半张开四种姿势，另一只手和手腕保留当前姿势。编辑动作时会在当前帧设置关键帧。'),
}
for _language,_section in _HAND_PRESETS.items():
    GUIDES[_language].append(_section)

_REFRESH_NOTES={
'ja':'新規起動時の先頭はWalkです。保存プロジェクトはその内容を維持します。左右反転は根の位置・水平の向きを保ち、身体の傾きも左右へ反転します。書き出し操作は上部メニューへ統一し、FBX、MMDモデル選択・VMD、MP4の順です。書き出し設定も同メニューにあり、MP4の実解像度／30fpsを確認できます。MMDモデル選択時に対応検査の完了または非対応理由を表示します。形式・ボーンの検査であり、全動作の見た目の保証ではありません。ウィンドウサイズに合わせて各パネルが左右端・下端へ追従します。図は選択中の言語で撮影した実画面で、クリックすると拡大します。',
'en':'A new session starts with Walk; saved projects retain their contents. Mirroring preserves root position and horizontal facing while reflecting body tilt. Export controls are in the top menu: FBX, MMD target and VMD, then MP4. Export settings and actual MP4 resolution / 30 fps are shown there. MMD selection reports supported checks or a reason for rejection; this is not a guarantee of visual motion quality. Panels follow window edges when resized. Figures were captured in the selected language; click to enlarge.',
'es':'Una sesión nueva empieza con Walk; los proyectos guardados conservan su contenido. El espejo mantiene posición y rumbo horizontal y refleja la inclinación. El menú superior reúne FBX, modelo MMD y VMD, y MP4, con ajustes y resolución real / 30 fps. La selección MMD informa compatibilidad o motivo de rechazo; no garantiza calidad visual. Los paneles siguen los bordes al cambiar tamaño. Las figuras se capturaron en el idioma seleccionado; pulse para ampliar.',
'fr':'Une nouvelle session commence par Walk ; les projets conservent leur contenu. Le miroir conserve position et orientation horizontale et reflète l’inclinaison. Le menu supérieur regroupe FBX, modèle MMD et VMD, puis MP4, avec réglages et résolution réelle / 30 ips. Le contrôle MMD indique compatibilité ou raison du refus, sans garantir la qualité visuelle. Les panneaux suivent les bords lors du redimensionnement. Figures capturées dans la langue choisie ; cliquez pour agrandir.',
'zh':'新会话的首个目标为Walk，打开项目保留其保存内容。镜像保持根位置和水平朝向，并左右反转身体倾斜。导出操作统一在顶部：FBX、MMD目标模型和VMD、MP4，设置与实际MP4分辨率／30fps也在此显示。选择MMD时提示检查通过或不支持原因，但不保证动作视觉质量。调整窗口大小时面板随边缘移动。图片分别使用当前语言拍摄，点击可放大。'}
TOPICS=TOPICS+('interface_refresh_20261104',)
for _language,_body in _REFRESH_NOTES.items():
    _title,_workflow=GUIDES[_language][0]
    GUIDES[_language][0]=(_title,_body+'\n\n'+_workflow)
    GUIDES[_language].append((_title+' — 2026-11-04',_body))

from .studio_interval import GUIDES as INTERVAL_GUIDES
TOPICS=TOPICS+('interval_motion',)
for _language,_section in INTERVAL_GUIDES.items():GUIDES[_language].append(_section)
_INTERVAL_OFF={
'ja':('OFFは従来の連続4姿勢を条件にした生成です。','OFFでは「区間での動作」に従います。「ポーズ条件のみ」が従来の4姿勢の指定です。'),
'en':('OFF retains four-pose conditioning.','OFF follows Interval motion; Pose conditions only retains four-pose conditioning.'),
'es':('Desactivado conserva las cuatro poses de condición.','Desactivado sigue Movimiento del tramo; Solo condiciones de pose conserva las cuatro poses.'),
'fr':('Désactivé conserve les quatre poses de conditionnement.','Désactivé suit Mouvement du trajet ; Conditions de pose seules conserve les quatre poses.'),
'zh':('关闭时仍使用连续4姿势作为条件。','关闭时使用区间动作设置；仅姿势条件模式使用连续4姿势。')}
for _language,(_old,_new) in _INTERVAL_OFF.items():
    GUIDES[_language]=[(_title,_body.replace(_old,_new)) for _title,_body in GUIDES[_language]]


def draw_manual(app,ui):
    viewport=ui.get_main_viewport()
    ui.set_next_window_size(ui.ImVec2(min(840,viewport.size.x-40),min(760,viewport.size.y-60)),ui.Cond_.first_use_ever)
    ui.push_font(ui.get_font(),26.)
    visible,app.show_manual=ui.begin('User Guide###studio_user_guide',app.show_manual)
    try:
        if visible:
            ui.text_unformatted('MotionBricks Studio Ti')
            _,app.manual_search=ui.input_text('Guide search',app.manual_search)
            ui.separator()
            ui.begin_child('guide_content',ui.ImVec2(0,-40),child_flags=ui.ChildFlags_.borders)
            try:
                query=app.manual_search.strip().casefold();found=False
                for i,(title,body) in enumerate(GUIDES.get(app.language,GUIDES['en'])):
                    if query and query not in (title+' '+body+' '+TOPICS[i]).casefold():continue
                    found=True
                    if ui.collapsing_header(title+'###guide_section_'+str(i),flags=ui.TreeNodeFlags_.default_open):
                        ui.text_wrapped(body);ui.spacing()
                        from .studio_manual_images import draw_figure
                        draw_figure(app,ui,TOPICS[i])
                if not found:ui.text_wrapped('No matching sections.')
            finally:ui.end_child()
            if ui.button('Close'):app.show_manual=False
    finally:
        ui.end()
        ui.pop_font()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
