"""Optional local Kimodo connection. No bundled runtime, models or credentials."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import os
import subprocess

DEFAULT_ROOT=Path(__file__).resolve().parents[2]/'kimodo-studio'
FLAGS=getattr(subprocess,'CREATE_NO_WINDOW',0)
REQUIRED=('launcher.py','app_core.py','run_generator.py','source/kimodo/__init__.py')
PROBE=r'''
import importlib.util,json
required=('torch','kimodo','viser','huggingface_hub')
missing=[name for name in required if importlib.util.find_spec(name) is None]
result=dict(missing=missing,python=__import__('platform').python_version(),cuda=False,gpus=[])
if 'torch' not in missing:
    import torch
    result.update(torch=torch.__version__,cuda=torch.cuda.is_available())
    if result['cuda']:
        result['gpus']=[dict(name=torch.cuda.get_device_name(i),memory_gib=round(torch.cuda.get_device_properties(i).total_memory/1024**3,1)) for i in range(torch.cuda.device_count())]
print('STUDIO_KIMODO_CHECK='+json.dumps(result))
'''


def validate_root(root):
    root=Path(root).expanduser().resolve()
    if not all((root/name).is_file() for name in REQUIRED):
        raise ValueError('Kimodo Motion Lab Ti folder required / Kimodo Motion Lab Tiのフォルダーを選択してください。')
    python=root/'.venv/Scripts/python.exe'
    if not python.is_file():
        raise ValueError('Kimodo Python environment is missing / KimodoのPython環境がありません。')
    return root,python


def diagnose(root):
    root,python=validate_root(root)
    try:
        process=subprocess.run([str(python),'-c',PROBE],cwd=str(root),capture_output=True,text=True,encoding='utf8',errors='replace',timeout=30,creationflags=FLAGS)
    except subprocess.TimeoutExpired:
        raise ValueError('Environment check timed out. Kimodo was not stopped / 環境診断が時間切れになりました。Kimodoは停止していません。') from None
    lines=[line.partition('=')[2] for line in process.stdout.splitlines() if line.startswith('STUDIO_KIMODO_CHECK=')]
    if process.returncode or not lines:
        # Third-party startup output may contain environment secrets; never show it.
        raise ValueError('Cannot load the Kimodo Python environment / KimodoのPython環境を読み込めません。Kimodo起動アプリでログを確認してください。')
    result=json.loads(lines[-1]);result['ready']=not result['missing']
    return result


class KimodoLink:
    def __init__(self,user_directory):
        self.config=Path(user_directory)/'kimodo-connection.json'
        try:
            data=json.loads(self.config.read_text(encoding='utf8'))
            self.root=Path(data['root'])
        except (OSError,ValueError,TypeError,KeyError):self.root=DEFAULT_ROOT
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='kimodo-check')
        self.future=None;self.report=None;self.error=None;self.open=False

    def choose_root(self,root):
        root,_=validate_root(root)
        self.config.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.config.with_suffix('.tmp')
        temporary.write_text(json.dumps({'root':str(root)},ensure_ascii=False),encoding='utf8')
        temporary.replace(self.config)
        self.root=root;self.report=None;self.error=None

    def check(self):
        if self.future is None:
            self.error=None;self.report=None;self.future=self.pool.submit(diagnose,self.root)

    def poll(self):
        if self.future is not None and self.future.done():
            try:self.report=self.future.result()
            except Exception as exc:self.error=str(exc)
            self.future=None

    def launch(self):
        root,python=validate_root(self.root)
        if not self.report or not self.report['ready']:
            raise ValueError('Check the environment first / 先に環境診断を実行してください。')
        pythonw=python.with_name('pythonw.exe')
        # The launcher has its own single-instance mutex; it raises an existing window.
        return subprocess.Popen([str(pythonw if pythonw.is_file() else python),str(root/'launcher.py')],cwd=str(root),creationflags=FLAGS)

    @property
    def results(self):return self.root/'user_data/results'


LABELS={
'title':('Kimodo connection','Kimodo連携','Conexión con Kimodo','Connexion Kimodo','Kimodo联动'),
'about':('Optional: connect an existing Kimodo Motion Lab Ti installation. Studio works without Kimodo.','任意機能：導入済みのKimodo Motion Lab Tiと接続します。KimodoなしでもStudioは使えます。','Opcional: conecte una instalación de Kimodo Motion Lab Ti. Studio funciona sin Kimodo.','Facultatif : connectez une installation de Kimodo Motion Lab Ti. Studio fonctionne sans Kimodo.','可选功能：连接已安装的Kimodo Motion Lab Ti。Studio无需Kimodo也可使用。'),
'folder':('Choose Kimodo folder...','Kimodoのフォルダーを選択...','Elegir carpeta de Kimodo...','Choisir le dossier Kimodo...','选择Kimodo文件夹...'),
'check':('Check environment','環境を診断','Comprobar entorno','Vérifier l’environnement','检查环境'),
'checking':('Checking environment...','環境を診断しています...','Comprobando entorno...','Vérification en cours...','正在检查环境...'),
'start':('Open Kimodo launcher','Kimodo起動アプリを開く','Abrir iniciador de Kimodo','Ouvrir le lanceur Kimodo','打开Kimodo启动器'),
'import':('Import generated NPZ...','生成したNPZを取り込む...','Importar NPZ generado...','Importer un NPZ généré...','导入生成的NPZ...'),
'results':('Open results folder','生成結果フォルダーを開く','Abrir carpeta de resultados','Ouvrir le dossier des résultats','打开结果文件夹'),
'cpu':('CPU available; generation is slow. NVIDIA CUDA is not available in this environment.','CPUで利用できます（生成は低速）。この環境ではNVIDIA CUDAを利用できません。','CPU disponible; la generación es lenta. NVIDIA CUDA no está disponible.','CPU disponible ; génération lente. NVIDIA CUDA indisponible.','可使用CPU（生成较慢）。当前环境无法使用NVIDIA CUDA。'),
'workflow':('Generate and save as NPZ in Kimodo, then import here. Keep its launcher open while generating. Imports use the existing SOMA77 converter and preserve every frame; review quality before adoption.','Kimodoで生成してNPZ保存した後、ここから取り込みます。生成中はKimodo起動アプリを閉じないでください。既存のSOMA77変換で全フレームを保持します。採用前に動作を確認してください。','Genere y guarde NPZ en Kimodo e impórtelo aquí. Mantenga abierto el iniciador durante la generación. La conversión SOMA77 conserva todos los fotogramas; revise la calidad.','Générez et enregistrez un NPZ dans Kimodo, puis importez-le ici. Gardez le lanceur ouvert pendant la génération. La conversion SOMA77 conserve toutes les images ; vérifiez la qualité.','在Kimodo生成并保存NPZ后从此处导入。生成期间请勿关闭启动器。沿用SOMA77转换并保留所有帧，采用前请检查动作质量。'),
'conditions':('Models, dependencies and Hugging Face authorization are managed in Kimodo. This check does not download models or validate model access.','モデル・依存環境・Hugging Face認証はKimodo側で管理します。この診断ではモデルを取得せず、利用承認も確認しません。','Kimodo gestiona modelos, dependencias y autorización de Hugging Face. Esta comprobación no descarga modelos ni verifica el acceso.','Kimodo gère modèles, dépendances et autorisation Hugging Face. Ce contrôle ne télécharge rien et ne valide pas l’accès aux modèles.','模型、依赖环境及Hugging Face认证由Kimodo管理。此检查不下载模型，也不验证模型访问权限。'),
'close':('Close','閉じる','Cerrar','Fermer','关闭')}


from .studio_kimodo_help import LABELS as CONNECTION_HELP
LABELS.update(CONNECTION_HELP)

def label(key,language):return LABELS[key][('en','ja','es','fr','zh').index(language if language in ('en','ja','es','fr','zh') else 'en')]


def draw_connection(app,ui):
    link=app.kimodo_link;link.poll()
    if not link.open:return
    lang=app.language
    ui.set_next_window_size(ui.ImVec2(820,850),ui.Cond_.first_use_ever)
    visible,link.open=ui.begin(label('title',lang)+'###kimodo_connection',link.open)
    position=ui.get_window_pos();size=ui.get_window_size();link.ui_bounds=(position.x,position.y,size.x,size.y)
    try:
        if not visible:return
        ui.text_wrapped(label('about',lang));ui.separator();ui.text_wrapped(label('folder_hint',lang));ui.text_wrapped(str(link.root))
        installed=all((link.root/name).is_file() for name in REQUIRED) and (link.root/'.venv/Scripts/python.exe').is_file()
        ui.text_wrapped(label('installed' if installed else 'not_installed',lang))
        if not installed:ui.text_wrapped(label('setup_order',lang))
        waiting=link.future is not None
        ui.begin_disabled(waiting)
        if ui.button(label('folder',lang)):app.pending='kimodo_folder'
        if DEFAULT_ROOT!=link.root and all((DEFAULT_ROOT/name).is_file() for name in REQUIRED):
            ui.same_line()
            if ui.button(label('default',lang)):
                try:link.choose_root(DEFAULT_ROOT);link.check()
                except Exception as exc:link.error=str(exc)
        ui.same_line()
        if ui.button(label('check',lang)):link.check()
        ui.end_disabled()
        if waiting:ui.text_wrapped(label('checking',lang))
        if link.error:ui.text_wrapped(link.error)
        if link.report:
            report=link.report
            ui.text_wrapped('Python '+report['python']+' | PyTorch '+report.get('torch','—'))
            if report['missing']:ui.text_wrapped('Missing / 不足: '+', '.join(report['missing']))
            elif not report['cuda']:ui.text_wrapped(label('cpu',lang))
            for gpu in report['gpus']:ui.text_wrapped(gpu['name']+' | '+str(gpu['memory_gib'])+' GiB')
        ui.begin_disabled(waiting or not link.report or not link.report['ready'])
        if ui.button(label('start',lang)):
            try:link.launch()
            except Exception as exc:link.error=str(exc)
        ui.end_disabled();ui.separator();ui.text_wrapped(label('workflow',lang))
        ui.begin_disabled(not link.results.is_dir())
        if ui.button(label('results',lang)):
            try:os.startfile(str(link.results.resolve()))
            except OSError as exc:link.error=str(exc)
        ui.end_disabled();ui.text_wrapped(label('conditions',lang))
        if ui.button(label('close',lang)):link.open=False
    finally:ui.end()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
