import os
from pathlib import Path
import subprocess
import sys
import importlib.metadata

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[33m"
RESET = "\033[0m"

PYTORCH_VERSION = "2.11.0"
CUDA_INDEX = "https://download.pytorch.org/whl/cu126"
CPU_INDEX = "https://download.pytorch.org/whl/cpu"

def run_pip(*args):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "--no-warn-script-location",
            *args,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        print()
        print(f"[{RED}FAILED{RESET}] Помилка встановлення пакета:")
        print(result.stderr)
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
        )

def is_pytorch_installed() -> bool:
    """Check whether the correct PyTorch build is installed."""

    suffix = "+cu126" if is_cuda_gpu_enable() else "+cpu"
    expected_version = PYTORCH_VERSION + suffix

    for package in ("torch", "torchaudio"):
        try:
            installed_version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            return False

        if installed_version != expected_version:
            return False

    return True
    
def install_pytorch() -> bool:
    """Install matching PyTorch and TorchAudio packages."""

    index_url = CUDA_INDEX if is_cuda_gpu_enable() else CPU_INDEX

    run_pip(
        "--upgrade",
        "--index-url", index_url,
        f"torch=={PYTORCH_VERSION}",
        f"torchaudio=={PYTORCH_VERSION}",
    )

    return is_pytorch_installed()

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
