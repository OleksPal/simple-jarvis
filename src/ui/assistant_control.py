
import customtkinter as ctk


class AssistantControl(ctk.CTkFrame):
    STATUS_CONFIG = {
        "Stopped": ("#9CA3AF", "Start", "#16A34A"),
        "Initializing...": ("#60A5FA", "Starting...", "#374151"),
        "Listening": ("#4ADE80", "Stop", "#DC2626"),
        "Processing": ("#60A5FA", "Stop", "#DC2626"),
        "Speaking": ("#C084FC", "Stop", "#DC2626"),
        "Stopping...": ("#FBBF24", "Stopping...", "#374151"),
        "Error": ("#F87171", "Retry", "#16A34A"),
    }

    BUSY_STATES = {
        "Initializing...",
        "Stopping...",
    }

    def __init__(
        self,
        master,
        on_start,
        on_stop,
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color="#1E1E1E",
            corner_radius=16,
            border_width=1,
            border_color="#4B5563",
            **kwargs,
        )

        self.on_start = on_start
        self.on_stop = on_stop
        self.status = "Stopped"

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # Left side: title and status stacked vertically.
        info_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        info_frame.grid(
            row=0,
            column=0,
            sticky="w",
            padx=(16, 10),
            pady=14,
        )

        ctk.CTkLabel(
            info_frame,
            text="Jarvis",
            font=ctk.CTkFont(
                family="Arial",
                size=18,
                weight="bold",
            ),
        ).pack(anchor="w")

        status_frame = ctk.CTkFrame(
            info_frame,
            fg_color="transparent",
        )
        status_frame.pack(anchor="w", pady=(3, 0))

        self.status_dot = ctk.CTkLabel(
            status_frame,
            text="●",
            font=ctk.CTkFont(size=12),
        )
        self.status_dot.pack(side="left", padx=(0, 5))

        self.status_label = ctk.CTkLabel(
            status_frame,
            text=self.status,
            font=ctk.CTkFont(size=13),
        )
        self.status_label.pack(side="left")

        # Right side: compact Start/Stop button.
        self.control_button = ctk.CTkButton(
            self,
            text="Start",
            width=85,
            height=32,
            font=ctk.CTkFont(
                family="Arial",
                size=13,
                weight="bold",
            ),
            command=self._toggle,
        )
        self.control_button.grid(
            row=0,
            column=1,
            sticky="e",
            padx=(10, 16),
            pady=14,
        )

        self.set_status("Stopped")

    def set_status(self, status):
        if status not in self.STATUS_CONFIG:
            raise ValueError(f"Unknown status: {status}")

        self.status = status
        color, button_text, button_color = (
            self.STATUS_CONFIG[status]
        )

        self.status_dot.configure(text_color=color)
        self.status_label.configure(
            text=status,
            text_color=color,
        )

        busy = status in {"Initializing...", "Stopping..."}

        self.control_button.configure(
            text=button_text,
            state="disabled" if busy else "normal",
            fg_color=button_color,
            hover_color=(
                button_color if busy else
                "#15803D" if status in {"Stopped", "Error"} else
                "#B91C1C"
            ),
        )

    def _toggle(self):
        if self.status in {"Initializing...", "Stopping..."}:
            return

        if self.status in {"Stopped", "Error"}:
            self.set_status("Initializing...")
            self.on_start()
        else:
            self.set_status("Stopping...")
            self.on_stop()