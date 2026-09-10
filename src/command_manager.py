import json
import subprocess
import webbrowser
from pathlib import Path

from src.recognition_comparator import compare_with_etalon


def load_commands(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)


def find_best_command(
    recognized: list[str],
    commands: dict,
    threshold: float = 0.60,
):
    best_command = None
    best_score = 0.0

    for command_name, command in commands.items():

        for phrase in command["phrases"]:

            # Convert JSON phrase to tokens
            expected = phrase.split()

            score, _ = compare_with_etalon(
                recognized,
                expected,
            )

            if score > best_score:
                best_score = score
                best_command = command_name

    if best_score < threshold:
        return None, best_score

    return best_command, best_score


def execute_command(command):
    action = command["action"]

    action_type = action["type"]

    if action_type == "program":
        launch_program(action["path"])

    elif action_type == "close_program":
        close_program(action["path"])

    elif action_type == "browser":
        open_browser(action["url"])

    else:
        raise ValueError(
            f"Невідома дія: {action_type}"
        )


def launch_program(path: str):
    subprocess.Popen(path)


def close_program(path):
    subprocess.run([
        "powershell", "-Command",
        f"Get-CimInstance Win32_Process | "
        f"Where-Object {{$_.CommandLine -like '*{path}*'}} | "
        f"Invoke-CimMethod -MethodName Terminate"
    ])


def open_browser(url: str):
    webbrowser.open_new_tab(url)
