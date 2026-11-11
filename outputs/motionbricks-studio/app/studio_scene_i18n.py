"""Environment UI labels; preset identifiers stay stable in saved projects."""
_labels={
'Move selected object':['選択した物体をマウスで移動','Mover el objeto seleccionado','Déplacer l’objet sélectionné','用鼠标移动所选物体'],
'Click a box in the viewport, then drag its X/Y/Z arrows. Select a character or target row to edit poses again.':['画面内のボックスをクリックし、XYZの矢印をドラッグして移動します。ポーズ編集に戻るにはキャラクターかターゲットの行を選択してください。','Haga clic en una caja y arrastre las flechas X/Y/Z. Seleccione un personaje o una fila de objetivo para editar poses.','Cliquez sur une boîte puis faites glisser les flèches X/Y/Z. Sélectionnez un personnage ou une cible pour modifier les poses.','点击视图中的方块后拖动XYZ箭头即可移动。选择角色或目标列表中的一行可返回姿势编辑。'],
'Object center (m)':['中心位置（m）','Centro del objeto (m)','Centre de l’objet (m)','物体中心（米）'],
'Place on ground':['地面に配置','Colocar en el suelo','Poser au sol','放置到地面'],
'Position Z is the object center. A 0.75 m box on the ground has Z = 0.375 m.':['位置Zは物体の中心です。高さ0.75mの箱を地面に置く場合、Zは0.375mです。','Z es el centro. Una caja de 0,75 m en el suelo usa Z = 0,375 m.','Z désigne le centre. Une boîte de 0,75 m posée au sol utilise Z = 0,375 m.','位置Z表示物体中心。0.75米高的箱子放在地面时，Z为0.375米。'],
'Adjusts the box in Studio only. UE actors are not moved.':['Studio上のボックスのみ調整します。UEのActorは移動しません。','Solo modifica la caja en Studio; no mueve actores UE.','Ajuste uniquement la boîte dans Studio ; les acteurs UE ne bougent pas.','仅调整Studio中的方块，不会移动UE Actor。'],
'Environment':['環境','Entorno','Environnement','环境'],
'Environment & Interactions':['環境・オブジェクトとの動作','Entorno e interacciones','Environnement et interactions','环境与交互'],
'Import UE objects':['UEの選択オブジェクトを取得','Importar objetos de UE','Importer les objets UE','获取UE所选对象'],
'Object name':['オブジェクト名','Nombre del objeto','Nom de l’objet','对象名称'],
'Enabled':['有効','Activado','Actif','启用'],
'Position (m)':['位置（m）','Posición (m)','Position (m)','位置（米）'],
'Size (m)':['幅・奥行き・高さ（m）','Dimensiones (m)','Dimensions (m)','尺寸（米）'],
'Object yaw':['向き（度）','Orientación','Orientation','朝向（度）'],
'Interaction':['動作の選択','Interacción','Interaction','交互动作'],
'Sample variation':['動作のバリエーション番号','Variante','Variante','动作变体编号'],
'Seated hold (s)':['座った状態を保持（秒）','Espera sentado (s)','Maintien assis (s)','坐姿保持（秒）'],
'Remove object':['オブジェクトを削除','Eliminar objeto','Supprimer l’objet','删除对象'],
'Load custom interaction preset...':['自作の動作設定を読み込む...','Cargar interacción propia...','Charger une interaction...','载入自定义交互...'],
'Clear custom preset':['自作の動作指定を解除','Quitar ajuste propio','Retirer le réglage personnalisé','清除自定义设置'],
'Route motion':['移動方法','Locomoción','Déplacement','移动方式'],
'Clearance radius (m)':['キャラクターの回避半径（m）','Radio de seguridad (m)','Rayon de dégagement (m)','避让半径（米）'],
'Build environment route':['障害物に合わせてターゲットを配置','Preparar ruta','Préparer le parcours','按障碍物布置目标'],
'Generate environment motion':['環境を使ってモーションを生成','Generar movimiento','Générer le mouvement','按环境生成动作'],
'Add jump_0_5m':['0.5mの障害物を追加','Añadir obstáculo de 0,5 m','Obstacle de 0,5 m','添加0.5米障碍物'],
'Add jump_0_75m':['0.75mの障害物を追加','Añadir obstáculo de 0,75 m','Obstacle de 0,75 m','添加0.75米障碍物'],
'Add avoidance':['くぐる障害物を追加','Añadir paso bajo','Ajouter un passage bas','添加低矮通道'],
'Add sit':['座面を追加','Añadir asiento','Ajouter une assise','添加座位'],
'Add avoid':['迂回するボックスを追加','Añadir caja para rodear','Ajouter une boîte à contourner','添加绕行方块'],
'Walk':['歩行','Caminar','Marcher','步行'],
'Run':['走行','Correr','Courir','跑步'],
'auto':['自動','Automático','Automatique','自动'],
'avoid':['迂回','Rodear','Contourner','绕行'],
'jump_0_5m':['乗り越え（0.5m）','Salto de 0,5 m','Franchir 0,5 m','越过0.5米'],
'jump_0_75m':['乗り越え（0.75m）','Salto de 0,75 m','Franchir 0,75 m','越过0.75米'],
'avoidance':['身をかがめてくぐる','Agacharse','Passer baissé','弯腰通过'],
'sit':['座る・立ち上がる','Sentarse y levantarse','S’asseoir et se lever','坐下与起立'],
'Objects use bounding boxes. Auto selects supported samples or plans a detour. Inspect generated motion for contact.':[
'物体は境界ボックスの概形で扱います。自動では対応サンプルを選び、対応範囲外は迂回します。生成後は実モデルの接触を確認してください。',
'Se usan cajas aproximadas. Auto elige muestras compatibles o una ruta alternativa. Revise los contactos.',
'Les objets utilisent des boîtes approximatives. Auto choisit un exemple adapté ou un détour. Vérifiez les contacts.',
'对象使用包围盒近似。自动模式选择适用动作或绕行路线。生成后请检查模型接触。'],
'Move Start and Destination far enough apart for approach and landing. Chair direction uses Object yaw. Custom presets can replace bundled samples before release.':[
'開始と到達先は助走・着地ができる距離に配置します。椅子の向きは「向き」で指定します。公開前に自作の動作設定へ差し替えられます。',
'Deje espacio para aproximarse y aterrizar. La orientación define la silla. Sustituya las muestras antes de publicar.',
'Prévoyez l’approche et la réception. L’orientation définit la chaise. Remplacez les exemples avant publication.',
'请为助跑和落地留出空间。座椅使用对象朝向。发布前可替换为自制动作。'],
}
_labels['Default interactions use independently authored adult motions. Keep approach and landing space. Chair yaw 0 faces -Y. Jump variation 0 uses one hand; 1 uses no hands. Custom presets retain their own source terms.']=[
'標準の環境動作は独立制作した成人向けモーションを使用します。進入・着地の余裕を確保してください。椅子の向き0度は−Y方向です。0.75m越えは番号0が片手、1が手なしです。外部の自作設定にはその素材の条件が適用されます。',
'Las interacciones estándar usan movimientos adultos creados independientemente. Reserve espacio. La silla a 0° mira hacia −Y. Para 0,75 m, variante 0 usa una mano y 1 ninguna. Los recursos externos conservan sus condiciones.',
'Les interactions standard utilisent des mouvements adultes créés indépendamment. Prévoyez de la place. À 0°, la chaise regarde vers −Y. Pour 0,75 m : variante 0 à une main, 1 sans main. Les ressources externes gardent leurs conditions.',
'标准环境动作使用独立制作的成人动作。请预留进出空间。椅子0度面向−Y。0.75米越障变体0使用单手，1不使用手。外部资源仍适用其自身条款。']
_labels['Environment actions use the replacement Kimodo clips. Object-fit checks run in the background. Auto detours when a clip cannot fit. Seat candidates use 0.4 m seats; inspect contacts and transitions. Jump variant 0 prefers a hand, with a no-hand fallback; variant 1 uses no hands.']=[
'環境動作は差し替えたKimodo動作を使い、物体への適合をバックグラウンドで確認します。合わない場合、Autoは迂回します。着座候補は座面高0.4m用です。接触とつなぎ目を確認してください。跳躍の番号0は片手を優先し、合わなければ手なしを使います。番号1は手なしです。',
'Las acciones usan los clips Kimodo de reemplazo. La comprobación se ejecuta en segundo plano; Auto rodea el objeto si no encaja. Asientos de 0,4 m: revise contacto y transiciones. Variante 0 prefiere una mano y recurre a sin manos; variante 1 usa sin manos.',
'Les actions utilisent les clips Kimodo de remplacement. Le contrôle se fait en arrière-plan ; Auto contourne si nécessaire. Sièges de 0,4 m : vérifiez contacts et raccords. Variante 0 privilégie une main, sinon sans main ; variante 1 sans main.',
'环境动作使用替换后的Kimodo片段，在后台检查与物体是否匹配。不匹配时Auto会绕行。坐下候选适用于0.4米座面，请检查接触与衔接。跳跃变体0优先单手，不合适时使用无手版本；变体1使用无手版本。']
TRANSLATIONS={code:{key:values[i] for key,values in _labels.items()} for i,code in enumerate(('ja','es','fr','zh'))}

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
