import json
import subprocess
import webbrowser
import pyautogui

def load_commands(filename):
    file_content = {}

    with open(filename, "r", encoding="utf-8") as file:
        file_content = json.load(file)

    return file_content["commands"]

def save_commands(filename, commands):
    file_content = {
        "commands": commands
    }

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(file_content, file, ensure_ascii=False, indent=4)


def get_command_name(phrase: str, config: dict) -> str | None:
    cleaned_phrase = phrase.strip().lower()

    for command_name, data in config.items():
        if cleaned_phrase in [
            p.strip().lower()
            for p in data.get("phrases", [])
        ]:
            return command_name

    return None

def get_phrases(config):
    commands_dict = config.get("commands", config)
    
    return [
        phrase
        for command in commands_dict.values()
        if isinstance(command, dict)
        for phrase in command.get("phrases", []) 
    ]

def execute_command(command):
    action = command["action"]

    action_type = action["type"]

    if action_type == "open_file":
        launch_program(action["path"])

    elif action_type == "close_file":
        close_program(action["path"])

    elif action_type == "open_url":
        open_browser(action["url"])

    elif action_type == "close_current_tab":
        close_current_tab()

    elif action_type == "close_jarvis":
        close_jarvis()

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

def close_current_tab():
    pyautogui.keyDown("ctrl")
    pyautogui.press("w")
    pyautogui.keyUp("ctrl")

def close_jarvis():
    exit()

def open_browser(url: str):
    webbrowser.open_new_tab(url)
