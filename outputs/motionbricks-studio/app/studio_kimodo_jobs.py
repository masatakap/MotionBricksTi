"""Explicit generation requests to the optional local Kimodo process."""
from pathlib import Path
import hashlib,json,math,re,time,uuid

ID=re.compile(r'^[0-9a-f]{32}$')


class JobClient:
    def __init__(self):
        self.prompt='An adult man walks straight forward at a natural pace.'
        self.duration=6.;self.steps=100;self.seed=42;self.postprocess=True;self.name='Motion'
        self.server=None;self.job=None;self.status=None;self.error=None;self.next_poll=0

    def poll(self,root):
        if time.monotonic()<self.next_poll:return
        self.next_poll=time.monotonic()+.5;self.server=None
        try:
            path=Path(root)/'user_data/studio-bridge.json'
            if path.stat().st_size<4000:
                data=json.loads(path.read_text(encoding='utf8'))
                if data.get('protocol')==1 and ID.fullmatch(str(data.get('instance',''))) and 0<=time.time()-data['updated']<15:self.server=data
        except (OSError,ValueError,KeyError,TypeError):pass
        if self.job:
            try:
                status=json.loads((self.job/'status.json').read_text(encoding='utf8'))
                if status.get('job_id')==self.job.name:self.status=status
            except (OSError,ValueError):pass

    @property
    def active(self):return self.job is not None and (not self.status or self.status.get('state') not in ('complete','failed','cancelled'))

    def submit(self,root):
        if self.active:raise ValueError('A Studio job is already active / Studioの生成処理が進行中です。')
        self.next_poll=0;self.poll(root)
        if not self.server:raise ValueError('Open the updated Kimodo launcher and start its 3D screen / 更新版のKimodo起動アプリから3D画面を起動してください。')
        if not self.prompt.strip() or len(self.prompt)>4000:raise ValueError('Enter a prompt of 1–4000 characters / プロンプトを入力してください。')
        if not math.isfinite(self.duration) or not 1<=self.duration<=30:raise ValueError('Duration: 1–30 seconds / 尺は1〜30秒です。')
        if not 1<=self.steps<=150 or not 0<=self.seed<2**31:raise ValueError('Steps: 1–150; seed: 0–2147483647')
        job=Path(root).resolve()/'user_data/studio-jobs'/uuid.uuid4().hex;job.mkdir(parents=True)
        data=dict(job_id=job.name,instance=self.server['instance'],prompt=self.prompt.strip(),duration=self.duration,steps=self.steps,seed=self.seed,postprocess=self.postprocess)
        temporary=job/'request.tmp';temporary.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8');temporary.replace(job/'request.json')
        self.job=job;self.status=None;self.error=None

    def cancel(self):
        if self.active:(self.job/'cancel.json').write_text('{}',encoding='utf8')

    def result(self):
        if not self.job or not self.status or self.status.get('state')!='complete':raise ValueError('Generation has not completed')
        path=self.job/'result.npz'
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=self.status.get('sha256'):raise ValueError('Generation result hash does not match / 生成結果のハッシュが一致しません。')
        return path


