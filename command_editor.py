import customtkinter as ctk
from ctkfontawesome import icon_to_ctkimage
from pathlib import Path
from src.ui.command_row import CommandRow
from src.ui.command_settings import CommandSettings
from src.command_manager import load_commands, save_commands

from src.logger import setup_logger
from src.ui.log_console import LogConsole
from src.ui.assistant_control import AssistantControl

logger = setup_logger()

COMMANDS_PATH = Path("config/commands.json")

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

        logger.debug("Debugging command execution")
        logger.info("Command executed successfully")
        logger.warning("Configuration value is missing")
        logger.error("Failed to open file")
        logger.critical("Application encountered a critical error")
        logger.debug("Debugging command execution")
        logger.info("Command executed successfully")
        logger.warning("Configuration value is missing")
        logger.error("Failed to open file")
        logger.critical("Application encountered a critical error")
        logger.debug("Debugging command execution")
        logger.info("Command executed successfully")
        logger.warning("Configuration value is missing")
        logger.error("Failed to open file")
        logger.critical("Application encountered a critical error")
        logger.debug("Debugging command execution")
        logger.info("Command executed successfully")
        logger.warning("Configuration value is missing")
        logger.error("Failed to open file")
        logger.critical("Application encountered a critical error")
        logger.debug("Debugging command execution")
        logger.info("Command executed successfully")
        logger.warning("Configuration value is missing")
        logger.error("Failed to open file")
        logger.critical("Application encountered a critical error")
        logger.debug("Debugging command execution")
        logger.info("Command executed successfully")
        logger.warning("Configuration value is missing")
        logger.error("Failed to open file")
        logger.critical("Application encountered a critical error")
    
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
        # TODO: Start your voice assistant backend.
        pass

    def stop_assistant(self):
        # TODO: Stop your voice assistant backend.
        pass

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
