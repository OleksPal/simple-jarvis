import os
from pathlib import Path
import subprocess
import sys
import gc
import torch
from importlib.metadata import version, PackageNotFoundError

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[33m"
RESET = "\033[0m"

def is_cuda_gpu_enable():
    return os.system("nvidia-smi >nul 2>&1") == 0

def add_jarvis_to_startup():
    current_folder = Path.cwd()
    script_path = current_folder / "script.py"

    startup_folder = (
        Path(os.environ["APPDATA"])
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )

    shortcut_path = startup_folder / "Jarvis.lnk"

    powershell_script = f'''
        $ws = New-Object -ComObject WScript.Shell
        $sc = $ws.CreateShortcut("{shortcut_path}")
        $sc.TargetPath = "python.exe"
        $sc.Arguments = '"{script_path}"'
        $sc.WorkingDirectory = "{current_folder}"
        $sc.Save()
    '''

    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            powershell_script,
        ],
        check=True,
    )

def cleanup_memory():
    """Release unused Python and CUDA memory."""
    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()