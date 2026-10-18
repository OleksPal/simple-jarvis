
import customtkinter as ctk


class UnderlinedEntry(ctk.CTkFrame):
    def __init__(
        self,
        master,
        value="",
        font_size=22,
        underline_color="#808080",
        active_color="#8ab4f8",
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs,
        )

        self.active_color = active_color
        self.underline_color = underline_color

        self.grid_columnconfigure(0, weight=1)

        self.variable = ctk.StringVar(value=value)

        self.entry = ctk.CTkEntry(
            self,
            textvariable=self.variable,
            font=ctk.CTkFont(size=font_size, weight="bold"),
            fg_color="transparent",
            border_width=0,
            corner_radius=0,
        )
        self.entry.grid(row=0, column=0, sticky="ew")

        self.underline = ctk.CTkFrame(
            self,
            height=2,
            fg_color=underline_color,
            corner_radius=0,
        )
        self.underline.grid(
            row=1, column=0, sticky="ew", pady=(2, 0)
        )

        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_in(self, event=None):
        self.underline.configure(fg_color=self.active_color)

    def _on_focus_out(self, event=None):
        self.underline.configure(fg_color=self.underline_color)

    def get(self):
        return self.variable.get().strip()

    def set(self, value):
        self.variable.set(value)

    def focus(self):
        self.entry.focus_set()
