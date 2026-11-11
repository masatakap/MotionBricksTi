# Copyright (c) 2026 MASATAKA. MASATAKA-owned contributions: CC0-1.0; see NOTICE.txt.
"""Shared local JSON transport, including Windows atomic-replace sharing semantics."""
from pathlib import Path
import errno
import functools
import json
import os
import time
import uuid


def transient_io(error):
    return isinstance(error,(PermissionError,FileNotFoundError)) or getattr(error,'winerror',None) in (5,32,33,303,1175) or error.errno in (errno.EAGAIN,errno.EBUSY)


@functools.lru_cache(maxsize=1)
def _windows_api():
    import ctypes
    from ctypes import wintypes
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    api.CreateFileW.restype=wintypes.HANDLE
    api.CloseHandle.argtypes=[wintypes.HANDLE];api.CloseHandle.restype=wintypes.BOOL
    api.ReplaceFileW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.DWORD,wintypes.LPVOID,wintypes.LPVOID]
    api.ReplaceFileW.restype=wintypes.BOOL
    return api


def read_text(path):
    if os.name!='nt':return Path(path).read_text(encoding='utf-8-sig')
    import ctypes,msvcrt
    api=_windows_api()
    # Share delete is essential: the writer publishes by replacing this pathname.
    handle=api.CreateFileW(os.path.abspath(path),0x80000000,0x7,None,3,0x80,None)
    if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    try:descriptor=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
    except BaseException:
        api.CloseHandle(handle);raise
    with os.fdopen(descriptor,'r',encoding='utf-8-sig') as stream:return stream.read()


def read_json(path,*,optional=False):
    for attempt in range(4):
        try:return json.loads(read_text(path))
        except OSError as exc:
            if not transient_io(exc):raise
            if optional:return None
            if attempt==3:raise
            time.sleep(.001*(attempt+1))


def write_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        for attempt in range(4):
            try:
                if os.name=='nt' and path.exists():
                    import ctypes
                    if not _windows_api().ReplaceFileW(os.path.abspath(path),os.path.abspath(temporary),None,0,None,None):
                        code=ctypes.get_last_error()
                        # ReplaceFile can fail to remove the old destination on
                        # Windows (1175). Rename replacement is still atomic;
                        # never fall back to truncating a live frame in place.
                        if code in (2,1175):os.replace(temporary,path)
                        else:raise ctypes.WinError(code)
                else:os.replace(temporary,path)
                return
            except OSError as exc:
                if not transient_io(exc) or attempt==3:raise
                time.sleep(.001*(attempt+1))
    finally:temporary.unlink(missing_ok=True)
def is_valid_object(value):
    """UE can reject a destroyed Python wrapper before IsValid even executes."""
    if value is None:return False
    try:
        import unreal
        return bool(unreal.SystemLibrary.is_valid(value))
    except Exception:
        return False

