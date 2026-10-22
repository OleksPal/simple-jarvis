
import customtkinter as ctk
from pathlib import Path
from command_row import CommandRow
from command_settings import CommandSettings
from src.command_manager import load_commands, save_commands

COMMANDS_PATH = Path("config/commands.json")

ACTION_MAP = {
    "Відкрити файл": "open_file",
    "Закрити файл": "close_file",
    "Відкрити посилання": "open_url",
    "Закрити поточну вкладку": "close_current_tab",
    "Закрити Jarvis": "close_jarvis",
}

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Jarvis - Редактор Команд")
        self.geometry("950x600")
        self.minsize(800, 500)

        self.next_id = 1

        # Main layout
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Load JSON configuration
        self.commands = load_commands(COMMANDS_PATH)

        self.rows = {}
        self.selected_command = None

        # Left-side container
        self.command_container = ctk.CTkFrame(self)
        self.command_container.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=10,
            pady=10,
        )

        self.command_container.grid_columnconfigure(0, weight=1)
        self.command_container.grid_rowconfigure(0, weight=1)

        # Scrollable command list below the button
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

        # Add command button at the top
        self.add_command_button = ctk.CTkButton(
            self.command_list,
            text="+ Додати нову команду",
            command=self.add_new_command,
        )
        self.add_command_button.pack(
            fill="x",
            pady=(5, 10),
        )

        # Regular settings container: fills the available right column
        self.settings_container = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )

        self.settings_container.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=10,
            pady=10,
        )

        # Make the container's cell expand with the window
        self.settings_container.grid_rowconfigure(0, weight=1)
        self.settings_container.grid_columnconfigure(0, weight=1)

        # Settings panel fills the entire container
        self.settings_panel = CommandSettings(
            self.settings_container,
            on_create=self.create_command,
            on_edit=self.edit_command,
            on_delete=self.delete_command
        )

        self.settings_panel.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        # Create command rows
        for name, data in self.commands.items():
            action = data["action"]

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

        # Select the first command
        if self.commands:
            self.select_command(next(iter(self.commands)))

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

    def create_command(self, name, command):
        name = name.strip()

        if not name:
            return False

        if name in self.commands:
            return False

        self.commands[name] = command
        save_commands(COMMANDS_PATH, self.commands)

        row = CommandRow(
            master=self.command_list,
            name=name,
            description=self.key_to_action(command["action"]["type"]),
            enabled=True,
            on_select=self.select_command,
            on_toggle=self.toggle_command,
        )
        row.pack(fill="x", pady=3)

        self.rows[name] = row
        self.select_command(name)

        return True

    def edit_command(self, old_name, new_name, command):
        new_name = new_name.strip()

        if not new_name or old_name not in self.commands:
            return False

        if new_name != old_name and new_name in self.commands:
            return False

        # Preserve the original position
        updated_commands = {
            (new_name if name == old_name else name):
                (command if name == old_name else data)
            for name, data in self.commands.items()
        }

        # Build the replacement row
        row = CommandRow(
            master=self.command_list,
            name=new_name,
            description=self.key_to_action(command["action"]["type"]),
            enabled=command["action"].get("enabled", True),
            on_select=self.select_command,
            on_toggle=self.toggle_command,
        )

        old_row = self.rows.get(old_name)

        # Update state
        self.commands = updated_commands

        if old_row:
            old_row.destroy()

        self.rows.pop(old_name, None)
        self.rows[new_name] = row

        # Repack rows in dictionary order
        for command_row in self.rows.values():
            command_row.pack_forget()

        for name in self.commands:
            self.rows[name].pack(fill="x", pady=3)

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
