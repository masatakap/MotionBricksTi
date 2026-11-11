"""Pose bridge labels in all supported Studio languages."""
ROWS=[
('Connect UE / Start synchronization','UEに接続・同期を開始','Conectar UE / Iniciar sincronización','Connecter UE / Démarrer la synchronisation','连接UE / 开始同步'),
('Disconnect UE','UEとの同期を終了','Desconectar UE','Déconnecter UE','断开UE连接'),
('Import UE target points','UEの目標位置を取り込む','Importar puntos objetivo de UE','Importer les points cibles UE','导入UE目标点'),
('Save completed motion to UE','完成モーションをUEへ保存','Guardar movimiento final en UE','Enregistrer le mouvement final dans UE','将完成的动作保存到UE'),
('Unreal Engine','Unreal Engine','Unreal Engine','Unreal Engine','Unreal Engine'),
('Install UE IK Bridge...','UE IK連携を導入...','Instalar puente IK de UE...','Installer le pont IK UE...','安装UE IK桥接...'),
('Unreal Engine project','Unreal Engineプロジェクト','Proyecto de Unreal Engine','Projet Unreal Engine','Unreal Engine项目'),
('Set up UE project connection...','UEプロジェクトの接続設定...','Configurar la conexión con un proyecto de UE...','Configurer la connexion au projet UE...','设置 UE 项目连接...'),
('UE project configured. Start synchronization in Studio, then connect the character in UE.','UEプロジェクトを設定しました。Studioで同期を開始し、UEでキャラクターを接続してください。','Proyecto de UE configurado. Inicia la sincronización en Studio y conecta el personaje en UE.','Projet UE configuré. Démarrez la synchronisation dans Studio, puis connectez le personnage dans UE.','UE 项目已配置。请在 Studio 中开始同步，然后在 UE 中连接角色。'),
('Send selected pose to UE','選択ポーズをUEへ送る','Enviar pose seleccionada a UE','Envoyer la pose sélectionnée à UE','将所选姿势发送到UE'),
('Import UE pose as new target','UEのポーズを新規ターゲットに追加','Importar pose de UE como nuevo objetivo','Importer la pose UE comme nouvelle cible','将UE姿势导入为新目标'),
('Update sent target with UE pose','UEのポーズで送信元を更新','Actualizar objetivo enviado con pose de UE','Actualiser la cible envoyée avec la pose UE','用UE姿势更新源目标'),
('Sent pose to UE. Use MotionBricks > Create IK Pose Editor in UE.','UEへ送りました。UEのMotionBricksメニューから「IKポーズ編集を開始」を選んでください。','Pose enviada. En UE, use MotionBricks > Create IK Pose Editor.','Pose envoyée. Dans UE, utilisez MotionBricks > Create IK Pose Editor.','姿势已发送。在UE中选择MotionBricks > Create IK Pose Editor。'),
('Imported UE IK pose as a new target.','UEで編集したIKポーズを新規ターゲットに追加しました。','Pose IK de UE importada como nuevo objetivo.','Pose IK UE importée comme nouvelle cible.','已将UE IK姿势导入为新目标。'),
]
TRANSLATIONS={code:{row[0]:row[i] for row in ROWS} for i,code in enumerate(('en','ja','es','fr','zh'))}

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
