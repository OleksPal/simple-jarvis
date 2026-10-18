import customtkinter as ctk
from underlined_entry import UnderlinedEntry

class PhraseListEditor(ctk.CTkFrame):
    def __init__(self, master, values=None, on_change=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_change = on_change

        # This list stays synchronized with all user changes.
        self.strings = list(values or [])
        self.entries = []

        ctk.CTkLabel(
            self,
            text="Фрази:",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", pady=(15, 5))

        self.rows_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.rows_frame.pack(fill="x", expand=True)

        self.add_button = ctk.CTkButton(
            self,
            text="+ Додати фразу",
            command=self.add_string,
        )
        self.add_button.pack(anchor="w", pady=(5, 0))

        for value in self.strings:
            self._create_row(value)

    def _create_row(self, value=""):
        row = ctk.CTkFrame(
            self.rows_frame,
            fg_color="transparent",
        )
        row.pack(fill="x", pady=5)

        entry = UnderlinedEntry(
            row,
            value=value,
            font_size=14,
        )
        entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 15)
        )

        # Update the in-memory list whenever the user types.
        entry.entry.bind(
            "<KeyRelease>",
            lambda event: self._sync_strings(),
        )

        delete_button = ctk.CTkButton(
            row,
            text="Видалити",
            width=60,
            command=lambda: self.delete_string(row),
        )
        delete_button.pack(side="right")

        self.entries.append((row, entry))

    def _sync_strings(self):
        """Synchronize the in-memory list with the input fields."""
        self.strings = [
            entry.get()
            for _, entry in self.entries
        ]

        if self.on_change:
            self.on_change()

    def add_string(self):
        """Add an empty input and immediately update the list."""
        self._create_row("")
        self._sync_strings()

    def delete_string(self, row):
        """Delete an input and immediately update the list."""
        for item in self.entries:
            if item[0] == row:
                self.entries.remove(item)
                break

        row.destroy()
        self._sync_strings()

    def set_strings(self, values):
        """Replace all strings and rebuild the inputs."""
        for row, _ in self.entries:
            row.destroy()

        self.entries.clear()
        self.strings = list(values)

        for value in self.strings:
            self._create_row(value)

        self._sync_strings()