LABELS={
'title':('Generate from Studio','Studioから生成','Generar desde Studio','Générer depuis Studio','从Studio生成'),
'prompt':('Motion prompt (English recommended)','動作のプロンプト（英語推奨）','Descripción (inglés recomendado)','Description (anglais conseillé)','动作描述（建议英语）'),
'duration':('Duration (seconds)','尺（秒）','Duración (segundos)','Durée (secondes)','时长（秒）'),
'steps':('Diffusion steps','生成ステップ数','Pasos de difusión','Étapes de diffusion','扩散步数'),
'seed':('Seed','シード','Semilla','Graine','随机种子'),
'postprocess':('Kimodo foot postprocessing','Kimodoの足滑り補正','Corrección de pies Kimodo','Correction des pieds Kimodo','Kimodo脚滑修正'),
'ready':('Kimodo job connection ready','Kimodoの生成連携：接続中','Conexión lista','Connexion prête','Kimodo生成连接就绪'),
'offline':('Start the updated Kimodo 3D screen first. An already-open older process needs a restart after saving its work.','更新版Kimodoの3D画面を起動してください。旧版の起動中プロセスは、作業を保存して再起動すると接続できます。','Inicie la vista 3D actualizada de Kimodo. Guarde y reinicie un proceso antiguo.','Démarrez la vue 3D Kimodo mise à jour. Enregistrez puis redémarrez un ancien processus.','请先启动更新版Kimodo的3D界面；旧进程需保存工作后重启。'),
'generate':('Generate new motion','新しいモーションを生成','Generar movimiento nuevo','Générer un mouvement','生成新动作'),
'cancel':('Cancel generation','生成をキャンセル','Cancelar generación','Annuler la génération','取消生成'),
'import':('Import this result...','この生成結果を取り込む...','Importar este resultado...','Importer ce résultat...','导入此结果...'),
'name':('Library name','ライブラリの保存名','Nombre en la biblioteca','Nom dans la bibliothèque','动作库名称'),
'note':('This request generates one independent motion without browser constraints. It shares the model and waits for other generation. Cancellation is checked between diffusion steps; text encoding may finish first. Results are imported only when you press Import.','ブラウザーの制約を使わず、独立した動作を1件生成します。同じモデルを共有し、他の生成中は待機します。キャンセルは拡散ステップ間で反映し、文章解析中は完了まで待つ場合があります。取り込みボタンを押すまで編集内容へ反映しません。','Genera un movimiento independiente sin restricciones del navegador. Comparte el modelo y espera otras tareas. La cancelación se comprueba entre pasos; la codificación puede terminar primero. Importe explícitamente el resultado.','Génère un mouvement indépendant sans les contraintes du navigateur. Partage le modèle et attend les autres tâches. Annulation entre étapes ; l’encodage peut devoir finir. Importez explicitement le résultat.','生成一个独立动作，不使用浏览器约束。共享模型并等待其他生成任务。取消在扩散步之间检查，文本编码可能需先完成。只有点击导入后才应用。'),
'waiting':('Waiting','待機中','En espera','En attente','等待中'),
'generating':('Generating','生成中','Generando','Génération','生成中'),
'complete':('Complete','生成完了','Completado','Terminé','已完成'),
'failed':('Failed: check Kimodo authorization, memory and connection, then retry.','生成失敗：Kimodo側の認証・メモリ・接続を確認して再試行してください。','Error: revise autorización, memoria y conexión.','Échec : vérifiez autorisation, mémoire et connexion.','失败：请检查Kimodo认证、内存及连接后重试。'),
'cancelled':('Cancelled','キャンセル済み','Cancelado','Annulé','已取消'),
'lost':('Kimodo connection lost. Restart it and release this job before retrying.','Kimodoの接続が切れました。再起動後、このジョブを終了して再試行してください。','Conexión perdida. Reinicie y libere la tarea.','Connexion perdue. Redémarrez et libérez cette tâche.','Kimodo连接中断，请重启并结束此任务后重试。'),
'release':('Release disconnected job','切断されたジョブを終了','Liberar tarea desconectada','Libérer la tâche déconnectée','结束断线任务')}


def text(key,language):return LABELS[key][('en','ja','es','fr','zh').index(language if language in ('en','ja','es','fr','zh') else 'en')]


def draw_jobs(app,ui):
    link=app.kimodo_link;client=link.jobs;client.poll(link.root);lang=app.language
    ui.separator();ui.text(text('title',lang));ui.text_wrapped(text('ready' if client.server else 'offline',lang))
    ui.begin_disabled(client.active)
    ui.text_wrapped(text('prompt',lang));_,client.prompt=ui.input_text_multiline('###kimodo_job_prompt',client.prompt,ui.ImVec2(-1,85))
    _,client.duration=ui.input_float(text('duration',lang),client.duration)
    _,client.steps=ui.input_int(text('steps',lang),client.steps)
    _,client.seed=ui.input_int(text('seed',lang),client.seed)
    _,client.postprocess=ui.checkbox(text('postprocess',lang),client.postprocess)
    ui.end_disabled()
    ui.begin_disabled(client.active or not client.server)
    if ui.button(text('generate',lang)):
        try:client.submit(link.root)
        except Exception as exc:client.error=str(exc)
    ui.end_disabled()
    if client.active:
        ui.same_line()
        if ui.button(text('cancel',lang)):client.cancel()
        if not client.server:
            ui.text_wrapped(text('lost',lang))
            if ui.button(text('release',lang)):client.cancel();client.status={'state':'cancelled'}
    if client.status:
        state=client.status.get('state','waiting');ui.text_wrapped(text(state if state in LABELS else 'waiting',lang))
        if state=='generating' and client.status.get('phase')=='diffusion':ui.progress_bar(client.status.get('completed_steps',0)/max(1,client.status.get('steps',1)))
        if state=='complete':
            _,client.name=ui.input_text(text('name',lang),client.name)
            ui.begin_disabled(app.busy)
            if ui.button(text('import',lang)):
                try:app.use_library_file(str(client.result()),name=client.name.strip() or None)
                except Exception as exc:client.error=str(exc)
            ui.end_disabled()
    if client.error:ui.text_wrapped(client.error)
    ui.text_wrapped(text('note',lang))

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
