import customtkinter as ctk

class CommandRow(ctk.CTkFrame):
    def __init__(
        self,
        master,
        name: str,
        description: str,
        enabled: bool = False,
        on_select=None,
        on_toggle=None,
        **kwargs,
    ):
        super().__init__(
            master,
            corner_radius=8,
            fg_color="transparent",
            **kwargs,
        )

        self.name = name
        self.on_select = on_select
        self.on_toggle = on_toggle

        self.is_selected = False
        self.default_color = "transparent"
        self.hover_color = ("gray85", "gray25")
        self.selected_color = ("#D5E3FA", "#263B60")

        self.grid_columnconfigure(0, weight=1)

        # Text container
        self.text_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.text_frame.grid(
            row=0, column=0, sticky="nsew",
            padx=10, pady=3,
        )

        self.title_label = ctk.CTkLabel(
            self.text_frame,
            text=name,
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.title_label.pack(fill="x")

        self.description_label = ctk.CTkLabel(
            self.text_frame,
            text=description,
            anchor="w",
            text_color="gray75",
            font=ctk.CTkFont(size=12),
        )
        self.description_label.pack(fill="x")

        # Switch
        self.switch = ctk.CTkSwitch(
            self,
            text="",
            width=42,
            command=self._on_toggle,
        )
        self.switch.grid(
            row=0, column=1, padx=12,
        )

        if enabled:
            self.switch.select()
        else:
            self.switch.deselect()

        # Clicking the row or its text selects the command.
        for widget in (
            self,
            self.text_frame,
            self.title_label,
            self.description_label,
        ):
            widget.bind("<Button-1>", self._on_select)
            widget.bind("<Enter>", self._on_hover)
            widget.bind("<Leave>", self._on_leave)
            widget.configure(cursor="hand2")

    def _on_select(self, event=None):
        if self.on_select:
            self.on_select(self.name)

    def _on_toggle(self):
        if self.on_toggle:
            self.on_toggle(
                self.name,
                bool(self.switch.get()),
            )

    def set_selected(self, selected: bool):
        self.is_selected = selected

        self.configure(
            fg_color=(
                self.selected_color
                if selected
                else self.default_color
            )
        )

    def set_enabled(self, enabled: bool):
        if enabled:
            self.switch.select()
        else:
            self.switch.deselect()

    def _on_hover(self, event=None):
        if not self.is_selected:
            self.configure(fg_color=self.hover_color)

    def _on_leave(self, event=None):
        if not self.is_selected:
            self.configure(fg_color=self.default_color)

    def update_content(self, name: str, description: str):
        self.name = name

        self.title_label.configure(text=name)
        self.description_label.configure(text=description)
