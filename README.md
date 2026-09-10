# Jarvis

A Python voice assistant for Windows.

## Features

- Voice commands
- Open websites
- Launch programs
- Close programs

## Requirements

- Python 3.11
- Windows
- A working microphone and audio output

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/OleksPal/Jarvis.git
cd Jarvis
```

### 2. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 3. Verify the installation

Check for dependency conflicts:

```bash
python -m pip check
```

## Running the Project

Before running the application, run `setup.py`. The setup script downloads the required additional TTS files and creates the configuration files needed by the project:

```bash
python setup.py
```

Run the application with:

```bash
python script.py
```

## Adding Custom Commands

Custom voice commands can be added or modified in:

```text
config/commands.json
```

The `commands.json` file is created automatically by `setup.py` if it does not exist.

Each command has three main parts:

- **Command name** — the name used to identify the command in the configuration file.
- **Phrases** — phrases that Jarvis recognizes as triggers for the command.
- **Action** — what Jarvis should do when one of the phrases is recognized.

### Command Structure

A command has the following structure:

```json
{
    "Command Name": {
        "phrases": [
            "first phrase",
            "second phrase"
        ],
        "action": {
            "type": "action_type",
            "path": "path_or_url"
        }
    }
}
```

### Supported Actions

#### Open a Website

Use the `browser` action to open a URL in the default browser:

```json
"Open YouTube": {
    "phrases": [
        "open youtube",
        "start youtube"
    ],
    "action": {
        "type": "browser",
        "url": "https://www.youtube.com"
    }
}
```

The `url` field specifies the website that should be opened.

#### Launch a Program

Use the `program` action to launch an application:

```json
"Open Notepad": {
    "phrases": [
        "open notepad",
        "start notepad"
    ],
    "action": {
        "type": "program",
        "path": "notepad.exe"
    }
}
```

The `path` field specifies the executable to launch.

For programs that are not available through the system `PATH`, provide the full path to the executable:

```json
"path": "C:\\Program Files\\MyProgram\\program.exe"
```

Note that Windows backslashes must be escaped as `\\` in JSON.

#### Close a Program

Use the `close_program` action to close a running program:

```json
"Close Notepad": {
    "phrases": [
        "close notepad",
        "stop notepad"
    ],
    "action": {
        "type": "close_program",
        "path": "notepad.exe"
    }
}
```

The `path` field specifies the program that should be closed. Depending on the program, you can provide either the executable name or the full path to the executable:

```json
"path": "notepad.exe"
```

or:

```json
"path": "C:\\Program Files\\MyProgram\\program.exe"
```

Windows backslashes must be escaped as `\\` in JSON.

### Adding a New Command

To add a new command, add another entry inside the main `{ }` object in `commands.json`.

For example:

```json
{
    "YouTube": {
        "phrases": [
            "open youtube",
            "start youtube"
        ],
        "action": {
            "type": "browser",
            "url": "https://www.youtube.com"
        }
    },
    "Calculator": {
        "phrases": [
            "open calculator",
            "start calculator"
        ],
        "action": {
            "type": "program",
            "path": "calc.exe"
        }
    }
}
```

You can add as many phrases as you want to the `phrases` array. This allows the same action to be triggered by different voice commands.

## Language Support

Currently, Jarvis supports **Ukrainian only** for voice commands and speech recognition.

When adding custom commands to `config/commands.json`, use Ukrainian phrases in the `phrases` array.

### Important

Make sure the JSON syntax is valid after making changes.

After modifying `commands.json`, restart Jarvis for the changes to take effect.

