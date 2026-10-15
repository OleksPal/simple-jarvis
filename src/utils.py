import os
from pathlib import Path
import subprocess
import sys
from importlib.metadata import version, PackageNotFoundError

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[33m"
RESET = "\033[0m"

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
    try:
        torch_version = version("torch")
        audio_version = version("torchaudio")

        if not torch_version.startswith("2.11.0"):
            return False

        if not audio_version.startswith("2.11.0"):
            return False

        return True

    except (PackageNotFoundError, ImportError):
        return False
    
def install_pytorch():
    if is_pytorch_installed():
        return

    print(f"[{GREEN}OK{RESET}] Встановлюється CPU PyTorch...")
    print()

    run_pip(
        "--extra-index-url",
        "https://download.pytorch.org/whl/cpu",
        "torch==2.11.0",
        "torchaudio==2.11.0",
    )

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
