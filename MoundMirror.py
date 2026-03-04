import cv2
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, Menu
from PIL import Image, ImageTk
from collections import deque
from datetime import datetime
import os
import json

from threaded_camera import ThreadedCamera

class MoundMirrorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mound Mirror - Catcher POV")
        self.root.geometry("1000x700")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- CONFIGURATION DEFAULTS ---
        self.load_config()
        self.is_recording = False
        self.is_replay_mode = False
        self.fps = 30.0

        # --- VIDEO STATE ---
        self.cap = None
        self.running = False
        self.delay_buffer = deque()
        self.replay_buffer = deque()
        self.writer = None
        self.temp_filename = "temp_rec.mp4"
        self.frame_lock = threading.Lock()

        # --- SHARED THREAD VARIABLES ---
        self.latest_frame = None
        self.current_image_ref = None
        self.thread_message = None  # Safe way to pass errors to the UI

        # --- GUI SETUP ---
        self.create_menu()
        self.create_main_layout()

        # Let the UI draw completely before starting the camera
        self.root.after(1000, self.start_camera_thread)
        self.root.after(100, self.update_ui_loop)

    def create_menu(self):
        menubar = Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save Recording...", command=self.save_recording)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        settings_menu = Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Preferences...", command=self.open_preferences)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        view_menu = Menu(menubar, tearoff=0)
        view_menu.add_checkbutton(label="Fullscreen (F)", command=self.toggle_fullscreen)
        menubar.add_cascade(label="View", menu=view_menu)

    def create_main_layout(self):
        # Pack controls first to prevent fullscreen push-off
        self.controls_frame = tk.Frame(self.root, bg="#333", height=60)
        self.controls_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.video_frame = tk.Frame(self.root, bg="black")
        self.video_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.video_label = tk.Label(self.video_frame, bg="black")
        self.video_label.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.configure("TButton", padding=6)

        self.btn_replay = ttk.Button(self.controls_frame, text="⏪ INSTANT REPLAY (Space)", command=self.trigger_replay)
        self.btn_replay.pack(side=tk.LEFT, padx=20, pady=10)

        self.btn_record = tk.Button(self.controls_frame, text="⚫ REC", bg="#444", fg="red", font=("Arial", 10, "bold"),
                                    command=self.toggle_record)
        self.btn_record.pack(side=tk.RIGHT, padx=20, pady=10)

        self.lbl_status = tk.Label(self.controls_frame, text="Ready", bg="#333", fg="white")
        self.lbl_status.pack(side=tk.LEFT, padx=10)

        self.root.bind('<space>', lambda e: self.trigger_replay(e))
        self.root.bind('<f>', lambda e: self.toggle_fullscreen())
        self.root.bind('<q>', lambda e: self.on_close())

    def start_camera_thread(self):
        if self.running:
            return

        self.lbl_status.config(text=f"Connecting to {self.camera_mode.upper()}...", fg="yellow")
        self.running = True
        self.thread = threading.Thread(target=self.video_loop, daemon=True)
        self.thread.start()

    def update_ui_loop(self):
        # 1. Thread-safe status updates
        if self.thread_message:
            if self.thread_message == "FAILED":
                self.lbl_status.config(text="Camera Connection Failed", fg="red")
            self.thread_message = None # Clear message after displaying

        # 2. Display the newest frame
        if self.latest_frame is not None:
            self.show_frame(self.latest_frame)
            
        self.root.after(15, self.update_ui_loop)

    def video_loop(self):
        self.cap = ThreadedCamera(mode=self.camera_mode, source=self.camera_source)
        success = self.cap.start()

        if not success:
            self.running = False
            self.thread_message = "FAILED" # Send message safely to UI thread
            return

        ret, frame = self.cap.read()
        while (not ret or frame is None) and self.running:
            time.sleep(0.1)
            ret, frame = self.cap.read()

        if not self.running or frame is None:
            return

        h, w = frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v') # type: ignore
        self.writer = cv2.VideoWriter(self.temp_filename, fourcc, self.fps, (w, h))

        self.update_buffer_sizes()

        while self.running:
            ret, frame = self.cap.read()

            if not ret or frame is None:
                time.sleep(0.01)
                continue

            if self.is_recording and self.writer:
                self.writer.write(frame)

            with self.frame_lock:
                self.delay_buffer.append(frame)
                self.replay_buffer.append(frame.copy())

                if not self.is_replay_mode:
                    current_maxlen = self.delay_buffer.maxlen if self.delay_buffer.maxlen is not None else 0
                    if len(self.delay_buffer) >= current_maxlen and current_maxlen > 0:
                        self.latest_frame = self.delay_buffer[0]
                    else:
                        self.latest_frame = frame

            time.sleep(1.0 / self.fps)

        self.cap.stop()
        if self.writer: self.writer.release()

    def show_frame(self, cv_frame):
        win_w = self.video_label.winfo_width()
        win_h = self.video_label.winfo_height()

        if win_w < 10 or win_h < 10: return

        h, w = cv_frame.shape[:2]
        scale = min(win_w / w, win_h / h)
        new_w, new_h = int(w * scale), int(h * scale)

        frame_rgb = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        imgtk = ImageTk.PhotoImage(image=img_resized)

        self.current_image_ref = imgtk
        self.video_label.configure(image=self.current_image_ref)

        status_text = f"DELAY: {self.delay_seconds}s"
        if self.is_recording:
            status_text += " | ⚫ RECORDING"
        
        # Don't overwrite the "Connecting..." message if we are still buffering
        if self.lbl_status.cget("text") != f"Connecting to {self.camera_mode.upper()}...":
            self.lbl_status.config(text=status_text, fg="red" if self.is_recording else "white")

    def trigger_replay(self, event=None):
        if self.is_replay_mode:
            self.is_replay_mode = False
            return
        threading.Thread(target=self.replay_worker, daemon=True).start()

    def replay_worker(self):
        self.is_replay_mode = True
        self.root.after(0, lambda: self.lbl_status.config(text="REPLAYING... (Press SPACE to Stop)", fg="yellow"))

        with self.frame_lock:
            frames = list(self.replay_buffer)

        wait_time = (1.0 / self.fps) / self.playback_speed

        for frame in frames:
            if not self.is_replay_mode:
                break

            display = frame.copy()
            cv2.putText(display, f"REPLAY ({self.playback_speed}x)", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.5,
                        (0, 255, 255), 3)

            self.latest_frame = display
            time.sleep(wait_time)

        self.is_replay_mode = False
        self.root.after(0, lambda: self.lbl_status.config(text="Ready", fg="white"))

    def toggle_record(self):
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.btn_record.config(text="🟥 STOP", fg="white", bg="red")
        else:
            self.btn_record.config(text="⚫ REC", fg="red", bg="#444")

    def open_preferences(self):
        top = tk.Toplevel(self.root)
        top.title("Preferences")
        top.geometry("450x450") 

        tk.Label(top, text="Camera Mode:").pack(pady=(10, 0))
        mode_var = tk.StringVar(value=self.camera_mode)
        mode_cb = ttk.Combobox(top, textvariable=mode_var, values=["wired", "ip", "gopro"], state="readonly")
        mode_cb.pack(pady=5)

        source_label = tk.Label(top, text="Camera Source:")
        source_label.pack(pady=(5, 0))
        source_var = tk.StringVar(value=str(self.camera_source))
        source_entry = tk.Entry(top, textvariable=source_var, width=50)

        def update_ui(event=None):
            m = mode_var.get()
            if m == "gopro":
                source_label.config(text="GoPro selected (Auto-connects to HERO11 Black over Wi-Fi)")
                source_entry.pack_forget()
            elif m == "wired":
                source_label.config(text="Wired Camera ID (usually 0, 1, or 2):")
                source_entry.pack(pady=5, padx=20)
            else:
                source_label.config(text="IP Camera URL (e.g., http://192.168...):")
                source_entry.pack(pady=5, padx=20)

        mode_cb.bind("<<ComboboxSelected>>", update_ui)
        update_ui()

        tk.Label(top, text="Delay (Seconds)").pack(pady=(15, 5))
        delay_var = tk.DoubleVar(value=self.delay_seconds)
        tk.Scale(top, variable=delay_var, from_=1, to=20, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20)

        tk.Label(top, text="Replay Speed (0.1x - 1.0x)").pack(pady=5)
        speed_var = tk.DoubleVar(value=self.playback_speed)
        tk.Scale(top, variable=speed_var, from_=0.1, to=1.0, resolution=0.1, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20)

        tk.Label(top, text="Replay History (Seconds)").pack(pady=5)
        hist_var = tk.DoubleVar(value=self.replay_seconds)
        tk.Scale(top, variable=hist_var, from_=5, to=30, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20)

        def apply():
            old_mode = self.camera_mode
            old_source = self.camera_source

            self.camera_mode = mode_var.get()
            self.camera_source = source_var.get()
            self.delay_seconds = delay_var.get()
            self.playback_speed = speed_var.get()
            self.replay_seconds = hist_var.get()

            self.update_buffer_sizes()
            self.save_config()

            if old_mode != self.camera_mode or old_source != self.camera_source:
                # Stop the current thread and start a fresh one
                self.running = False
                self.root.after(500, self.start_camera_thread)

            top.destroy()

        ttk.Button(top, text="Apply Settings", command=apply).pack(pady=20)

    def update_buffer_sizes(self):
        max_delay = int(self.fps * self.delay_seconds)
        max_replay = int(self.fps * self.replay_seconds)
        self.delay_buffer = deque(self.delay_buffer, maxlen=max_delay)
        self.replay_buffer = deque(self.replay_buffer, maxlen=max_replay)

    def load_config(self):
        self.config_file = "moundmirror_config.json"
        self.camera_mode = "wired"
        self.camera_source = "0"
        self.delay_seconds = 4.0
        self.replay_seconds = 10.0
        self.playback_speed = 0.5

        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.camera_mode = config.get("camera_mode", self.camera_mode)
                    self.camera_source = config.get("camera_source", self.camera_source)
                    self.delay_seconds = config.get("delay_seconds", self.delay_seconds)
                    self.replay_seconds = config.get("replay_seconds", self.replay_seconds)
                    self.playback_speed = config.get("playback_speed", self.playback_speed)
            except Exception as e:
                pass

    def save_config(self):
        config = {
            "camera_mode": self.camera_mode,
            "camera_source": self.camera_source,
            "delay_seconds": self.delay_seconds,
            "replay_seconds": self.replay_seconds,
            "playback_speed": self.playback_speed
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception:
            pass

    def toggle_fullscreen(self):
        is_fs = self.root.attributes("-fullscreen")
        self.root.attributes("-fullscreen", not is_fs)

    def save_recording(self):
        if not os.path.exists(self.temp_filename) or os.path.getsize(self.temp_filename) < 1000:
            messagebox.showwarning("No Video", "No recording data found.")
            return

        default_name = f"Bullpen_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.mp4"
        path = filedialog.asksaveasfilename(defaultextension=".mp4", initialfile=default_name,
                                            filetypes=[("MP4", "*.mp4")])

        if path:
            import shutil
            try:
                shutil.copy(self.temp_filename, path)
                messagebox.showinfo("Success", f"Saved to {path}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def on_close(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.running = False
            self.root.destroy()
            if os.path.exists(self.temp_filename):
                try:
                    os.remove(self.temp_filename)
                except:
                    pass

if __name__ == "__main__":
    root = tk.Tk()
    app = MoundMirrorApp(root)
    root.mainloop()
