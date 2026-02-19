import cv2
import time
import threading
import tkinter as tk
from tkinter import simpledialog, filedialog
from collections import deque
from datetime import datetime
import os


class VeloVision:
    def __init__(self):
        # UI State
        self.camera_id = 0
        self.running = True
        self.recording = False
        self.replay_mode = False
        self.show_ui = True

        # Configuration Defaults
        self.fps = 60
        self.width = 1280
        self.height = 720
        self.delay_seconds = 4
        self.replay_seconds = 10
        self.slow_mo_factor = 4

        # Buffers
        self.delay_buffer = deque()
        self.replay_buffer = deque()

        # Video Writer
        self.writer = None
        self.temp_filename = "temp_recording.mp4"

        # Mouse State
        self.mouse_x, self.mouse_y = 0, 0
        self.clicked = False

    def select_camera(self):
        """Opens a simple dialog to ask for camera ID"""
        root = tk.Tk()
        root.withdraw()  # Hide the main tkinter window

        # Ask user for Camera ID
        cam_input = simpledialog.askinteger("VeloVision Setup",
                                            "Enter Camera Index:\n(0 for Webcam, 1/2 for External/GoPro)",
                                            initialvalue=0, minvalue=0, maxvalue=10)

        if cam_input is not None:
            self.camera_id = cam_input
        else:
            self.camera_id = 0  # Default if they cancel

        root.destroy()

    def init_camera(self):
        self.cap = cv2.VideoCapture(self.camera_id)

        # Try to force HD resolution (GoPros like high res)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        # Read actual parameters
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps <= 0: self.fps = 30  # Fallback

        print(f"Camera Initialized: {self.width}x{self.height} @ {self.fps} FPS")

        # Initialize Video Writer (Hidden temp file)
        # We use mp4v for broad compatibility
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.writer = cv2.VideoWriter(self.temp_filename, fourcc, self.fps, (self.width, self.height))

    def update_settings(self, val=None):
        """Callback for Trackbars"""
        # Read trackbar positions
        d_val = cv2.getTrackbarPos("Delay (s)", "VeloVision Control")
        r_val = cv2.getTrackbarPos("Replay Time (s)", "VeloVision Control")

        # Update logic ensuring min values
        self.delay_seconds = max(1, d_val)
        self.replay_seconds = max(2, r_val)

        # Resize buffers
        max_delay_frames = int(self.fps * self.delay_seconds)
        max_replay_frames = int(self.fps * self.replay_seconds)

        if self.delay_buffer.maxlen != max_delay_frames:
            self.delay_buffer = deque(self.delay_buffer, maxlen=max_delay_frames)

        if self.replay_buffer.maxlen != max_replay_frames:
            self.replay_buffer = deque(self.replay_buffer, maxlen=max_replay_frames)

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.clicked = True
            self.mouse_x, self.mouse_y = x, y

    def draw_ui(self, frame):
        """Draws the buttons and status directly onto the frame"""

        # Create a UI footer area (Gray bar)
        ui_height = 80
        # Make the frame bigger to fit UI
        full_display = cv2.copyMakeBorder(frame, 0, ui_height, 0, 0, cv2.BORDER_CONSTANT, value=[50, 50, 50])

        h, w = full_display.shape[:2]

        # --- BUTTON DEFINITIONS ---
        # 1. RECORD Button
        btn_rec_color = (0, 0, 255) if self.recording else (0, 100, 0)
        rec_text = "STOP REC" if self.recording else "START REC"
        cv2.rectangle(full_display, (20, h - 70), (180, h - 20), btn_rec_color, -1)
        cv2.putText(full_display, rec_text, (35, h - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # 2. REPLAY Button
        cv2.rectangle(full_display, (200, h - 70), (360, h - 20), (200, 100, 0), -1)
        cv2.putText(full_display, "REPLAY", (230, h - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # 3. Status Info
        status_text = f"Delay: {self.delay_seconds}s | Buffer: {self.replay_seconds}s"
        cv2.putText(full_display, status_text, (400, h - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        # --- CLICK HANDLING ---
        if self.clicked:
            self.clicked = False
            # Check Record Click
            if 20 < self.mouse_x < 180 and (h - 70) < self.mouse_y < (h - 20):
                self.recording = not self.recording
                print(f"Recording State: {self.recording}")

            # Check Replay Click
            elif 200 < self.mouse_x < 360 and (h - 70) < self.mouse_y < (h - 20):
                self.trigger_replay()

        return full_display

    def trigger_replay(self):
        print(">>> STARTING REPLAY")
        self.replay_mode = True

        # Snapshot buffer (Avoids thread modification during playback)
        replay_data = list(self.replay_buffer)
        total_frames = len(replay_data)

        if total_frames == 0:
            print("Buffer empty, nothing to replay.")
            self.replay_mode = False
            return

        # Calculate wait time for slow motion
        wait_time = int((1 / self.fps) * 1000 * self.slow_mo_factor)

        window_name = "VeloVision Control"

        # FIX: Use enumerate(replay_data) instead of looping and looking up index
        for i, frame in enumerate(replay_data):
            ui_frame = frame.copy()

            # Text Overlay
            cv2.putText(ui_frame, "INSTANT REPLAY (SLOW)", (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)

            # Progress Bar Logic
            h, w = ui_frame.shape[:2]
            # Calculate progress (0.0 to 1.0)
            progress = (i + 1) / total_frames
            bar_width = int(w * progress)

            # Draw Progress Bar (Yellow)
            cv2.rectangle(ui_frame, (0, h - 10), (bar_width, h), (0, 255, 255), -1)

            cv2.imshow(window_name, ui_frame)

            key = cv2.waitKey(wait_time) & 0xFF

            # 'q' stops the replay and returns to live feed
            # 'Space' also stops it (toggles)
            if key == ord('q') or key == 32:
                break

        self.replay_mode = False
        print(">>> REPLAY FINISHED")


    def save_recording(self):
        if not os.path.exists(self.temp_filename):
            return

        root = tk.Tk()
        root.withdraw()

        # Ask yes/no
        save_it = simpledialog.messagebox.askyesno("VeloVision", "Session ended. Save the recording?")

        if save_it:
            # Ask for location
            default_name = f"Bullpen_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.mp4"
            save_path = filedialog.asksaveasfilename(defaultextension=".mp4",
                                                     initialfile=default_name,
                                                     filetypes=[("MP4 Video", "*.mp4")])
            if save_path:
                # Rename the temp file to the save path
                # We need to close writer first (done in main loop)
                try:
                    # Python rename can't overwrite easily across drives, so we copy/delete
                    import shutil
                    shutil.move(self.temp_filename, save_path)
                    print(f"Saved to {save_path}")
                except Exception as e:
                    print(f"Error saving: {e}")

        # Cleanup temp file
        if os.path.exists(self.temp_filename):
            os.remove(self.temp_filename)

        root.destroy()

    def run(self):
        self.select_camera()
        self.init_camera()

        window_name = "VeloVision Control"
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, self.mouse_callback)

        # Create Trackbars
        cv2.createTrackbar("Delay (s)", window_name, self.delay_seconds, 30, self.update_settings)
        cv2.createTrackbar("Replay Time (s)", window_name, self.replay_seconds, 60, self.update_settings)

        print("System Ready. Press SPACE for Replay, Q to Quit.")

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                break

            # 1. Recording Logic
            # We record the RAW frame (no text overlays)
            if self.recording and self.writer:
                self.writer.write(frame)

            # 2. Buffer Logic
            self.delay_buffer.append(frame)
            self.replay_buffer.append(frame.copy())  # Copy for replay safety

            # 3. Visualization Logic
            if len(self.delay_buffer) >= self.delay_buffer.maxlen:
                display_frame = self.delay_buffer[0].copy()

                # Add "Live" overlay info
                cv2.putText(display_frame, f"DELAY: -{self.delay_seconds}s", (20, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

                if self.recording:
                    cv2.circle(display_frame, (self.width - 50, 50), 15, (0, 0, 255), -1)
                    cv2.putText(display_frame, "REC", (self.width - 110, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                                (0, 0, 255), 2)

                # Draw the UI Buttons at bottom
                final_image = self.draw_ui(display_frame)

                cv2.imshow(window_name, final_image)

            # 4. Input Handling
            key = cv2.waitKey(1) & 0xFF

            # Spacebar (32) or 'r' triggers Replay
            if key == 32:
                self.trigger_replay()
            elif key == ord('q'):
                self.running = False

            # Check for Window Close (X button)
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                self.running = False

        # Cleanup
        self.cap.release()
        self.writer.release()
        cv2.destroyAllWindows()

        # Trigger Save Dialog
        self.save_recording()


if __name__ == "__main__":
    app = VeloVision()
    app.run()
