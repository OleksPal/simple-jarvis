
from copy import deepcopy
import customtkinter as ctk
from tkinter import filedialog
from CTkMessagebox import CTkMessagebox

from phrase_list_editor import PhraseListEditor
from underlined_entry import UnderlinedEntry

ACTION_MAP = {
    "Відкрити файл": "open_file",
    "Закрити файл": "close_file",
    "Відкрити посилання": "open_url",
    "Закрити поточну вкладку": "close_current_tab",
    "Закрити Jarvis": "close_jarvis",
}

class CommandSettings(ctk.CTkFrame):    
    def __init__(self, master, on_create=None, on_edit=None, on_delete=None, **kwargs):
        super().__init__(master, **kwargs)

        self.current_command = None
        self.on_create = on_create
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.original_name = None
        self.original_command = {}

        # Main content: scrollable, with room for the footer
        self.content_frame = ctk.CTkScrollableFrame(
            self,
            orientation="vertical",
            fg_color="transparent",
        )
        self.content_frame.pack(
            side="top",
            fill="both",
            expand=True,
        )

        # Sticky bottom action bar
        self.footer = ctk.CTkFrame(
            self,
            corner_radius=0,
        )
        self.footer.pack(
            side="bottom",
            fill="x",
        )

        self.footer.grid_columnconfigure(0, weight=1)

        self.cancel_button = ctk.CTkButton(
            self.footer,
            text="Скасувати",
            width=110,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            hover_color=("gray80", "gray25"),
            command=self.on_cancel,
        )
        self.cancel_button.grid(
            row=0,
            column=1,
            padx=(10, 8),
            pady=12,
        )

        self.save_button = ctk.CTkButton(
            self.footer,
            text="Зберегти",
            width=120,
            command=self.on_save,
            state="disabled",
        )
        self.save_button.grid(
            row=0,
            column=2,
            padx=(0, 20),
            pady=12,
        )

    def show_settings(self, name, command):
        self.original_name = name
        self.original_command = deepcopy(command)
        self.current_command = deepcopy(command)

        # Clear previous settings
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        action = self.current_command["action"]

        # Header
        self.header_frame = ctk.CTkFrame(
            self.content_frame,
            fg_color="transparent",
        )
        self.header_frame.pack(
            fill="x",
            padx=20,
            pady=(20, 5),
        )

        # Command name on the left
        self.name_input = UnderlinedEntry(
            self.header_frame,
            value=name,
            font_size=22,
        )
        self.name_input.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 15),
        )

        # Delete command button at the top
        self.delete_command_button = ctk.CTkButton(
            self.header_frame,
            text="Видалити",
            command=self.confirm_delete,
        )
        self.delete_command_button.pack(
            fill="x",
            pady=(5, 10),
        )

        # Voice phrases
        self.string_editor = PhraseListEditor(
            master=self.content_frame,
            values=command.get("phrases", []),
            on_change=self.update_save_button,
        )
        self.string_editor.pack(fill="x", padx=20, pady=10)

        # Action type label
        ctk.CTkLabel(
            self.content_frame,
            font=ctk.CTkFont(weight="bold"),
            text="Тип дії:",
        ).pack(anchor="w", padx=20, pady=(10, 0))

        # Action type dropdown
        self.action_type_var = ctk.StringVar(
            value=self.key_to_action(action["type"])
        )

        self.action_type_dropdown = ctk.CTkOptionMenu(
            self.content_frame,
            variable=self.action_type_var,
            values=[
                "Відкрити файл",
                "Закрити файл",
                "Відкрити посилання",
                "Закрити поточну вкладку",
                "Закрити Jarvis",
            ],
            command=self.on_action_type_change,
        )

        self.action_type_dropdown.pack(
            anchor="w",
            padx=20,
            pady=5,
        )

        self.property_frame = ctk.CTkFrame(
            self.content_frame,
            fg_color="transparent",
        )
        self.property_frame.pack(
            fill="x",
            anchor="w",
            padx=0,
            pady=5,
        )

        # Revalidate when the name or action property changes
        self.name_input.entry.bind(
            "<KeyRelease>",
            self.update_save_button,
            add="+",
        )

        self.show_action_property()
        self.update_save_button()

    def get_action_property(self, action_type):
        if action_type in ("open_file", "close_file"):
            return "Шлях", "path"

        if action_type == "open_url":
            return "Посилання", "url"

        return None, None

    def show_action_property(self):
        action = self.current_command["action"]
        action_type = action["type"]

        label_text, property_key = self.get_action_property(action_type)

        # Nothing to display for this action type
        if property_key is None:
            return

        # Label
        ctk.CTkLabel(
            self.property_frame, 
            font=ctk.CTkFont(weight="bold"),
            text=f"{label_text}:",
        ).pack(anchor="w", padx=20, pady=(5, 0))

        # Input initialized from existing command data
        self.property_var = ctk.StringVar(
            value=action.get(property_key, "")
        )

        # Input and optional Browse button
        input_frame = ctk.CTkFrame(
            self.property_frame,
            fg_color="transparent",
        )
        input_frame.pack(
            anchor="w",
            fill="x",
            padx=20,
            pady=5,
        )

        self.property_input = UnderlinedEntry(
            input_frame,
            value=action.get(property_key, ""),
            font_size=14,
        )
        self.property_input.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 5),
        )

        self.property_input.entry.bind(
            "<KeyRelease>",
            self.update_save_button,
            add="+",
        )

        if property_key == "path":
            ctk.CTkButton(
                input_frame,
                text="Пошук...",
                width=80,
                command=self.browse_file,
            ).pack(side="left")

    def on_action_type_change(self, value):
        action_type = self.action_to_key(value)
        self.current_command["action"]["type"] = action_type

        for widget in self.property_frame.winfo_children():
            widget.destroy()

        self.show_action_property()
        self.update_save_button()

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select a program",
            filetypes=[
                ("Executable files", "*.exe"),
                ("All files", "*.*"),
            ],
        )

        if file_path:
            self.property_input.set(file_path)

        self.update_save_button()
    
    def show_empty_settings(self):
        self.original_name = None
        self.original_command = None

        self.current_command = {
            "phrases": [""],
            "action": {
                "type": "open_file",
                "enabled": False,
                "path": "",
            },
        }

        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # Header — same layout as an existing command
        self.header_frame = ctk.CTkFrame(
            self.content_frame,
            fg_color="transparent",
        )
        self.header_frame.pack(
            fill="x",
            padx=20,
            pady=(20, 5),
        )

        self.name_input = UnderlinedEntry(
            self.header_frame,
            value="",
            font_size=22,
        )
        self.name_input.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 15),
        )

        # Voice phrases — one empty entry
        self.string_editor = PhraseListEditor(
            master=self.content_frame,
            values=[""],
            on_change=self.update_save_button,
        )
        self.string_editor.pack(
            fill="x",
            padx=20,
            pady=10,
        )

        # Action type label
        ctk.CTkLabel(
            self.content_frame,
            font=ctk.CTkFont(weight="bold"),
            text="Тип дії:",
        ).pack(anchor="w", padx=20, pady=(10, 0))

        # Action dropdown — defaults to program
        self.action_type_var = ctk.StringVar(value=self.key_to_action("open_file"))

        self.action_type_dropdown = ctk.CTkOptionMenu(
            self.content_frame,
            variable=self.action_type_var,
            values=[
                "Відкрити файл",
                "Закрити файл",
                "Відкрити посилання",
                "Закрити поточну вкладку",
                "Закрити Jarvis",
            ],
            command=self.on_action_type_change,
        )
        self.action_type_dropdown.pack(
            anchor="w",
            padx=20,
            pady=5,
        )

        # Action property — initially an empty Path field
        self.property_frame = ctk.CTkFrame(
            self.content_frame,
            fg_color="transparent",
        )
        self.property_frame.pack(
            fill="x",
            anchor="w",
            padx=0,
            pady=5,
        )

        self.show_action_property()
        self.update_save_button()

    def create_command(self):
        name = self.name_input.get()

        if not name:
            print("Please enter a command name.")
            return

        if self.on_create:
            self.on_create(
                name,
                {
                    "phrases": self.string_editor.strings,
                    "action": {
                        "type": "program",
                        "enabled": True,
                        "path": "",
                    },
                },
            )

    def validate_fields(self):
        if not hasattr(self, "name_input"):
            return False

        if not self.name_input.get().strip():
            return False

        if not any(
            phrase.strip()
            for phrase in self.string_editor.strings
        ):
            return False

        action_type = self.action_to_key(self.action_type_var.get())
        _, property_key = self.get_action_property(action_type)

        if property_key is not None:
            if not hasattr(self, "property_input"):
                return False

            if not self.property_input.get().strip():
                return False

        return True

    def update_save_button(self, *args):
        if self.validate_fields():
            self.save_button.configure(state="normal")
        else:
            self.save_button.configure(state="disabled")

    def on_save(self):
        name = self.name_input.get().strip()

        action = self.current_command["action"]
        action_type = action["type"]

        _, property_key = self.get_action_property(action_type)

        action_content = {
            "type": action_type,
            "enabled": action.get("enabled", True),
        }

        if property_key is not None:
            action_content[property_key] = self.property_input.get().strip()

        command_content = {
            "phrases": self.string_editor.strings,
            "action": action_content,
        }

        if self.original_name is not None and self.on_edit:
            self.on_edit(self.original_name, name, command_content)
        elif self.on_create:
            self.on_create(name, command_content)

    def confirm_delete(self):
        result = CTkMessagebox(
            title="Підтвердження видалення",
            message="Ви впевнені, що хочете видалити цю команду?",
            icon="warning",
            option_1="Відмінити",
            option_2="Видалити",
            width=350,
            height=180,
            justify="center",
            button_color="#DC2626",
            button_hover_color="#B91C1C",
            bg_color="#1E1E1E",
            fg_color="#1E1E1E",
            text_color="#FFFFFF",
            title_color="#FFFFFF"
        ).get()

        if result == "Видалити":
            self.on_delete(self.original_name)

    def on_cancel(self):
        if self.original_name is not None:
            # Editing an existing command: discard changes and restore it
            self.show_settings(
                self.original_name,
                deepcopy(self.original_command),
            )
        else:
            # Creating a new command: reset to empty settings
            self.show_empty_settings()

    @staticmethod
    def action_to_key(action_name):
        """Convert display name to internal key."""
        return ACTION_MAP.get(action_name)

    @staticmethod
    def key_to_action(action_key):
        """Convert internal key to display name."""
        return {value: key for key, value in ACTION_MAP.items()}.get(action_key)