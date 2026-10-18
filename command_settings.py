
import customtkinter as ctk
from tkinter import filedialog

from phrase_list_editor import PhraseListEditor
from underlined_entry import UnderlinedEntry

class CommandSettings(ctk.CTkFrame):
    def __init__(self, master, on_create=None, **kwargs):
        super().__init__(master, **kwargs)
        self.current_command = None
        self.on_create = on_create

    def show_settings(self, name, command):
        self.current_command = command

        # Clear previous settings
        for widget in self.winfo_children():
            widget.destroy()

        action = command["action"]

        # Header
        self.header_frame = ctk.CTkFrame(
            self,
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

        # Buttons on the right
        ctk.CTkButton(
            self.header_frame,
            text="Відмінити",
            width=100,
            command=self.on_cancel,
        ).pack(side="right", padx=(10, 0))

        self.save_button = ctk.CTkButton(
            self.header_frame,
            text="Зберегти",
            width=100,
            command=self.on_save,  # Use self.create_command for a new command
            state="disabled",
        )
        self.save_button.pack(side="right")

        # Voice phrases
        self.string_editor = PhraseListEditor(
            master=self,
            values=command.get("phrases", []),
            on_change=self.update_save_button,
        )
        self.string_editor.pack(fill="x", padx=20, pady=10)

        # Action type label
        ctk.CTkLabel(
            self,
            font=ctk.CTkFont(weight="bold"),
            text="Тип дії:",
        ).pack(anchor="w", padx=20, pady=(10, 0))

        # Action type dropdown
        self.action_type_var = ctk.StringVar(
            value=action["type"]
        )

        self.action_type_dropdown = ctk.CTkOptionMenu(
            self,
            variable=self.action_type_var,
            values=[
                "program",
                "close_program",
                "browser",
                "close_current_tab",
                "close_jarvis",
            ],
            command=self.on_action_type_change,
        )

        self.action_type_dropdown.pack(
            anchor="w",
            padx=20,
            pady=5,
        )

        self.property_frame = ctk.CTkFrame(
            self,
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
        if action_type in ("program", "close_program"):
            return "Шлях", "path"

        elif action_type == "browser":
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
        self.current_command["action"]["type"] = value

        # Remove the previous Path/URL field
        for widget in self.property_frame.winfo_children():
            widget.destroy()

        # Display the field required by the new action type
        self.show_action_property()

        self.property_input.entry.bind(
            "<KeyRelease>",
            self.update_save_button,
            add="+",
        )

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

    def on_strings_changed(self, values):
        print("Updated strings:", values)
    
    def show_empty_settings(self):
        self.current_command = {
            "phrases": [""],
            "action": {
                "type": "program",
                "enabled": False,
                "path": "",
            },
        }

        for widget in self.winfo_children():
            widget.destroy()

        # Header — same layout as an existing command
        self.header_frame = ctk.CTkFrame(
            self,
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

        ctk.CTkButton(
            self.header_frame,
            text="Відмінити",
            width=100,
            command=self.on_cancel,
        ).pack(side="right", padx=(10, 0))

        self.save_button = ctk.CTkButton(
            self.header_frame,
            text="Зберегти",
            width=100,
            command=self.on_save,  # Use self.create_command for a new command
            state="disabled",
        )
        self.save_button.pack(side="right")

        # Voice phrases — one empty entry
        self.string_editor = PhraseListEditor(
            master=self,
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
            self,
            font=ctk.CTkFont(weight="bold"),
            text="Тип дії:",
        ).pack(anchor="w", padx=20, pady=(10, 0))

        # Action dropdown — defaults to program
        self.action_type_var = ctk.StringVar(value="program")

        self.action_type_dropdown = ctk.CTkOptionMenu(
            self,
            variable=self.action_type_var,
            values=[
                "program",
                "close_program",
                "browser",
                "close_current_tab",
                "close_jarvis",
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
            self,
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
                        "enabled": False,
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

        action_type = self.action_type_var.get()
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
        action = self.current_command["action"]
        _, property_key = self.get_action_property(action["type"])

        self.current_command["phrases"] = self.string_editor.strings

        if property_key is not None:
            action[property_key] = self.property_input.get()

        print("Saving:", self.current_command)

    def on_cancel(self):
        # Add your cancel behavior here.
        pass