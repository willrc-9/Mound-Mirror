# ⚾ VeloVision - Look through your catcher's eyes
**Real-Time Video Delay & Instant Replay for Baseball Training**

[![Download Windows](https://img.shields.io/badge/Download-Windows-blue?logo=windows&style=for-the-badge)](https://github.com/YOUR_USERNAME/VeloVision/releases)
![Version](https://img.shields.io/badge/version-0.2-green?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-orange?style=for-the-badge)

---

## 📝 Overview
**VeloVision** is a computer vision tool designed for pitchers and hitters to analyze mechanics without interrupting their workflow. It provides a live "time tunnel" video feed (delayed by X seconds) so athletes can complete a motion and immediately review it on screen without touching a computer.

Built with **Python** and **OpenCV**, it features an instant slow-motion replay system that captures the last 10 seconds of action at the press of a button.

## ✨ Features
* **Time Tunnel:** Set a custom delay (e.g., 5 seconds) to see yourself after the action happens.
* **Instant Replay:** Press `SPACE` to trigger a 10-second slow-motion replay of the last action.
* **Smart Recording:** Save specific bullpen sessions to MP4 for later analysis.
* **Hardware Support:** Works with standard Webcams, GoPros (via HDMI/CamLink), and USB Capture Cards.

## 🚀 Installation & Usage
1.  Go to the [**Releases**](https://github.com/YOUR_USERNAME/VeloVision/releases) page.
2.  Download the latest `VeloVision.exe` file.
3.  Run the application (No installation required).
    * *Note: Windows may flag the app as unrecognized. Click "More Info" -> "Run Anyway".*

### Setup Guide
1.  **Select Camera:** Upon launch, enter `0` for webcam or `1` for external camera (GoPro).
2.  **Set Delay:** Use the "Delay" slider to sync the video with your rhythm (usually 4-6 seconds).
3.  **Train:** Throw your pitch, then look at the screen to see the delayed feed.

## 🎮 Controls

| Input | Action |
| :--- | :--- |
| **SPACE** | Trigger Instant Slow-Motion Replay |
| **Q** | Quit Application / Exit Replay |
| **Mouse Click** | Toggle Recording (Red Button) |

## 🛠️ Tech Stack
* **Language:** Python 3.12
* **Computer Vision:** OpenCV (cv2)
* **GUI:** Tkinter & OpenCV HighGUI
* **Build Tool:** PyInstaller

---
*Developed by William Collison • Licensed under MIT*
