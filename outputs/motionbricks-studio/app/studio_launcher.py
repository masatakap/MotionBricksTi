"""Desktop entry point: keep the console out of the way and retain a local error log."""
import os
from pathlib import Path
import sys
import traceback


def scene_worker_init():
    """Configure pythonw output before unpickling native-library work items.

    Keep this initializer in a stdlib-only module. Importing studio_scene_plan
    to resolve the initializer itself is too early: pythonw has no stdout.
    """
    import faulthandler
    folder=Path(__file__).resolve().parents[1]/'user_data';folder.mkdir(exist_ok=True)
    log=(folder/'scene-worker.log').open('a',encoding='utf8',buffering=1)
    sys.stdout=sys.stderr=log
    faulthandler.enable(file=log,all_threads=True)
    print(f'Scene worker started: pid={os.getpid()}',flush=True)


def show_startup_error(message):
    import ctypes

    if sys.__stderr__ is not None:
        print(message, file=sys.__stderr__)
    ctypes.windll.user32.MessageBoxW(None, message, 'MotionBricks Studio Ti', 0x10)


def main():
    root = Path(__file__).resolve().parents[1]
    log_path = root / 'user_data' / 'studio.log'
    try:
        os.chdir(root)
        log_path.parent.mkdir(exist_ok=True)
        log = log_path.open('a', encoding='utf-8', buffering=1)
    except OSError as exc:
        show_startup_error(
            'Studio cannot write to its local folder. Clone it into a writable folder and run Setup Studio.cmd.\n'
            'Studioのフォルダーに書き込めません。書き込み可能な場所にクローンし、Setup Studio.cmdを実行してください。\n\n'
            f'{exc}'
        )
        return 1
    with log:
        import faulthandler
        from contextlib import redirect_stdout, redirect_stderr

        with redirect_stdout(log), redirect_stderr(log):
            faulthandler.enable(file=log, all_threads=True)
            try:
                from .studio import main as run
                run()
            except Exception as exc:
                traceback.print_exc()
                show_startup_error(
                    f'{exc}\n\nRun Setup Studio.cmd to check the environment.\n'
                    'Setup Studio.cmdで動作環境を確認できます。\n\n'
                    f'Log / ログ\n{log_path}'
                )
                return 1
            finally:
                faulthandler.disable()
    return 0


if __name__ == '__main__':
    sys.exit(main())

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
