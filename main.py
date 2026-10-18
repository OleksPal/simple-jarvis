
import customtkinter as ctk
from pathlib import Path
from command_row import CommandRow
from command_settings import CommandSettings
from src.command_manager import load_commands

COMMANDS_PATH = Path("config/commands.json")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Редактор Команд Jarvis")
        self.geometry("950x600")
        self.minsize(800, 500)

        self.next_id = 1

        # Main layout
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Load JSON configuration
        self.config_data = load_commands(COMMANDS_PATH)
        self.commands = self.config_data["commands"]

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

        # Scrollable settings container
        self.settings_scroll = ctk.CTkScrollableFrame(
            self,
            orientation="vertical",
        )

        self.settings_scroll.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=10,
            pady=10,
        )

        # Settings panel inside the scrollable container
        self.settings_panel = CommandSettings(
            self.settings_scroll,
            on_create=self.create_command,
        )
        self.settings_panel.pack(
            fill="both",
            expand=True,
        )

        # Create command rows
        for name, data in self.commands.items():
            action = data["action"]

            row = CommandRow(
                master=self.command_list,
                name=name,
                description=action["type"],
                enabled=action.get("enabled", False),
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

        print(f"{name}: enabled={enabled}")

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
        if name in self.commands:
            print("A command with this name already exists.")
            return

        self.commands[name] = command

        row = CommandRow(
            master=self.command_list,
            name=name,
            description=command["action"]["type"],
            enabled=False,
            on_select=self.select_command,
            on_toggle=self.toggle_command,
        )
        row.pack(fill="x", pady=3)

        self.rows[name] = row
        self.select_command(name)


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    App().mainloop()
