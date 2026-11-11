"""Motion authoring labels, ordered English / Japanese / Spanish / French / Chinese."""
ROWS=[
('The clip itself plays without AI or IK corrections. AI is used only to generate the connections before and after it.','クリップ本体はAI・IK補正なしで再生します。AIは前後をつなぐ動きの生成に使います。','El clip se reproduce sin correcciones de IA ni IK. La IA solo genera las conexiones anteriores y posteriores.','Le clip est lu sans correction IA ni IK. L’IA génère uniquement les raccords avant et après.','片段本体播放时不进行AI或IK修正。AI仅用于生成前后的衔接动作。'),
('Every frame is kept. The conditioning time does not trim the motion in this mode.','全フレームを保持します。このモードでは、生成に使う時刻を選んでも動作全体は省略しません。','Se conservan todos los fotogramas. El instante de condición no recorta el movimiento en este modo.','Toutes les images sont conservées. L’instant de conditionnement ne coupe pas le mouvement dans ce mode.','保留所有帧。此模式下，选择生成条件时刻不会裁剪完整动作。'),
('Always Play Entire Motion: ON','最初から最後まで必ず流す：ON','Reproducir movimiento completo: SÍ','Lire tout le mouvement : OUI','从头到尾完整播放：开'),
('Always Play Entire Motion: OFF','最初から最後まで必ず流す：OFF','Reproducir movimiento completo: NO','Lire tout le mouvement : NON','从头到尾完整播放：关'),
('ON: reach the first pose, play every frame, then transition from the final pose.','ON：最初の姿勢まで移動し、全フレームを再生して、最後の姿勢から次の動作へつなぎます。','SÍ: llegar a la primera pose, reproducir todos los fotogramas y pasar al siguiente movimiento desde la pose final.','OUI : rejoindre la première pose, lire toutes les images, puis enchaîner depuis la pose finale.','开启：到达初始姿势后播放所有帧，再从最终姿势衔接下一动作。'),
('OFF: use the selected four poses as generation conditions.','OFF：選択時刻の連続4姿勢を生成条件として使います。','NO: usar las cuatro poses seleccionadas como condiciones de generación.','NON : utiliser les quatre poses choisies comme conditions de génération.','关闭：使用选定时刻的连续4姿势作为生成条件。'),
('The selected four poses contain movement.','選択した連続4姿勢には動きの情報があります。','Las cuatro poses seleccionadas contienen movimiento.','Les quatre poses choisies contiennent du mouvement.','所选连续4姿势包含运动信息。'),
('The selected four poses are static. Choose a time with movement to carry motion information.','選択した4姿勢は静止しています。動きの情報を含めるには、動いている時刻を選んでください。','Las cuatro poses son estáticas. Elija un instante con movimiento para incluir esa información.','Les quatre poses sont statiques. Choisissez un instant en mouvement pour transmettre cette information.','所选4姿势为静止姿势。请选择有运动的时刻以包含运动信息。'),
('Motion name','動作名','Nombre del movimiento','Nom du mouvement','动作名称'),
('Conditioning frame','生成に使う時刻','Instante de condición','Instant de conditionnement','生成条件时刻'),
('Motion Authoring','動作の作成・編集','Creación de movimientos','Création de mouvements','动作制作与编辑'),
('New Motion (Rest Pose)','新規動作（基準姿勢から）','Nuevo movimiento (pose de referencia)','Nouveau mouvement (pose de référence)','新建动作（基准姿势）'),
('Motion from Current Pose','現在のポーズから動作を作成','Movimiento desde la pose actual','Mouvement depuis la pose actuelle','从当前姿势创建动作'),
('Edit Motion','動作を編集','Editar movimiento','Modifier le mouvement','编辑动作'),
('Editing frame','編集するフレーム','Fotograma de edición','Image à modifier','编辑帧'),
('Preview Motion','動作を再生','Reproducir movimiento','Lire le mouvement','播放动作'),
('Pause Motion','動作を一時停止','Pausar movimiento','Mettre en pause','暂停动作'),
('Motion Start','動作の先頭へ','Inicio del movimiento','Début du mouvement','回到动作开头'),
('Motion length (s)','動作の尺（秒）','Duración del movimiento (s)','Durée du mouvement (s)','动作时长（秒）'),
('Add Key','キーを追加','Añadir clave','Ajouter une clé','添加关键帧'),
('Delete Key','キーを削除','Eliminar clave','Supprimer la clé','删除关键帧'),
('Motion root position','動作内のルート位置','Posición raíz del movimiento','Position racine du mouvement','动作根骨位置'),
('Use This Time (4 Poses)','この時刻の連続4姿勢を使う','Usar este instante (4 poses)','Utiliser cet instant (4 poses)','使用此时刻（连续4姿势）'),
('Save Motion As...','動作を名前を付けて保存...','Guardar movimiento como...','Enregistrer le mouvement sous...','动作另存为...'),
('Studio motion','Studio動作','Movimiento de Studio','Mouvement Studio','Studio动作'),
('Edit bones at each time. Edits automatically add a key. Other keys are preserved.','時刻を選んでボーンを編集するとキーが追加されます。ほかの時刻のキーは保持します。','Edite huesos en cada instante. Se añade una clave automáticamente y se conservan las demás.','Modifiez les os à chaque instant. Une clé est ajoutée automatiquement ; les autres sont conservées.','选择时刻编辑骨骼会自动添加关键帧，并保留其他时刻的关键帧。'),
('Created from the skeleton reference pose; no motion clip was copied.','骨格の基準姿勢から作成しています。モーションクリップはコピーしていません。','Creado desde la pose de referencia, sin copiar clips de movimiento.','Créé depuis la pose de référence, sans copier de clip de mouvement.','从骨架基准姿势创建，未复制动作片段。'),
('Created from the current pose. Its source terms still apply.','現在のポーズから作成しています。元の素材の利用条件は引き継ぎます。','Creado desde la pose actual. Se mantienen las condiciones del recurso original.','Créé depuis la pose actuelle. Les conditions de la source restent applicables.','从当前姿势创建，原始素材的使用条款仍适用。'),
]
TRANSLATIONS={code:{row[0]:row[i] for row in ROWS} for i,code in enumerate(('en','ja','es','fr','zh'))}

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
