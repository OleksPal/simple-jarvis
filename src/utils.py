import os
from pathlib import Path
import subprocess
import sys
import gc
import torch

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[33m"
RESET = "\033[0m"

def is_cuda_gpu_enable():
    return os.system("nvidia-smi >nul 2>&1") == 0


def create_shortcut(shortcut_path: Path, script_path: Path, working_directory: Path):
    pythonw_path = Path(sys.executable).with_name("pythonw.exe")

    powershell_script = f'''
        $ws = New-Object -ComObject WScript.Shell
        $sc = $ws.CreateShortcut("{shortcut_path}")
        $sc.TargetPath = "{pythonw_path}"
        $sc.Arguments = '"{script_path}"'
        $sc.WorkingDirectory = "{working_directory}"
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
        capture_output=True,
        text=True,
    )

def cleanup_memory():
    """Release unused Python and CUDA memory."""
    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()