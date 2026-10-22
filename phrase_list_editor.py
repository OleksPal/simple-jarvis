import customtkinter as ctk
from ctkfontawesome import icon_to_ctkimage
from underlined_entry import UnderlinedEntry

add_icon = icon_to_ctkimage(
    "plus",
    fill="#FFFFFF",
    scale_to_width=14
)

microphone_icon = icon_to_ctkimage(
    "microphone",
    fill="white",
    scale_to_width=12
)

circle_minus_icon = icon_to_ctkimage(
    "circle-minus",
    fill="white",
    scale_to_width=12
)

class PhraseListEditor(ctk.CTkFrame):
    def __init__(self, master, values=None, on_change=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_change = on_change

        # This list stays synchronized with all user changes.
        self.strings = list(values or [])
        self.entries = []

        ctk.CTkLabel(
            self,
            text=" Фрази:",
            font=ctk.CTkFont(weight="bold", size=14),
            image=microphone_icon,
            compound="left",
        ).pack(anchor="w", pady=(15, 5))

        self.rows_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.rows_frame.pack(fill="x", expand=True)

        self.add_button = ctk.CTkButton(
            self,
            image=add_icon,
            text="Додати фразу",
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

        # Synchronize whenever the underlying StringVar changes.
        entry.variable.trace_add(
            "write",
            lambda *_: self._sync_strings(),
        )

        delete_button = ctk.CTkButton(
            row,
            text="",
            fg_color="#C62828",
            hover_color="#E53935",
            image=circle_minus_icon,
            width=28,
            height=28,
            command=lambda: self.delete_string(row),
        )
        delete_button.pack(
            side="right"
        )

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
        self.entries = [
            item for item in self.entries
            if item[0] != row
        ]

        row.destroy()
        self._sync_strings()

    def set_strings(self, values):
        """Replace all strings and rebuild the inputs."""
        for row, _ in self.entries:
            row.destroy()

        self.entries.clear()
        self.strings = [
            str(value) if value is not None else ""
            for value in (values or [])
        ]

        for value in self.strings:
            self._create_row(value)

        self._sync_strings()