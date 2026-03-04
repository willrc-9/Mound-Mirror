import cv2
import threading
import time
import socket
import requests
import asyncio
from bleak import BleakScanner, BleakClient

class ThreadedCamera:
    def __init__(self, mode="wired", source=0):
        self.mode = mode
        self.source = source
        self.running = False
        self.frame = None
        self.lock = threading.Lock()
        self.capture = None
        self.keep_alive_thread = None

    def start(self):
        if self.mode == "gopro":
            return self._start_gopro()
        else:
            return self._start_standard()

    def _start_standard(self):
        print(f"[Mound Mirror] Connecting to {self.mode} camera: {self.source}")
        if self.mode == "wired":
            try:
                self.source = int(self.source)
            except ValueError:
                self.source = 0
                
        self.capture = cv2.VideoCapture(self.source)
        if not self.capture.isOpened():
            print("[Mound Mirror] Failed to open camera.")
            return False
            
        self.running = True
        threading.Thread(target=self._update, daemon=True).start()
        return True

    def _start_gopro(self):
        print("[Mound Mirror] Starting Seamless GoPro Connection...")
        
        # 1. DYNAMIC BLUETOOTH WAKE-UP
        print("[Mound Mirror] -> Scanning for nearby GoPros...")
        try:
            async def wake_gopro():
                # Scan for 5 seconds to find any GoPro in the area
                devices = await BleakScanner.discover(timeout=5.0)
                gopro_device = next((d for d in devices if d.name and "GoPro" in d.name), None)
                
                if not gopro_device:
                    print("[Mound Mirror] No GoPro found via Bluetooth. Is it on?")
                    return
                
                print(f"[Mound Mirror] -> Found {gopro_device.name} ({gopro_device.address}), connecting...")
                
                # Connect dynamically using the discovered address
                async with BleakClient(gopro_device.address, timeout=10.0) as client:
                    CMD_UUID = "b5f90072-aa8d-11e3-9046-0002a5d5c51b"
                    await client.write_gatt_char(CMD_UUID, bytearray([0x03, 0x17, 0x01, 0x01]), response=True)
                    print("[Mound Mirror] -> Camera Wi-Fi is broadcasting!")

            asyncio.run(wake_gopro())
            time.sleep(2)
        except Exception as e:
            print(f"[Mound Mirror] BLE Wakeup failed or skipped: {e}")

        # 2. WAIT FOR OS TO AUTO-CONNECT
        print("[Mound Mirror] -> Waiting for OS to auto-connect to GoPro Wi-Fi...")
        connected = False
        for _ in range(15): 
            try:
                requests.get("http://10.5.5.9:8080/", timeout=2)
                connected = True
                break
            except requests.exceptions.RequestException:
                time.sleep(2)

        if not connected:
            print("[Mound Mirror] ERROR: OS did not auto-connect to the Wi-Fi.")
            return False

        print("[Mound Mirror] -> Connected to GoPro network!")

        # 3. CLEAR STUCK STREAMS & START NEW STREAM
        print("[Mound Mirror] -> Starting Video Stream...")
        try:
            requests.get("http://10.5.5.9:8080/gopro/camera/stream/stop", timeout=2)
            time.sleep(1)
            response = requests.get("http://10.5.5.9:8080/gopro/camera/stream/start", timeout=5)
            if response.status_code != 200:
                print(f"[Mound Mirror] GoPro refused to start. Code: {response.status_code}")
                return False
        except Exception:
            print("[Mound Mirror] Could not reach GoPro API.")
            return False

        # 4. OPEN UDP STREAM IN OPENCV
        print("[Mound Mirror] -> Opening UDP Feed...")
        stream_url = "udp://10.5.5.9:8554?overrun_nonfatal=1&fifo_size=50000000"
        self.capture = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
        self.capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)

        if not self.capture.isOpened():
            print("[Mound Mirror] Failed to open UDP stream.")
            return False

        self.running = True
        self.keep_alive_thread = threading.Thread(target=self._keep_alive, daemon=True)
        self.keep_alive_thread.start()
        threading.Thread(target=self._update, daemon=True).start()
        
        print("[Mound Mirror] GoPro stream is live!")
        return True

    def _keep_alive(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        msg = b"_GPHD_:0:0:2:0.000000\n"
        while self.running:
            try:
                sock.sendto(msg, ("10.5.5.9", 8554))
            except:
                pass
            time.sleep(2.0)

    def _update(self):
        while self.running:
            ret, frame = self.capture.read()
            if ret:
                with self.lock:
                    self.frame = frame
            else:
                time.sleep(0.01)

    def read(self):
        with self.lock:
            if self.frame is not None:
                return True, self.frame.copy()
            return False, None

    def stop(self):
        print("[Mound Mirror] Shutting down camera thread...")
        self.running = False
        if self.capture:
            self.capture.release()
            
        if self.mode == "gopro":
            try:
                requests.get("http://10.5.5.9:8080/gopro/camera/stream/stop", timeout=2)
            except:
                pass