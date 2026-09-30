import os
import tkinter as tk
import webbrowser
from threading import Thread
from tkinter import messagebox

from werkzeug.serving import BaseWSGIServer, make_server

from server import app, initialize


INK = "#10120f"
SURFACE = "#181c16"
PAPER = "#f3f1e9"
LIME = "#c6f36a"
MUTED = "#a4a99b"


class ControlPanel:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.server: BaseWSGIServer | None = None
        self.host = os.environ.get("HOST", "127.0.0.1")
        self.port = int(os.environ.get("PORT", "8000"))
        self.url = f"http://127.0.0.1:{self.port}"
        self.state_label: tk.Label
        self.detail_label: tk.Label
        self.start_button: tk.Button
        self.pause_button: tk.Button
        self.resume_button: tk.Button
        self.stop_button: tk.Button
        self.open_button: tk.Button

        self.root.title("Homi / Server Control")
        self.root.geometry("520x430")
        self.root.minsize(460, 400)
        self.root.configure(bg=INK)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.build_ui()

        try:
            initialize()
            self.start()
        except Exception as error:
            self.set_status("SETUP ERROR", str(error), "#ff9d84")
            self.start_button.configure(state="disabled")

    def build_ui(self) -> None:
        header = tk.Frame(self.root, bg=INK, padx=28, pady=24)
        header.pack(fill="x")
        tk.Label(header, text="P+", bg=LIME, fg=INK, width=3, height=1, font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(header, text="HOMI / SERVER CONTROL", bg=INK, fg=PAPER, font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(17, 3))
        tk.Label(header, text="LOCAL WEBSITE PROCESS", bg=INK, fg=MUTED, font=("Consolas", 9)).pack(anchor="w")

        status = tk.Frame(self.root, bg=SURFACE, padx=19, pady=17, highlightbackground="#34392e", highlightthickness=1)
        status.pack(fill="x", padx=28, pady=(3, 18))
        status_top = tk.Frame(status, bg=SURFACE)
        status_top.pack(fill="x")
        tk.Label(status_top, text="STATUS", bg=SURFACE, fg=MUTED, font=("Consolas", 9)).pack(side="left")
        self.state_label = tk.Label(status_top, text="STARTING", bg=SURFACE, fg=LIME, font=("Consolas", 10, "bold"))
        self.state_label.pack(side="right")
        tk.Label(status, text=self.url, bg=SURFACE, fg=PAPER, font=("Consolas", 10)).pack(anchor="w", pady=(12, 3))
        self.detail_label = tk.Label(status, text="", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9), wraplength=420, justify="left", anchor="w")
        self.detail_label.pack(fill="x", pady=(3, 0))

        controls = tk.Frame(self.root, bg=INK, padx=28)
        controls.pack(fill="x")
        row = tk.Frame(controls, bg=INK)
        row.pack(fill="x")
        self.start_button = self.make_button(row, "START", LIME, INK, self.start, side="left", expand=True)
        self.pause_button = self.make_button(row, "PAUSE", "#292e24", PAPER, self.pause, side="left", expand=True)
        self.resume_button = self.make_button(row, "RESUME", "#292e24", PAPER, self.resume, side="left", expand=True)
        self.stop_button = self.make_button(row, "STOP", "#4a2b25", "#ffb09a", self.stop, side="left", expand=True)
        self.open_button = self.make_button(controls, "OPEN WEBSITE  ↗", "#242820", PAPER, self.open_site, side="top", expand=False)
        self.open_button.pack(fill="x", pady=(11, 0))

        tk.Label(self.root, text="The public site cannot control this window.", bg=INK, fg=MUTED, font=("Segoe UI", 9)).pack(side="bottom", pady=19)
        self.update_controls()

    def make_button(self, parent: tk.Widget, text: str, bg: str, fg: str, command, side: str, expand: bool) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=LIME,
            activeforeground=INK,
            disabledforeground="#777b70",
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            font=("Consolas", 9, "bold"),
            padx=10,
            pady=12,
        )
        if side == "left":
            button.pack(side=side, expand=expand, fill="x", padx=(0, 7))
        return button

    def set_status(self, title: str, detail: str, color: str) -> None:
        self.state_label.configure(text=title, fg=color)
        self.detail_label.configure(text=detail)
        self.update_controls()

    def update_controls(self) -> None:
        running = self.server is not None
        paused = running and bool(getattr(self.server, "paused", False))
        self.start_button.configure(state="disabled" if running else "normal")
        self.pause_button.configure(state="normal" if running and not paused else "disabled")
        self.resume_button.configure(state="normal" if paused else "disabled")
        self.stop_button.configure(state="normal" if running else "disabled")
        self.open_button.configure(state="normal" if running else "disabled")

    def start(self) -> None:
        if self.server is not None:
            return
        try:
            app.config["SITE_PAUSED"] = False
            server = make_server(self.host, self.port, app, threaded=True)
            server.paused = False
            thread = Thread(target=server.serve_forever, name="HomiSiteServer", daemon=True)
            thread.start()
            self.server = server
            self.set_status("RUNNING", "The website is live on this computer.", LIME)
        except OSError as error:
            self.set_status("START FAILED", f"{error}. Stop any other server using this port, then try again.", "#ff9d84")

    def pause(self) -> None:
        if self.server is not None:
            self.server.paused = True
            app.config["SITE_PAUSED"] = True
            self.set_status("PAUSED", "Requests receive a pause notice until you resume the site.", "#ffd27a")

    def resume(self) -> None:
        if self.server is not None:
            self.server.paused = False
            app.config["SITE_PAUSED"] = False
            self.set_status("RUNNING", "The website is live on this computer.", LIME)

    def stop(self) -> None:
        server = self.server
        if server is None:
            return
        self.server = None
        app.config["SITE_PAUSED"] = False
        server.shutdown()
        server.server_close()
        self.set_status("STOPPED", "Server stopped. Your site files and saved content are unchanged.", LIME)

    def open_site(self) -> None:
        webbrowser.open(self.url)

    def close(self) -> None:
        self.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    ControlPanel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
