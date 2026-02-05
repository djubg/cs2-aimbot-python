# CS2 AimBot Python 🖱️🎯

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python) ![License](https://img.shields.io/badge/License-MIT-green) ![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

**Python-based visual aim assist for Counter-Strike 2 (CS2)** using YOLO for target detection, MSS for screen capture, and Tkinter for GUI/overlay.

This project is intended for educational purposes, demonstrating real-time object detection, mouse control, and GUI overlay techniques in Python.

---

## Features ✨

- Screen capture around the center with configurable FOV  
- Real-time enemy detection using YOLO (Ultralytics)  
- Lock/unlock targets with right-click  
- Smooth mouse movement with deadzone and interpolation  
- Head/body aim selection  
- Transparent overlay showing FOV and locked target  
- Live YOLO view for debugging  
- Configurable sensitivity, resolution, auto-shoot, and more  
- Dynamic deadzone for fast-moving targets  
- Compatible with CS2 (AMD & NVIDIA GPUs)

---

## Technical Details ⚙️

- **MSS:** High-performance screen capture  
- **YOLO (Ultralytics):** Object detection  
- **Tkinter:** GUI and overlay  
- **Win32 API:** Mouse movement & clicks  
- **pynput:** Right-click handling  
- **Threading & Queues:** Separate threads for capture, inference, overlay, and mouse control

---

## Installation 💻

1. Clone the repository:

```bash
git clone https://github.com/djubg/cs2-aimbot-python.git
Navigate to the project folder:

cd cs2-aimbot-python
Install dependencies:

pip install -r requirements.txt
requirements.txt should include:

ultralytics
opencv-python
mss
pynput
pywin32
numpy
tk
```

## Usage 🚀
Run the main script:
```
python main.py
```

Configure the GUI:

FOV (Field of View)

Sensitivity

Auto-shoot

Resolution presets

Head/body aim

Right-click to lock/unlock targets.

Open YOLO live view to debug detections.

## FAQ / Troubleshooting ❓
Overlay not visible: Ensure Tkinter window is not minimized; overlay is always on top.

YOLO detections slow: Reduce capture resolution or YOLO FPS.

Mouse movement jerky: Adjust deadzone and smoothing.

Windows error _thread._local object has no attribute 'srcdc': Ensure MSS is instantiated in the main thread.

## Notes 📝
Head factor = 0.25, Body factor = 0.5 (adjustable)

Overlay centered and always on top

Dynamic deadzone prevents jitter on fast-moving targets

# Disclaimer ⚠️
This project is for educational purposes only. Using aim assist in online multiplayer games may result in bans. The author is not responsible for misuse. Use responsibly.

## License 📄
MIT License
https://choosealicense.com/licenses/mit/
