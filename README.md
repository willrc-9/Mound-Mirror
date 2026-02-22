[Here you can see the new logo image, which is a tight crop of the camera with the baseball lens and "MOUND MIRROR" text, centered at the top.]

# Mound Mirror (v0.5 Beta) ⚾🎥

Mound Mirror is a localized, low-latency delayed video feedback system designed specifically for baseball pitchers during bullpen sessions. By utilizing a wireless catcher-POV camera and a configurable rolling frame buffer, pitchers can throw a pitch and immediately watch their own mechanics without needing a coach to manually record and play back the footage.

## 🚀 What's New in v0.5 Beta

* **Wireless Catcher POV:** Transitioned from wired USB webcams to wireless local IP camera streams.
* **Standalone Executables:** No Python installation required! Pre-compiled binaries are now available for both Windows and Linux.
* **Threaded Network Capture:** Implemented a Producer-Consumer threading model to handle Wi-Fi drops and network stutters silently, preventing the main interface from freezing.
* **Persistent Configuration:** The app automatically remembers your camera URL, delay settings, and playback speeds between sessions.
* **Dynamic GUI Settings:** Change your IP camera URL, delay time, and slow-motion speed on the fly without restarting the application.

## 🛠️ Features

* **Customizable Time Delay:** Set a continuous delay (e.g., 4 seconds) so you can throw, turn to the screen, and watch the pitch arrive.
* **Instant Replay Mode:** Hit Spacebar to instantly pause the live delay and watch the last X seconds of footage in configurable slow-motion (0.1x - 1.0x speed).
* **Live Recording:** Record bullpen sessions directly to `.mp4` and save them locally.
* **Cross-Platform Support:** Ready to run on Windows and Linux systems.

## 📋 Hardware Requirements

* A computer running the application (placed safely near the mound or backstop).
* An iOS/Android smartphone (to be used as the wireless camera).
* A tactical chest-rig/harness to securely mount the phone under the catcher's chest protector.
* A local Wi-Fi network (both the computer and phone must be connected to the exact same network).

## ⚙️ Quick Start Guide

### 1. Download Mound Mirror
Head over to the Releases tab on this repository and download the latest executable for your operating system:
* **Windows:** Download the `.exe` file.
* **Linux:** Download the Linux executable file.

### 2. Start the Wireless Camera (iPhone/Android)
1. Download IP Camera Lite (or a similar IP webcam app) on your smartphone.
2. Connect your phone to your local Wi-Fi network.
3. Open the app and tap **Turn on IP Camera Server**.
4. Note the IP address and port displayed on the screen (e.g., `http://192.168.1.50:8081`).

### 3. Launch the Application
* **Windows:** Double-click the downloaded executable.
* **Linux:** Open your terminal, navigate to your download folder, make the file executable, and run it:

```bash
chmod +x MoundMirror_v0.5
./MoundMirror_v0.5
