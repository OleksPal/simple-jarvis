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
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.title_label.pack(fill="x")

        self.description_label = ctk.CTkLabel(
            self.text_frame,
            text=description,
            anchor="w",
            text_color="gray",
            font=ctk.CTkFont(size=11),
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

        # Click on the row or text to select it
        for widget in (
            self,
            self.text_frame,
            self.title_label,
            self.description_label,
        ):
            widget.bind("<Button-1>", self._on_select)

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
        self.configure(
            fg_color="#263B60" if selected else "transparent"
        )

    def set_enabled(self, enabled: bool):
        if enabled:
            self.switch.select()
        else:
            self.switch.deselect()
