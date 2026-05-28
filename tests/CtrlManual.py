import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import json
import threading
import time

BG        = "#0d0f14"
PANEL     = "#161920"
BORDER    = "#252a36"
ACCENT    = "#00e5ff"
ACCENT2   = "#ff4d6d"
ACCENT3   = "#a3e635"
TEXT      = "#e8eaf0"
TEXT_DIM  = "#555d72"
SLIDER_TR = "#1e2330"

FONT_MONO  = ("Courier New", 10)
FONT_LABEL = ("Courier New", 9, "bold")
FONT_TITLE = ("Courier New", 13, "bold")
FONT_VAL   = ("Courier New", 11, "bold")
FONT_LOG   = ("Courier New", 8)


class ArduinoController(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ARDUINO CONTROLLER")
        self.configure(bg=BG)
        self.resizable(False, False)

        self.ser         = None
        self.connected   = False
        self.read_thread = None

        self.sv_var        = tk.BooleanVar(value=False)
        self.stop_var      = tk.BooleanVar(value=False)
        self.deviation_var = tk.BooleanVar(value=False)
        self.sg_var        = tk.BooleanVar(value=True)
        self.servo_var     = tk.IntVar(value=90)
        self.pwm_var       = tk.IntVar(value=0)

        self._build_ui()
        self._refresh_ports()

    def _build_ui(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=20, pady=(18, 0))

        tk.Label(header, text="◈ ARDUINO CONTROLLER", font=FONT_TITLE,
                 fg=ACCENT, bg=BG).pack(side="left")

        self.status_dot = tk.Label(header, text="●", font=("Courier New", 14),
                                   fg=ACCENT2, bg=BG)
        self.status_dot.pack(side="right", padx=(0, 4))
        self.status_lbl = tk.Label(header, text="DISCONNECTED",
                                   font=FONT_LABEL, fg=ACCENT2, bg=BG)
        self.status_lbl.pack(side="right")

        self._sep()

        # ── Conexão ─────────────────────────
        conn = self._panel("CONEXÃO SERIAL")
        row  = tk.Frame(conn, bg=PANEL)
        row.pack(fill="x", pady=(0, 8))

        tk.Label(row, text="PORTA", font=FONT_LABEL, fg=TEXT_DIM, bg=PANEL,
                 width=7, anchor="w").pack(side="left")
        self.port_cb = ttk.Combobox(row, state="readonly", width=14, font=FONT_MONO)
        self.port_cb.pack(side="left", padx=(0, 8))

        tk.Label(row, text="BAUD", font=FONT_LABEL, fg=TEXT_DIM, bg=PANEL,
                 width=5, anchor="w").pack(side="left")
        self.baud_cb = ttk.Combobox(row, state="readonly", width=9,
                                    font=FONT_MONO,
                                    values=["9600","19200","38400","57600","115200"])
        self.baud_cb.set("9600")
        self.baud_cb.pack(side="left", padx=(0, 8))

        self._btn(row, "↺", self._refresh_ports, TEXT_DIM).pack(side="left", padx=(0, 6))
        self.conn_btn = self._btn(row, "CONECTAR", self._toggle_connect, ACCENT)
        self.conn_btn.pack(side="left")

        # ── Flags ───────────────────────────
        flags_panel = self._panel("FLAGS DE CONTROLE")
        flags_row   = tk.Frame(flags_panel, bg=PANEL)
        flags_row.pack(fill="x")

        for name, var, color in [
            ("STOP",      self.stop_var,      ACCENT2),
            ("DEVIATION", self.deviation_var, "#f59e0b"),
            ("SV",        self.sv_var,        ACCENT),
            ("SG",        self.sg_var,        ACCENT3),
        ]:
            self._toggle_flag(flags_row, name, var, color).pack(side="left", padx=(0, 10))

        # ── Servo ───────────────────────────
        self._slider_row(self._panel("SERVO (graus)"),
                         "SERVO", self.servo_var, 0, 180, ACCENT, unit="°")

        # ── PWM ─────────────────────────────
        pwm_panel = self._panel("PWM  [ -255 → 255 ]")
        pwm_row   = tk.Frame(pwm_panel, bg=PANEL)
        pwm_row.pack(fill="x", pady=3)

        tk.Label(pwm_row, text="PWM", font=FONT_LABEL, fg="#f59e0b",
                 bg=PANEL, width=6, anchor="w").pack(side="left")

        self._pwm_val_lbl = tk.Label(pwm_row, text="    0",
                                     font=FONT_VAL, fg=TEXT_DIM, bg=PANEL, width=7)
        self._pwm_val_lbl.pack(side="left", padx=(0, 8))

        def on_pwm(v):
            iv = int(float(v))
            self._pwm_val_lbl.configure(
                text=f"{iv:>5}",
                fg=ACCENT2 if iv < 0 else (TEXT_DIM if iv == 0 else ACCENT3)
            )

        tk.Scale(pwm_row, from_=-255, to=255, orient="horizontal",
                 variable=self.pwm_var, length=300, showvalue=False,
                 bg=PANEL, fg="#f59e0b", troughcolor=SLIDER_TR,
                 activebackground="#f59e0b", highlightthickness=0,
                 bd=0, sliderrelief="flat", sliderlength=16,
                 command=on_pwm).pack(side="left")

        def zero_pwm():
            self.pwm_var.set(0)
            self._pwm_val_lbl.configure(text="    0", fg=TEXT_DIM)

        self._btn(pwm_row, "0", zero_pwm, TEXT_DIM).pack(side="left", padx=(8, 0))

        # ── Ações ───────────────────────────
        self._sep()
        actions = tk.Frame(self, bg=BG)
        actions.pack(fill="x", padx=20, pady=(0, 4))

        self._btn(actions, "⬛  STOP EMERGÊNCIA",
                  self._emergency_stop, ACCENT2, big=True).pack(side="left", padx=(0, 10))
        self._btn(actions, "↺  ZERAR PWM",
                  zero_pwm, TEXT_DIM, big=True).pack(side="left", padx=(0, 10))
        self._btn(actions, "▶  ENVIAR JSON",
                  self._send, ACCENT, big=True).pack(side="left", padx=(0, 10))

        send_loop_row = tk.Frame(actions, bg=BG)
        send_loop_row.pack(side="left")

        self.loop_btn = self._btn(send_loop_row, "⟳  AUTO-ENVIO",
                                  self._toggle_loop, ACCENT3, big=True)
        self.loop_btn.pack(side="left", padx=(0, 6))

        tk.Label(send_loop_row, text="ms", font=FONT_LABEL, fg=TEXT_DIM, bg=BG).pack(side="right")
        self.interval_entry = tk.Entry(send_loop_row, width=5, font=FONT_MONO,
                                       bg=PANEL, fg=TEXT, insertbackground=TEXT,
                                       relief="flat", bd=0, highlightthickness=1,
                                       highlightcolor=BORDER, highlightbackground=BORDER)
        self.interval_entry.insert(0, "500")
        self.interval_entry.pack(side="right", padx=(0, 4))
        tk.Label(send_loop_row, text="intervalo:", font=FONT_LABEL,
                 fg=TEXT_DIM, bg=BG).pack(side="right", padx=(6, 0))

        self._loop_running = False
        self._loop_thread  = None

        # ── Log ─────────────────────────────
        self._sep()
        log_panel = self._panel("LOG SERIAL", pad_bottom=10)

        self.log_text = tk.Text(log_panel, height=8, width=80,
                                font=FONT_LOG, bg="#0a0c10", fg=ACCENT3,
                                insertbackground=TEXT, relief="flat",
                                state="disabled", bd=0, highlightthickness=0)
        self.log_text.pack(fill="both")

        sb = tk.Scrollbar(log_panel, command=self.log_text.yview, bg=PANEL,
                          troughcolor=PANEL, activebackground=ACCENT)
        sb.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=sb.set)

        self.log_text.tag_config("sent",     foreground=ACCENT)
        self.log_text.tag_config("received", foreground=ACCENT3)
        self.log_text.tag_config("error",    foreground=ACCENT2)
        self.log_text.tag_config("info",     foreground="#a78bfa")

        self._btn(log_panel, "LIMPAR LOG", self._clear_log,
                  TEXT_DIM).pack(anchor="e", pady=(4, 0))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox",
                        fieldbackground=PANEL, background=PANEL,
                        foreground=TEXT, selectbackground=BORDER,
                        selectforeground=TEXT, bordercolor=BORDER,
                        arrowcolor=ACCENT)
        style.map("TCombobox",
                  fieldbackground=[("readonly", PANEL)],
                  background=[("readonly", PANEL)])

    # ──────────────────────────────────────────
    def _sep(self):
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=20, pady=10)

    def _panel(self, title, pad_bottom=6):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="x", padx=20, pady=(0, pad_bottom))
        tk.Label(outer, text=title, font=FONT_LABEL, fg=TEXT_DIM,
                 bg=BG).pack(anchor="w", pady=(0, 4))
        inner = tk.Frame(outer, bg=PANEL, padx=12, pady=10,
                         highlightthickness=1, highlightbackground=BORDER)
        inner.pack(fill="x")
        return inner

    def _btn(self, parent, text, cmd, color, big=False):
        padx = (12, 12) if big else (8, 8)
        pady = (6, 6)   if big else (4, 4)
        b = tk.Button(parent, text=text, font=FONT_LABEL,
                      fg=BG, bg=color, activebackground=color,
                      activeforeground=BG, relief="flat", bd=0,
                      cursor="hand2", command=cmd,
                      padx=padx[0], pady=pady[0])
        b.bind("<Enter>", lambda e: b.configure(bg=self._lighten(color)))
        b.bind("<Leave>", lambda e: b.configure(bg=color))
        return b

    def _lighten(self, hex_color):
        try:
            r = min(255, int(hex_color[1:3], 16) + 30)
            g = min(255, int(hex_color[3:5], 16) + 30)
            b = min(255, int(hex_color[5:7], 16) + 30)
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return hex_color

    def _toggle_flag(self, parent, name, var, color):
        frame = tk.Frame(parent, bg=PANEL)

        def refresh(*_):
            state = var.get()
            lbl.configure(fg=color if state else TEXT_DIM)
            dot.configure(fg=color if state else TEXT_DIM)

        dot = tk.Label(frame, text="●", font=("Courier New", 10),
                       fg=TEXT_DIM, bg=PANEL)
        dot.pack(side="left")
        lbl = tk.Label(frame, text=name, font=FONT_LABEL,
                       fg=TEXT_DIM, bg=PANEL, cursor="hand2")
        lbl.pack(side="left", padx=(3, 0))

        def toggle(_=None):
            var.set(not var.get())
            refresh()

        dot.bind("<Button-1>", toggle)
        lbl.bind("<Button-1>", toggle)
        var.trace_add("write", refresh)
        return frame

    def _slider_row(self, parent, label, var, mn, mx, color, unit=""):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=3)

        tk.Label(row, text=label, font=FONT_LABEL, fg=color,
                 bg=PANEL, width=6, anchor="w").pack(side="left")

        val_lbl = tk.Label(row, text=f"{var.get():>5}{unit}",
                           font=FONT_VAL, fg=TEXT, bg=PANEL, width=7)
        val_lbl.pack(side="left", padx=(0, 8))

        def on_change(v):
            val_lbl.configure(text=f"{int(float(v)):>5}{unit}")

        tk.Scale(row, from_=mn, to=mx, orient="horizontal",
                 variable=var, length=300, showvalue=False,
                 bg=PANEL, fg=color, troughcolor=SLIDER_TR,
                 activebackground=color, highlightthickness=0,
                 bd=0, sliderrelief="flat", sliderlength=16,
                 command=on_change).pack(side="left")

        return val_lbl

    # ──────────────────────────────────────────
    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_cb["values"] = ports
        self.port_cb.set(ports[0] if ports else "")

    def _toggle_connect(self):
        self._disconnect() if self.connected else self._connect()

    def _connect(self):
        port = self.port_cb.get()
        baud = int(self.baud_cb.get())
        if not port:
            messagebox.showerror("Erro", "Selecione uma porta serial.")
            return
        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            time.sleep(2)
            self.connected = True
            self._set_status(True)
            self.conn_btn.configure(text="DESCONECTAR", bg=ACCENT2)
            self._log(f"Conectado em {port} @ {baud} baud", "info")
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
        except Exception as e:
            self._log(f"Erro ao conectar: {e}", "error")
            messagebox.showerror("Erro de conexão", str(e))

    def _disconnect(self):
        self._loop_running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.connected = False
        self._set_status(False)
        self.conn_btn.configure(text="CONECTAR", bg=ACCENT)
        self._log("Desconectado.", "info")

    def _set_status(self, ok):
        color = ACCENT3 if ok else ACCENT2
        self.status_dot.configure(fg=color)
        self.status_lbl.configure(fg=color, text="CONNECTED" if ok else "DISCONNECTED")

    # ──────────────────────────────────────────
    def _build_payload(self):
        return {
            "DEVIATION": self.deviation_var.get(),
            "STOP":      self.stop_var.get(),
            "SG":        self.sg_var.get(),
            "SV":        self.sv_var.get(),
            "SERVO":     self.servo_var.get(),
            "PWM":       self.pwm_var.get(),
        }

    def _send(self):
        if not self.connected:
            self._log("Não conectado.", "error")
            return
        payload = json.dumps(self._build_payload()) + "\n"
        try:
            self.ser.write(payload.encode("utf-8"))
            self._log(f"TX → {payload.strip()}", "sent")
        except Exception as e:
            self._log(f"Erro ao enviar: {e}", "error")

    def _emergency_stop(self):
        self.stop_var.set(True)
        self.pwm_var.set(0)
        self._pwm_val_lbl.configure(text="    0", fg=TEXT_DIM)
        self._send()

    def _toggle_loop(self):
        if self._loop_running:
            self._loop_running = False
            self.loop_btn.configure(text="⟳  AUTO-ENVIO", bg=ACCENT3)
        else:
            try:
                ms = int(self.interval_entry.get())
            except ValueError:
                ms = 500
            self._loop_running = True
            self.loop_btn.configure(text="■  PARAR", bg=ACCENT2)
            self._loop_thread = threading.Thread(
                target=self._auto_send_loop, args=(ms / 1000,), daemon=True)
            self._loop_thread.start()

    def _auto_send_loop(self, interval):
        while self._loop_running:
            self._send()
            time.sleep(interval)

    def _read_loop(self):
        while self.connected and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        self.after(0, self._log, f"RX ← {line}", "received")
            except:
                break

    # ──────────────────────────────────────────
    def _log(self, msg, tag="info"):
        ts = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{ts}] {msg}\n", tag)
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def on_close(self):
        self._loop_running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.destroy()


if __name__ == "__main__":
    app = ArduinoController()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()