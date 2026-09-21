# π RuView — Setup & Installation Guide

Welcome to **RuView**, the open-source spatial intelligence system that transforms ordinary WiFi Channel State Information (CSI) into real-time presence detection, vital signs monitoring, and 3D pose estimation — without cameras, wearables, or cloud dependencies.

---

## 📋 Table of Contents

- [System Architecture](#-system-architecture)
- [Prerequisites](#-prerequisites)
- [Option 1: Quick Start (Simulated Mode — No Hardware Needed)](#option-1-quick-start-simulated-mode--no-hardware-needed)
- [Option 2: Running from Source (Rust & Node.js)](#option-2-running-from-source-rust--nodejs)
- [Option 3: ESP32 Hardware Setup & Deployment](#option-3-esp32-hardware-setup--deployment)
- [🌐 Web UI & Live Visualizations](#-web-ui--live-visualizations)
- [🔌 REST API & WebSockets Reference](#-rest-api--websockets-reference)
- [🧪 Verification & Harness Tools](#-verification--harness-tools)
- [❓ Troubleshooting & FAQ](#-troubleshooting--faq)

---

## 🏗 System Architecture

```
┌─────────────────┐       UDP / CSI      ┌──────────────────────────┐
│  ESP32 Sensors  │ ───────────────────> │   Rust Sensing Server    │
│ (S3 / C6 / C3)  │  (Raw CSI packets)   │  (v2/sensing-server.exe) │
└─────────────────┘                      └────────────┬─────────────┘
                                                      │ HTTP / WebSockets
                                                      ▼
                                         ┌──────────────────────────┐
                                         │       Web UI / Client    │
                                         │ (http://localhost:3000) │
                                         └──────────────────────────┘
```

---

## 🛠 Prerequisites

### Hardware (Optional for live sensing)
* **ESP32-S3** or **ESP32-C6** development board (~$6–$9).
* Micro-USB or USB-C data cable for flashing.

### Software Environment
| Tool | Minimum Version | Recommended Version | Note |
|---|---|---|---|
| **Node.js** | v18.0+ | v22.0+ | For UI & CLI harness |
| **Rust** | 1.85+ | 1.87+ | For `v2/` sensing server |
| **Python** | 3.10+ | 3.13+ | For verification & ML scripts |
| **Git** | 2.30+ | latest | Submodules enabled |

---

## 🚀 Option 1: Quick Start (Simulated Mode — No Hardware Needed)

You can launch the entire RuView pipeline in under **2 minutes** using simulated CSI signals.

### Step 1: Clone the Repository
```bash
git clone https://github.com/AbhilashBala2003/ruview.git
cd ruview/RuView
```

### Step 2: Start the Prebuilt Sensing Server
If you are on Windows, you can launch the pre-compiled binary directly:
```powershell
.\v2\target\release\sensing-server.exe --source simulate --http-port 3000 --ws-port 3001 --ui-path .\ui
```

On Linux / macOS:
```bash
cd v2
cargo run --release --no-default-features -p wifi-densepose-sensing-server -- --source simulate --http-port 3000 --ws-port 3001 --ui-path ../ui
```

### Step 3: Open the Dashboard
Open your browser to:
**[http://localhost:3000/ui/index.html](http://localhost:3000/ui/index.html)**

* Click the **"Demo"** tab at the top.
* Click the **"Demo"** button under Human Pose Detection to see instant animated 17-keypoint COCO poses.

---

## ⚙️ Option 2: Running from Source (Rust & Node.js)

### 1. Build the Rust Sensing Server

#### On Windows (PowerShell):
Use the automated environment helper:
```powershell
.\build-server.ps1
```

Or build manually:
```powershell
cd v2
cargo build --release --no-default-features -p wifi-densepose-sensing-server
```

#### On Linux / macOS:
```bash
cd v2
cargo build --release --no-default-features -p wifi-densepose-sensing-server
```

### 2. Launching the Server
```powershell
# Run with simulation mode
.\v2\target\release\sensing-server.exe --source simulate --http-port 3000 --ws-port 3001 --ui-path .\ui
```

---

## 📡 Option 3: ESP32 Hardware Setup & Deployment

RuView provides both **ESP-IDF firmware binaries** and **MicroPython-based flashing tools** inside `firmware/`.

### Approach A: MicroPython Quick Flash (`firmware/esp32-ruview/`)

1. Connect your ESP32 board via USB.
2. Open PowerShell in `firmware/esp32-ruview/`:
```powershell
cd firmware/esp32-ruview
.\run_esp32.ps1
```
Or run the Python upload script directly:
```bash
python upload.py --port COM3 --baud 460800
```

3. To flash the MicroPython binary and launch the watcher:
```bash
python flash_and_run.py --port COM3
```

### Approach B: ESP-IDF Production Firmware (`firmware/esp32-csi-node/`)

If you have ESP-IDF installed:
```bash
cd firmware/esp32-csi-node

# Set target to ESP32-S3 or ESP32-C6
idf.py set-target esp32s3

# Build firmware
idf.py build

# Flash and monitor
idf.py -p COM3 flash monitor
```

### Provision WiFi & Target Server
Provision your ESP32 node to connect to your WiFi and target server IP:
```bash
python firmware/esp32-csi-node/provision.py \
  --port COM3 \
  --ssid "YourWiFiSSID" \
  --password "YourWiFiPassword" \
  --target-ip 192.168.1.100
```

---

## 🌐 Web UI & Live Visualizations

RuView provides multiple user interface views:

### 1. Main Dashboard (`ui/index.html`)
* **Demo Tab**: Instant visualization with 3D animated pose skeletons.
* **Sensing Tab**: Live 3D Gaussian splatting representation of human movement.
* **Vital Signs Tab**: Contactless real-time monitoring of respiration (6–30 BPM) and heart rate (40–120 BPM).

### 2. Standalone Observatory (`ui/observatory.html`)
A high-performance 3D spatial viewer connecting directly to `ws://localhost:3001/ws/sensing`.

---

## 🔌 REST API & WebSockets Reference

When the server is running on `http://localhost:3000`:

### REST Endpoints
| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Returns server health status and client count |
| `/api/v1/info` | GET | System version, backend engine, and feature flags |
| `/api/v1/vital-signs` | GET | Real-time breathing and heart rate estimates |
| `/api/v1/pose/current` | GET | Current 17-keypoint tracked human skeleton data |
| `/api/v1/sensing/latest` | GET | Latest raw CSI subcarrier frame per node |

#### Quick API Test (PowerShell):
```powershell
Invoke-RestMethod http://localhost:3000/health
Invoke-RestMethod http://localhost:3000/api/v1/vital-signs
Invoke-RestMethod http://localhost:3000/api/v1/pose/current
```

### WebSocket Streaming
* **Sensing Stream**: `ws://localhost:3001/ws/sensing`
* **Pose Stream**: `ws://localhost:3001/ws/pose`

---

## 🧪 Verification & Harness Tools

RuView includes built-in verification scripts and an npm CLI harness (`npx @ruvnet/ruview`).

### Run Proof Pipeline Verification
```bash
python archive/v1/data/proof/verify.py
```
*Output:* `VERDICT: PASS` (SHA-256 validation)

### Run Harness CLI
```bash
cd harness/ruview
node bin/cli.js doctor
node bin/cli.js verify
```

---

## ❓ Troubleshooting & FAQ

#### Q: The Pose Canvas is blank!
**A:** Click the **▶ Start** button or the purple **🎭 Demo** button on the Demo tab in `ui/index.html`.

#### Q: Can I run RuView without ESP32 hardware?
**A:** Yes! Launch the server with `--source simulate` to generate synthetic 3D poses and vitals.

#### Q: How do I change the HTTP / WebSocket port?
**A:** Pass `--http-port <PORT>` and `--ws-port <PORT>` to `sensing-server.exe`.

---

## 📄 License

MIT License. Developed with ❤️ by the RuView team.
