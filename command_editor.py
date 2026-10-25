import customtkinter as ctk
from ctkfontawesome import icon_to_ctkimage
from pathlib import Path
import threading
import queue
from src.ui.command_row import CommandRow
from src.ui.command_settings import CommandSettings
from src.command_manager import load_commands, save_commands, get_phrases

from src.logger import setup_logger
from src.ui.log_console import LogConsole
from src.ui.assistant_control import AssistantControl

import src.init_utils as init_utils

logger = setup_logger()

COMMANDS_PATH = Path("config/commands.json")
CONFIG_PATH = Path("config/jarvis.config.json")

ACTION_MAP = {
    "Відкрити файл": "open_file",
    "Закрити файл": "close_file",
    "Відкрити посилання": "open_url",
    "Закрити поточну вкладку": "close_current_tab",
    "Закрити Jarvis": "close_jarvis",
}

add_icon = icon_to_ctkimage(
    "plus",
    fill="#FFFFFF",
    scale_to_width=14
)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Jarvis")
        self.geometry("950x600")
        self.minsize(800, 500)

        # Application state
        self.commands = load_commands(COMMANDS_PATH)
        self.rows = {}
        self.selected_command = None

        # Create tabs
        self.tabview = ctk.CTkTabview(
            self,
            corner_radius=10,
            border_width=1,

            segmented_button_font=ctk.CTkFont(
                family="Arial",
                size=15,
                weight="bold",
            ),

            segmented_button_fg_color="#1E1E1E",
            segmented_button_selected_color="#2563EB",
            segmented_button_selected_hover_color="#1D4ED8",
            segmented_button_unselected_color="#2B2B2B",
            segmented_button_unselected_hover_color="#3B3B3B",

            text_color="#FFFFFF",
            anchor="nw",
        )

        self.tabview.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=5,
        )

        self.tabview._segmented_button.configure(
            font=ctk.CTkFont(
                family="Arial",
                size=15,
                weight="bold",
            )
        )

        self.command_center_tab = self.tabview.add("Центр керування")
        self.commands_tab = self.tabview.add("Команди")        

        # Build the interface
        self._configure_layout()
        self._create_command_list()
        self._create_settings_panel()

        # Populate command list
        for name, data in self.commands.items():
            self._create_command_row(name, data)

        # Select the first command
        if self.commands:
            self.select_command(next(iter(self.commands)))

        # Create assistant control
        self.assistant_control = AssistantControl(
            master=self.command_center_tab,
            on_start=self.start_assistant,
            on_stop=self.stop_assistant,
        )
        
        self.assistant_control.pack(
            fill="x",
            padx=10,
            pady=10
        )

        # Create the live log console
        self.log_console = LogConsole(
            master=self.command_center_tab,
            logger=logger,
        )
        self.log_console.pack(
            fill="both",
            expand=True,
            padx=10
        )

        # Assistant state
        self.assistant_thread = None
        self.assistant_running = False
        self.restart_requested = False

        # A new event is created for every execution.
        self.assistant_stop_event = threading.Event()
        self.assistant_events = queue.Queue()

        # Persistent resources, reused across Start/Stop cycles.
        self.assistant_resources = {}

        # Start the assistant after the GUI has had time to appear.
        self.after(100, self.start_assistant)

        # Poll status messages on the Tkinter main thread.
        self.after(100, self._process_assistant_events)
    
    def _configure_layout(self):
        self.commands_tab.grid_columnconfigure(0, weight=0, minsize=320)
        self.commands_tab.grid_columnconfigure(1, weight=1)
        self.commands_tab.grid_rowconfigure(0, weight=1)
    
    def _create_command_list(self):
        self.command_container = ctk.CTkFrame(self.commands_tab)

        self.command_container.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=10,
            pady=10,
        )

        self.command_container.grid_columnconfigure(0, weight=1)
        self.command_container.grid_rowconfigure(0, weight=1)

        self.command_list = ctk.CTkScrollableFrame(
            self.command_container,
            label_text="Команди",
        )

        self.command_list.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=5,
            pady=(0, 5),
        )
        
        # Command name filter
        self.command_filter_entry = ctk.CTkEntry(
            self.command_list,
            placeholder_text="Пошук команд...",
        )
        self.command_filter_entry.pack(
            fill="x",
            pady=(5, 10),
        )

        self.command_filter_entry.bind(
            "<KeyRelease>",
            self.filter_commands,
        )

        self.add_command_button = ctk.CTkButton(
            self.command_list,
            text="Додати нову команду",
            image=add_icon,
            command=self.add_new_command,
        )

        self.add_command_button.pack(
            fill="x",
            pady=(5, 10),
    )
    
    def _create_settings_panel(self):
        self.settings_container = ctk.CTkFrame(
            self.commands_tab,
            fg_color="transparent",
        )

        self.settings_container.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=10,
            pady=10,
        )

        self.settings_container.grid_rowconfigure(0, weight=1)
        self.settings_container.grid_columnconfigure(0, weight=1)

        self.settings_panel = CommandSettings(
            self.settings_container,
            on_create=self.create_command,
            on_edit=self.edit_command,
            on_delete=self.delete_command,
        )

        self.settings_panel.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

    def select_command(self, name):
        self.selected_command = name

        for row_name, row in self.rows.items():
            row.set_selected(row_name == name)

        self.show_settings(name)

    def toggle_command(self, name, enabled):
        self.commands[name]["action"]["enabled"] = enabled

        save_commands(COMMANDS_PATH, self.commands)

        if self.selected_command == name:
            self.show_settings(name)

    def show_settings(self, name):
        command = self.commands[name]
        self.settings_panel.show_settings(name, command)

    def add_new_command(self):
        # Deselect the currently selected command
        for row in self.rows.values():
            row.set_selected(False)

        self.selected_command = None

        # Display the empty settings view
        self.settings_panel.show_empty_settings()

    def _create_command_row(self, name, command):
        action = command["action"]

        row = CommandRow(
            master=self.command_list,
            name=name,
            description=self.key_to_action(action["type"]),
            enabled=action.get("enabled", True),
            on_select=self.select_command,
            on_toggle=self.toggle_command,
        )

        row.pack(fill="x", pady=3)
        self.rows[name] = row

        return row

    def create_command(self, name, command):
        name = name.strip()

        if not name:
            return False

        if name in self.commands:
            return False

        self.commands[name] = command
        save_commands(COMMANDS_PATH, self.commands)

        self._create_command_row(name, command)

        self.select_command(name)

        self.restart_assistant_if_running()
        return True
    
    def edit_command(self, old_name, new_name, command):
        new_name = new_name.strip()

        if not new_name or old_name not in self.commands:
            return False

        if new_name != old_name and new_name in self.commands:
            return False

        # Preserve command order
        updated_commands = {
            (new_name if name == old_name else name):
                (command if name == old_name else data)
            for name, data in self.commands.items()
        }

        old_row = self.rows[old_name]

        if new_name == old_name:
            # Update the existing row without destroying it
            old_row.update_content(
                name=new_name,
                description=self.key_to_action(
                    command["action"]["type"]
                ),
            )
            old_row.set_enabled(
                command["action"].get("enabled", True)
            )

        else:
            # A renamed command needs a new row with the new callback identity
            old_row.destroy()
            self.rows.pop(old_name)

            self._create_command_row(new_name, command)

            # Restore the original visual order
            for row in self.rows.values():
                row.pack_forget()

            for name in updated_commands:
                self.rows[name].pack(fill="x", pady=3)

        self.commands = updated_commands

        save_commands(COMMANDS_PATH, self.commands)
        self.select_command(new_name)

        self.restart_assistant_if_running()
        return True

    def delete_command(self, name):
        if not name:
            return

        if name in self.commands:
            del self.commands[name]

            # Remove the old entry and its row
            old_row = self.rows.pop(name, None)
            if old_row:
                old_row.destroy()

            if self.commands:
                self.select_command(next(iter(self.commands)))
            else:
                self.selected_command = None
                self.settings_panel.show_empty_settings()

            save_commands(COMMANDS_PATH, self.commands)
            self.restart_assistant_if_running()
        else:
            return
    
    def filter_commands(self, event=None):
        query = self.command_filter_entry.get().strip().casefold()

        # Hide all command rows
        for row in self.rows.values():
            row.pack_forget()

        # Show matching rows in their original order
        for name in self.commands:
            if query in name.casefold():
                self.rows[name].pack(fill="x", pady=3)

    
    def start_assistant(self):
        # Never launch a second worker while the previous one is alive.
        if self.assistant_thread and self.assistant_thread.is_alive():
            return

        # A fresh event is essential for each new execution.
        self.assistant_stop_event = threading.Event()
        stop_event = self.assistant_stop_event

        self.assistant_running = True

        self.assistant_thread = threading.Thread(
            target=self._assistant_worker,
            args=(stop_event,),
            daemon=True,
            name="JarvisAssistant",
        )
        self.assistant_thread.start()

    def restart_assistant_if_running(self):
        """Restart the loop after the current worker exits."""

        # Don't automatically start the assistant if it is stopped.
        if not self.assistant_running:
            return

        if self.assistant_thread and self.assistant_thread.is_alive():
            self.restart_requested = True
            self.assistant_stop_event.set()
        else:
            self.start_assistant()

    def _get_assistant_resources(self, stop_event):
        """Load each expensive resource once and reuse it."""

        resources = self.assistant_resources

        def should_stop():
            return stop_event.is_set()

        # Configuration
        if "config" not in resources:
            resources["config"] = init_utils.load_setup(CONFIG_PATH)

        if should_stop():
            return None

        config = resources["config"]

        # Voice activity detection
        if "vad_model" not in resources:
            resources["vad_model"] = init_utils.setup_vad()

        if should_stop():
            return None

        # Speech recognition
        if "speech_model" not in resources:
            resources["speech_model"] = (
                init_utils.setup_speech_recognition(config.model_size)
            )

        if should_stop():
            return None

        # Text-to-speech
        if "voice" not in resources:
            resources["voice"] = init_utils.setup_tts(config.use_cuda)

        if should_stop():
            return None

        # Semantic command resolver
        if "resolver_model" not in resources:
            resources["resolver_model"] = (
                init_utils.setup_sentence_transformer()
            )

        if should_stop():
            return None

        # Wake-word detector
        if "wakeword_model" not in resources:
            resources["wakeword_model"] = init_utils.setup_wake_word()

        return resources


    def _assistant_worker(self, stop_event):
        failed = False

        try:
            self.assistant_events.put(("status", "Ініціалізація..."))

            resources = self._get_assistant_resources(stop_event)

            # Stop may have been requested during model initialization.
            if resources is None or stop_event.is_set():
                return

            # Rebuild command phrases for each run, since commands may
            # have been added, edited, or deleted in the UI.
            commands = dict(self.commands)
            phrases = get_phrases(commands)

            encoded_options = init_utils.setup_encoded_phrases(
                resources["resolver_model"],
                phrases,
            )

            if stop_event.is_set():
                return

            self.assistant_events.put(("status", "Слухаю"))

            init_utils.start_loop(
                config=resources["config"],
                speech_recognition_model=resources["speech_model"],
                wakeword_model=resources["wakeword_model"],
                resolver_model=resources["resolver_model"],
                vad_model=resources["vad_model"],
                encoded_options=encoded_options,
                commands=commands,
                voice=resources["voice"],
                stop_event=stop_event,
                status_callback=self._report_status,
            )

        except Exception:
            failed = True
            logger.exception("Assistant failed")

        finally:
            self.assistant_running = False

            self.assistant_events.put((
                "status",
                "Помилка" if failed else "Зупинено",
            ))


    def stop_assistant(self):
        if self.assistant_thread and self.assistant_thread.is_alive():
            self.assistant_events.put(("status", "Зупиняюсь..."))
            self.assistant_stop_event.set()

    def _report_status(self, status):
        """Called by the assistant worker thread."""
        self.assistant_events.put(("status", status))

    def _process_assistant_events(self):
        """Update Tkinter widgets only on the main thread."""
        try:
            while True:
                event_type, value = self.assistant_events.get_nowait()

                if event_type == "status":
                    self.assistant_control.set_status(value)

        except queue.Empty:
            pass

        if (
            self.restart_requested
            and (
                self.assistant_thread is None
                or not self.assistant_thread.is_alive()
            )
        ):
            self.restart_requested = False
            self.start_assistant()

        self.after(100, self._process_assistant_events)

    @staticmethod
    def action_to_key(action_name):
        """Convert display name to internal key."""
        return ACTION_MAP.get(action_name)

    @staticmethod
    def key_to_action(action_key):
        """Convert internal key to display name."""
        return {value: key for key, value in ACTION_MAP.items()}.get(action_key)      

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    App().mainloop()
