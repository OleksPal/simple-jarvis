
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

ACTION_LABELS = list(ACTION_MAP.keys())
KEY_TO_ACTION = {
    action_key: label
    for label, action_key in ACTION_MAP.items()
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

        self._build_form(name, self.current_command, is_new=False)

    def show_empty_settings(self):
        self.original_name = None
        self.original_command = None

        self.current_command = {
            "phrases": [""],
            "action": {
                "type": "open_file",
                "enabled": True,
                "path": "",
            },
        }

        self._build_form("", self.current_command, is_new=True)
    
    def _build_form(self, name, command, is_new=False):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        self.property_input = None

        action = command["action"]
        action_label = self.key_to_action(action["type"])

        if action_label is None:
            raise ValueError(
                f"Unsupported action type: {action['type']!r}"
            )

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

        if not is_new:
            self.delete_command_button = ctk.CTkButton(
                self.header_frame,
                text="Видалити",
                command=self.confirm_delete,
            )
            self.delete_command_button.pack(
                side="left",
                padx=(0, 5),
            )

        # Voice phrases
        self.string_editor = PhraseListEditor(
            master=self.content_frame,
            values=command.get("phrases", []),
            on_change=self.update_save_button,
        )
        self.string_editor.pack(
            fill="x",
            padx=20,
            pady=10,
        )

        # Action type
        ctk.CTkLabel(
            self.content_frame,
            font=ctk.CTkFont(weight="bold"),
            text="Тип дії:",
        ).pack(anchor="w", padx=20, pady=(10, 0))

        self.action_type_var = ctk.StringVar(value=action_label)

        self.action_type_dropdown = ctk.CTkOptionMenu(
            self.content_frame,
            variable=self.action_type_var,
            values=ACTION_LABELS,
            command=self.on_action_type_change,
        )
        self.action_type_dropdown.pack(
            anchor="w",
            padx=20,
            pady=5,
        )

        # Action-specific property
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
        self.property_input = None

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

        if action_type is None or self.current_command is None:
            return

        old_action = self.current_command["action"]

        # Preserve the enabled state while resetting action-specific data
        self.current_command["action"] = {
            "type": action_type,
            "enabled": old_action.get("enabled", True),
        }

        _, property_key = self.get_action_property(action_type)

        if property_key is not None:
            self.current_command["action"][property_key] = ""

        for widget in self.property_frame.winfo_children():
            widget.destroy()

        self.property_input = None
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

    def validate_fields(self):
        if self.current_command is None:
            return False

        if not self.name_input.get().strip():
            return False

        phrases = self.string_editor.strings

        if not any(
            isinstance(phrase, str) and phrase.strip()
            for phrase in phrases
        ):
            return False

        action_type = self.action_to_key(
            self.action_type_var.get()
        )

        if action_type is None:
            return False

        _, property_key = self.get_action_property(action_type)

        if property_key is not None:
            if self.property_input is None:
                return False

            if not self.property_input.get().strip():
                return False

        return True

    def update_save_button(self, *args):
        is_valid = self.validate_fields()

        self.save_button.configure(
            state="normal" if is_valid else "disabled"
        )

    def on_save(self):
        if self.current_command is None:
            return
    
        name = self.name_input.get().strip()

        if not name or not self.validate_fields():
            self.update_save_button()
            return

        is_editing = self.original_name is not None

        if is_editing and self.on_edit is None:
            return

        if not is_editing and self.on_create is None:
            return

        action_type = self.action_to_key(self.action_type_var.get())

        if action_type is None:
            return

        _, property_key = self.get_action_property(action_type)

        action_content = {
            "type": action_type,
            "enabled": self.current_command["action"].get(
                "enabled", True
            ),
        }

        if property_key is not None:
            if self.property_input is None:
                return

            action_content[property_key] = (
                self.property_input.get().strip()
            )

        command_content = {
            "phrases": [
                phrase.strip()
                for phrase in self.string_editor.strings
                if phrase.strip()
            ],
            "action": action_content,
        }

        try:
            if is_editing:
                result = self.on_edit(
                    self.original_name,
                    name,
                    command_content,
                )
            else:
                result = self.on_create(name, command_content)

            if result is False:
                self.show_error(
                    "Не вдалося зберегти команду. "
                    "Перевірте назву та спробуйте ще раз."
                )

        except Exception as exc:
            self.show_error(f"Не вдалося зберегти команду:\n{exc}")

    def confirm_delete(self):
        if self.on_delete is None or self.original_name is None:
            return
    
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
            self.show_settings(
                self.original_name,
                deepcopy(self.original_command),
            )
        else:
            # Creating a new command: reset to empty settings
            self.show_empty_settings()

    def show_error(self, message):
        CTkMessagebox(
            title="Помилка",
            message=message,
            icon="cancel",
            option_1="OK",
            width=380,
            height=180,
            justify="center",
            button_color="#DC2626",
            button_hover_color="#B91C1C",
            bg_color="#1E1E1E",
            fg_color="#1E1E1E",
            text_color="#FFFFFF",
            title_color="#FFFFFF",
        )
    
    @staticmethod
    def action_to_key(action_name):
        return ACTION_MAP.get(action_name)

    @staticmethod
    def key_to_action(action_key):
        return KEY_TO_ACTION.get(action_key)
