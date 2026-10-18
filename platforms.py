"""Per-OS save locations, game-process checks, durable writes and the native file picker."""
import errno, os, re, subprocess, sys
from pathlib import Path

WINDOWS=os.name=='nt'
MACOS=sys.platform=='darwin'
APP_ID='892970'

def steam_roots():
    roots=[Path(os.environ['RUNE_STEAM_DIR']).expanduser()] if os.environ.get('RUNE_STEAM_DIR') else []
    if WINDOWS:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:roots.append(Path(winreg.QueryValueEx(key,'SteamPath')[0]))
        except OSError:pass
        roots.append(Path('C:/Program Files (x86)/Steam'))
    elif MACOS:roots.append(Path.home()/'Library/Application Support/Steam')
    return list(dict.fromkeys(roots))

def steam_remote_dirs(kind):
    return [p for root in steam_roots() for p in sorted((root/'userdata').glob(f'*/{APP_ID}/remote/{kind}')) if p.is_dir()]

def game_data_dirs():
    if WINDOWS:return [Path.home()/'AppData/LocalLow/IronGate/Valheim']
    # The Mac App Store build is sandboxed under ~/Library/Containers; scanning there triggers a macOS privacy prompt, so it is paste-a-path only.
    if MACOS:return [Path.home()/'Library/Application Support/IronGate/Valheim']
    return []

def local_dirs(kind):
    return [d/f'{kind}_local' for d in game_data_dirs()]

def process_name(entry):
    # ps prints "(name)" when it cannot read a process's arguments and "-zsh" for login shells.
    entry=entry.strip()
    if entry.startswith('(') and entry.endswith(')'):entry=entry[1:-1]
    return re.split(r'[\\/]',entry.lstrip('-'))[-1]

def is_game_process(name):
    # Prefix match because the macOS binary name is unconfirmed; a false match only blocks a save.
    return process_name(name).lower().startswith('valheim')

def _windows_processes():
    import ctypes
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),
                  ('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),
                  ('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),
                  ('name',wintypes.WCHAR*260)]
    dll=ctypes.WinDLL('kernel32',use_last_error=True)
    dll.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD]
    dll.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    dll.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    dll.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    dll.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=dll.CreateToolhelp32Snapshot(2,0)
    if handle==ctypes.c_void_p(-1).value:raise ValueError('Cannot check whether Valheim is running. Save cancelled.')
    names=[]
    try:
        entry=Entry();entry.size=ctypes.sizeof(entry)
        if not dll.Process32FirstW(handle,ctypes.byref(entry)):raise ValueError('Cannot inspect running processes. Save cancelled.')
        while True:
            names.append(entry.name)
            if not dll.Process32NextW(handle,ctypes.byref(entry)):
                if ctypes.get_last_error()!=18:raise ValueError('Process inspection failed. Save cancelled.')
                return names
    finally:dll.CloseHandle(handle)

def _macos_processes():
    try:result=subprocess.run(['/bin/ps','-axo','comm='],capture_output=True,text=True,errors='replace',timeout=10)
    except (OSError,subprocess.TimeoutExpired):raise ValueError('Cannot check whether Valheim is running. Save cancelled.')
    names=[process_name(line) for line in result.stdout.splitlines() if line.strip()]
    # ps always lists at least itself and launchd; an empty list means the check did not run.
    if result.returncode!=0 or len(names)<2:raise ValueError('Process inspection failed. Save cancelled.')
    return names

def ensure_game_closed():
    if WINDOWS:names=_windows_processes()
    elif MACOS:names=_macos_processes()
    else:raise ValueError('Direct saves are only enabled on Windows and macOS, where Rune can check that Valheim is closed.')
    running=next((n for n in names if is_game_process(n)),None)
    if running:raise ValueError(f'Close Valheim completely, including the main menu, before saving (found running process "{process_name(running)}").')

def flush_to_disk(stream):
    stream.flush()
    if MACOS:
        import fcntl
        # On macOS fsync only reaches the drive cache; F_FULLFSYNC is what survives power loss.
        try:fcntl.fcntl(stream.fileno(),fcntl.F_FULLFSYNC);return
        # Some network and FUSE volumes reject F_FULLFSYNC; fsync is the strongest flush they offer.
        except OSError as exc:
            if exc.errno not in (errno.ENOTSUP,errno.EOPNOTSUPP,errno.EINVAL,errno.ENOTTY):raise
    os.fsync(stream.fileno())

def pick_character_file():
    """Returns the chosen path, or None when the person cancels."""
    start=next((d for d in local_dirs('characters') if d.is_dir()),Path.home())
    if MACOS:
        # Tk must own the main thread on macOS and these requests run on worker threads, so use the system dialog instead.
        script=['on run argv','POSIX path of (choose file with prompt "Open Valheim character" default location (POSIX file (item 1 of argv)))','end run']
        args=['/usr/bin/osascript']+[part for line in script for part in ('-e',line)]+[str(start)]
        result=subprocess.run(args,capture_output=True,text=True)
        if result.returncode!=0:
            if re.search(r'\(-128\)\s*$',result.stderr):return None
            raise ValueError('The file picker could not be opened: '+result.stderr.strip())
        return result.stdout.strip() or None
    import tkinter as tk
    from tkinter import filedialog
    window=tk.Tk();window.withdraw();window.attributes('-topmost',True)
    try:path=filedialog.askopenfilename(parent=window,title='Open Valheim character',initialdir=str(start),filetypes=[('Valheim character','*.fch')])
    finally:window.destroy()
    return path or None
