
import logging
import queue
import customtkinter as ctk
from datetime import datetime

class QueueLogHandler(logging.Handler):
    """Send formatted log records to a thread-safe queue."""

    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            timestamp = datetime.fromtimestamp(
                record.created
            ).strftime("%d-%m-%Y %H:%M:%S")

            self.log_queue.put(
                (timestamp, record.levelname, record.getMessage())
            )
        except Exception:
            self.handleError(record)

class LogConsole(ctk.CTkFrame):
    COLORS = {
        "DEBUG":    "#60A5FA",  # Blue
        "INFO":     "#4ADE80",  # Green
        "WARNING":  "#FBBF24",  # Yellow
        "ERROR":    "#F87171",  # Red
        "CRITICAL": "#C084FC",  # Purple
    }

    def __init__(self, master, logger, **kwargs):
        super().__init__(master, **kwargs)

        self.logger = logger
        self.log_queue = queue.Queue()
        self._destroyed = False
        self._after_id = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=10,
            pady=(10, 5),
        )

        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Логи",
            font=ctk.CTkFont(
                family="Arial",
                size=16,
                weight="bold",
            ),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header,
            text="Очистити",
            width=70,
            height=28,
            command=self.clear,
        ).grid(row=0, column=1, padx=(5, 0))

        # Terminal output
        self.textbox = ctk.CTkTextbox(
            self,
            fg_color="#111827",
            text_color="#E5E7EB",
            font=ctk.CTkFont(
                family="Consolas",
                size=16 ,
            ),
            wrap="none",
            activate_scrollbars=True,
            corner_radius=8,
        )

        self.textbox.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=10,
            pady=(0, 10),
        )

        # Configure colors for each logging level
        for level, color in self.COLORS.items():
            self.textbox.tag_config(
                level,
                foreground=color,
            )

        self.textbox.tag_config(
            "timestamp",
            foreground="#9CA3AF",
        )
        
        self.textbox.tag_config(
            "message",
            foreground="#E5E7EB",
        )

        self.textbox.configure(state="disabled")

        # Connect this console to the existing logger
        self.handler = QueueLogHandler(self.log_queue)
        self.handler.setLevel(logging.DEBUG)
        self.handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(message)s",
                datefmt="%d-%m-%Y %H:%M:%S",
            )
        )

        self.logger.addHandler(self.handler)

        # Start reading queued records on Tkinter's main thread
        self._poll_logs()

    def _poll_logs(self):
        if self._destroyed:
            return

        try:
            self.textbox.configure(state="normal")

            was_at_bottom = (
                self.textbox.yview()[1] >= 0.999
            )

            # Process a batch instead of updating the UI
            # separately for every individual log record.
            while True:
                try:
                    timestamp, level, message = (
                        self.log_queue.get_nowait()  
                    )                  
                except queue.Empty:
                    break

                self.textbox.insert("end", f"[{level}] ", (level,))
                self.textbox.insert("end", f"{timestamp} ", ("timestamp",))
                self.textbox.insert("end", message + "\n", ("message",))

            if was_at_bottom:
                self.textbox.see("end")

        finally:
            if not self._destroyed:
                self.textbox.configure(state="disabled")
                self._after_id = self.after(100, self._poll_logs)

    def clear(self):
        """Clear displayed messages without deleting log files."""
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")

    def destroy(self):
        """Detach the handler when the console is destroyed."""
        self._destroyed = True

        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass

        self.logger.removeHandler(self.handler)
        self.handler.close()

        super().destroy()
