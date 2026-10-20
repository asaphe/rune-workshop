"""Windows WebView2 host lifecycle, isolated from the system browser."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import setup_webview


class BrowserJob:
    """Kill Rune's browser process tree when the app/server exits."""
    def __init__(self):
        class BasicLimits(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                        ('flags', wintypes.DWORD), ('min_ws', ctypes.c_size_t),
                        ('max_ws', ctypes.c_size_t), ('active', wintypes.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                        ('scheduling', wintypes.DWORD)]
        class ExtendedLimits(ctypes.Structure):
            _fields_ = [('basic', BasicLimits), ('io', ctypes.c_uint64 * 6),
                        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
        self.api.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        self.api.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def assign(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


class AppWindow:
    def __init__(self, url, runtime):
        if not setup_webview.ready():
            raise RuntimeError('Run Launch Rune.cmd to set up the WebView2 host first.')
        data_root = Path(runtime) / 'webview2-data'
        data_root.mkdir(exist_ok=True)
        self.profile = Path(tempfile.mkdtemp(prefix='session-', dir=data_root))
        self.closed = threading.Event()
        self.error = None
        self.job = None
        self.process = None
        try:
            self.job = BrowserJob()
            env = {k: v for k, v in os.environ.items() if not k.upper().startswith('WEBVIEW2_')}
            self.process = subprocess.Popen([
                str(setup_webview.target() / 'Rune.exe'), url, str(self.profile),
                str(Path(__file__).parent / 'web/rune.ico')],
                stdin=subprocess.PIPE, text=True, env=env)
            self.job.assign(self.process)
        except Exception:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=5)
            if self.job is not None:
                self.job.close()
            shutil.rmtree(self.profile, ignore_errors=True)
            raise

    def watch(self, on_close):
        while not self.closed.wait(.2):
            code = self.process.poll()
            if code is not None:
                if code != 0:
                    self.error = 'Rune WebView2 host exited unexpectedly (code %s). See .runtime/startup.log.' % code
                if not self.closed.is_set():
                    on_close()
                return

    def close(self):
        self.closed.set()
        try:
            if self.process.poll() is None:
                try:
                    self.process.stdin.write('close\n')
                    self.process.stdin.flush()
                    self.process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        finally:
            self.job.close()
            if self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=5)
            if self.process.stdin:
                self.process.stdin.close()
        for _ in range(30):
            try:
                shutil.rmtree(self.profile)
                break
            except OSError:
                time.sleep(.1)
