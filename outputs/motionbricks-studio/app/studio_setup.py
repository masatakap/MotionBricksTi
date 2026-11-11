"""Checks used by the Windows source setup before downloading the model."""
import argparse
from pathlib import Path
import platform
import sys
import tempfile


def check_paths(root):
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64') or sys.maxsize <= 2**32:
        raise RuntimeError('Studio requires 64-bit Windows on x86-64 and 64-bit Python.')
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError('Studio setup uses Python 3.12.')
    user_data = root / 'user_data'
    for folder in (root, user_data):
        try:
            folder.mkdir(exist_ok=True)
            with tempfile.TemporaryFile(dir=folder) as probe:
                probe.write(b'Studio setup')
        except OSError as exc:
            raise RuntimeError(f'Cannot write to {folder}. Use a writable local clone.') from exc
    print(f'Python {platform.python_version()} | Windows x64 | Writable Studio folder')


def check_gpu():
    import warp as wp
    from .utils.model_loading import require_tensorrt

    wp.init()
    require_tensorrt()
    print(f'TensorRT initialized on {wp.get_device().name}. The model will be tested during first launch.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('check', choices=('paths', 'gpu'))
    args = parser.parse_args()
    try:
        if args.check == 'paths':
            check_paths(Path(__file__).resolve().parents[1])
        else:
            check_gpu()
    except Exception as exc:
        print(f'Studio setup check failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
