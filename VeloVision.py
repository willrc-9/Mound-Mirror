import cv2
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, Menu
from PIL import Image, ImageTk
from collections import deque
from datetime import datetime
import os

# Try importing pygrabber for camera names
try:
    from pygrabber.dshow_graph import FilterGraph
    HAS_PYGRABBER = True
except ImportError:
    HAS_PYGRABBER = False

class VeloVisionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VeloVision 0.4")
        self.root.geometry("1000x700")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- CONFIGURATION DEFAULTS ---
        self.camera_index = 0
        self.delay_seconds = 4.0
        self.replay_seconds = 10.0
        self.playback_speed = 0.5
        self.is_recording = False
        self.is_replay_mode = False
        self.fps = 60.0

        # --- VIDEO STATE ---
        self.cap = None
        self.running = False
        self.delay_buffer = deque()
        self.replay_buffer = deque()
        self.writer = None
        self.temp_filename = "temp_rec.mp4"
        self.frame_lock = threading.Lock()

        # --- SHARED FRAME VARIABLE ---
        self.latest_frame = None

        # --- GUI SETUP ---
        self.create_menu()
        self.create_main_layout()

        # Auto-start default camera
        self.start_camera_thread()

        # --- START THE UI UPDATE LOOP ---
        self.update_ui_loop()

    def create_menu(self):
        menubar = Menu(self.root)
        self.root.config(menu=menubar)

        # File Menu
        file_menu = Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save Recording...", command=self.save_recording)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        # Settings Menu
        settings_menu = Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Preferences...", command=self.open_preferences)
        settings_menu.add_command(label="Select Camera...", command=self.open_camera_select)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        # View Menu
        view_menu = Menu(menubar, tearoff=0)
        view_menu.add_checkbutton(label="Fullscreen", command=self.toggle_fullscreen)
        menubar.add_cascade(label="View", menu=view_menu)

    def create_main_layout(self):
        # 1. Video Area (Black Background)
        self.video_frame = tk.Frame(self.root, bg="black")
        self.video_frame.pack(fill=tk.BOTH, expand=True)

        self.video_label = tk.Label(self.video_frame, bg="black")
        self.video_label.pack(fill=tk.BOTH, expand=True)

        # 2. Controls Bar (Bottom)
        self.controls_frame = tk.Frame(self.root, bg="#333", height=60)
        self.controls_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Buttons
        style = ttk.Style()
        style.configure("TButton", padding=6)

        self.btn_replay = ttk.Button(self.controls_frame, text="⏪ INSTANT REPLAY (Space)",
                                     command=self.trigger_replay)
        self.btn_replay.pack(side=tk.LEFT, padx=20, pady=10)

        self.btn_record = tk.Button(self.controls_frame, text="⚫ REC", bg="#444", fg="red",
                                    font=("Arial", 10, "bold"), command=self.toggle_record)
        self.btn_record.pack(side=tk.RIGHT, padx=20, pady=10)

        # Status Label
        self.lbl_status = tk.Label(self.controls_frame, text="Ready", bg="#333", fg="white")
        self.lbl_status.pack(side=tk.LEFT, padx=10)

        # Bind Key Events
        self.root.bind('<space>', lambda e: self.trigger_replay(e))
        self.root.bind('<f>', lambda e: self.toggle_fullscreen())
        self.root.bind('<q>', lambda e: self.on_close())

    def start_camera_thread(self):
        if self.running:
            self.running = False
            self.root.after(500, self.start_camera_thread)
            return

        self.running = True
        self.thread = threading.Thread(target=self.video_loop, daemon=True)
        self.thread.start()

    def update_ui_loop(self):
        """Checks for new frames and updates the UI safely on the main thread"""
        # Always show whatever is in the latest_frame variable
        # This works for both Live Feed AND Replay now.
        if self.latest_frame is not None:
            self.show_frame(self.latest_frame)

        # Schedule the next check in 15ms (approx 60 FPS)
        self.root.after(15, self.update_ui_loop)

    def video_loop(self):
        self.cap = cv2.VideoCapture(self.camera_index)
        self.cap.set(cv2.CAP_PROP_FPS, 60)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps <= 0: self.fps = 60.0

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.writer = cv2.VideoWriter(self.temp_filename, fourcc, 60.0, (w, h))

        self.update_buffer_sizes()

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                break

            if self.is_recording and self.writer:
                self.writer.write(frame)

            with self.frame_lock:
                self.delay_buffer.append(frame)
                self.replay_buffer.append(frame.copy())

                # SAVE FRAME TO VARIABLE (DO NOT SHOW DIRECTLY)
                if not self.is_replay_mode:
                    if len(self.delay_buffer) >= self.delay_buffer.maxlen:
                        self.latest_frame = self.delay_buffer[0]
                    else:
                        self.latest_frame = frame

            time.sleep(0.005)

        self.cap.release()
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

        self.video_label.imgtk = imgtk
        self.video_label.configure(image=imgtk)

        status_text = f"DELAY: {self.delay_seconds}s"
        if self.is_recording:
            status_text += " | ⚫ RECORDING"
        self.lbl_status.config(text=status_text, fg="red" if self.is_recording else "white")

    def trigger_replay(self, event=None):
        if self.is_replay_mode:
            self.is_replay_mode = False
            return
        threading.Thread(target=self.replay_worker, daemon=True).start()

    def replay_worker(self):
        self.is_replay_mode = True
        self.lbl_status.config(text="REPLAYING... (Press SPACE to Stop)", fg="yellow")

        with self.frame_lock:
            # Snapshot the buffer
            frames = list(self.replay_buffer)

        # --- MATH FIX: Use self.fps instead of 30.0 ---
        # This ensures it is always slow motion, no matter your camera speed.
        if self.fps <= 0: self.fps = 30.0  # Safety check

        # Formula: Time to wait = (Time per frame) / Speed Factor
        # Example: (0.016s) / 0.5 = 0.032s wait
        wait_time = (1.0 / self.fps) / self.playback_speed

        for frame in frames:
            # Stop if user hits Space
            if not self.is_replay_mode:
                break

            display = frame.copy()
            cv2.putText(display, f"REPLAY ({self.playback_speed}x)", (50, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 3)

            # --- STUTTER FIX: Just update the variable ---
            self.latest_frame = display

            # Sleep for the calculated slow-motion time
            time.sleep(wait_time)

        self.is_replay_mode = False
        self.lbl_status.config(text="Ready", fg="white")

    def toggle_record(self):
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.btn_record.config(text="🟥 STOP", fg="white", bg="red")
        else:
            self.btn_record.config(text="⚫ REC", fg="red", bg="#444")

    def open_camera_select(self):
        top = tk.Toplevel(self.root)
        top.title("Select Camera")
        top.geometry("300x150")

        tk.Label(top, text="Available Cameras:").pack(pady=10)

        cams = []
        if HAS_PYGRABBER:
            graph = FilterGraph()
            cams = graph.get_input_devices()
        else:
            cams = [f"Camera {i}" for i in range(5)]

        cam_var = tk.StringVar(value=cams[self.camera_index] if self.camera_index < len(cams) else cams[0])
        dropdown = ttk.OptionMenu(top, cam_var, cam_var.get(), *cams)
        dropdown.pack(pady=10)

        def confirm():
            try:
                self.camera_index = cams.index(cam_var.get())
                self.start_camera_thread()
                top.destroy()
            except:
                pass

        ttk.Button(top, text="Switch Camera", command=confirm).pack()

    def open_preferences(self):
        top = tk.Toplevel(self.root)
        top.title("Preferences")
        top.geometry("400x300")

        tk.Label(top, text="Delay (Seconds)").pack(pady=5)
        delay_var = tk.DoubleVar(value=self.delay_seconds)
        tk.Scale(top, variable=delay_var, from_=1, to=20, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20)

        tk.Label(top, text="Replay Speed (0.1x - 1.0x)").pack(pady=5)
        speed_var = tk.DoubleVar(value=self.playback_speed)
        tk.Scale(top, variable=speed_var, from_=0.1, to=1.0, resolution=0.1, orient=tk.HORIZONTAL).pack(fill=tk.X,
                                                                                                        padx=20)

        tk.Label(top, text="Replay History (Seconds)").pack(pady=5)
        hist_var = tk.DoubleVar(value=self.replay_seconds)
        tk.Scale(top, variable=hist_var, from_=5, to=30, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20)

        def apply():
            self.delay_seconds = delay_var.get()
            self.playback_speed = speed_var.get()
            self.replay_seconds = hist_var.get()
            self.update_buffer_sizes()
            top.destroy()

        ttk.Button(top, text="Apply Settings", command=apply).pack(pady=20)

    def update_buffer_sizes(self):
        max_delay = int(self.fps * self.delay_seconds)
        max_replay = int(self.fps * self.replay_seconds)

        self.delay_buffer = deque(self.delay_buffer, maxlen=max_delay)
        self.replay_buffer = deque(self.replay_buffer, maxlen=max_replay)

    def toggle_fullscreen(self):
        is_fs = self.root.attributes("-fullscreen")
        self.root.attributes("-fullscreen", not is_fs)

    def save_recording(self):
        if not os.path.exists(self.temp_filename) or os.path.getsize(self.temp_filename) < 1000:
            messagebox.showwarning("No Video", "No recording data found.")
            return

        default_name = f"Bullpen_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.mp4"
        path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            initialfile=default_name,
            filetypes=[("MP4", "*.mp4")]
        )

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
    app = VeloVisionApp(root)
    root.mainloop()