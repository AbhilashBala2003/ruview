# RuView — Setup Complete ✅

## System Status: RUNNING

**Date:** July 9, 2026  
**Sensing Server:** http://localhost:3000  
**WebSocket:** ws://localhost:3001/ws/sensing  
**UI:** http://localhost:3000/ui/index.html ← **OPEN IN BROWSER**

---

## What's Working

### ✅ Environment
- **Node.js** v22.18.0 + npm 11.7.0
- **Python** 3.13.14 + numpy 2.5.1 + scipy 1.18.0
- **Rust** 1.97.0 + MSVC Build Tools 2022
- **Git** submodules initialized (rufield, rvcsi, ruvector)

### ✅ Python Proof Pipeline
```bash
cd c:\Users\91949\Desktop\ruview\RuView
python archive/v1/data/proof/verify.py
```
**VERDICT: PASS** — SHA-256 match (f8e76f21a0f9852b70b6d9dd5318239f6b20cbcb4cdd995863263cecdc446f7a)

### ✅ Rust Sensing Server
```bash
cd c:\Users\91949\Desktop\ruview\RuView\v2
.\target\release\sensing-server.exe --source simulate --http-port 3000 --ws-port 3001
```
- **Build time:** 7m 02s (437 crates, release + LTO)
- **Binary size:** 5.5 MB
- **Status:** Running with simulated CSI data
- **Persons tracked:** 3 (17-keypoint COCO pose)
- **Vital signs:** breathing ~10 BPM, heart rate ~46 BPM

### ✅ REST API (all endpoints verified)
| Endpoint | Status | Sample |
|----------|--------|--------|
| `/health` | ✅ | `{"status":"ok","source":"simulated","clients":2}` |
| `/api/v1/info` | ✅ | `{"version":"0.3.3","backend":"rust","features":{...}}` |
| `/api/v1/vital-signs` | ✅ | `{"breathing_rate_bpm":9.7,"heart_rate_bpm":46.2}` |
| `/api/v1/pose/current` | ✅ | `{"persons":[...], "total_persons":3}` |
| `/api/v1/sensing/latest` | ✅ | `{"frame_id":..., "nodes":[...]}` |

### ✅ Harness (`npx @ruvnet/ruview`)
```bash
cd harness/ruview
node bin/cli.js doctor     # all checks pass
node bin/cli.js verify     # VERDICT: PASS
node bin/cli.js onboard    # recommends repo-build
node --test test/*.test.mjs  # 34 pass, 2 skip, 0 fail
```

### ✅ Claude Code Plugin
- **Location:** `plugins/ruview/`
- **Skills:** 9 (quickstart → verify)
- **Commands:** 7 (`/ruview-start` → `/ruview-verify`)
- **Agents:** 3 (onboarding-guide, config-engineer, training-engineer)
- **Smoke test:** `bash plugins/ruview/scripts/smoke.sh` (needs Git Bash/WSL)

---

## Quick Commands

### Start the server
```powershell
cd C:\Users\91949\Desktop\ruview\RuView
.\v2\target\release\sensing-server.exe --source simulate --http-port 3000 --ws-port 3001 --ui-path .\ui
```

### Check health
```powershell
Invoke-RestMethod http://localhost:3000/health
```

### Open UI
```powershell
Start-Process http://localhost:3000/ui/index.html
```

### Verify proof
```powershell
python archive/v1/data/proof/verify.py
```

### Harness tools
```powershell
cd harness\ruview
node bin/cli.js --help
node bin/cli.js onboard
node bin/cli.js claim-check --text "accuracy 95% (MEASURED, verify.py)"
```

---

## What Was Fixed

1. **Installed Python 3.13** via winget → ran proof pipeline
2. **Installed Rust 1.97 + MSVC Build Tools** → compiled sensing-server
3. **Fixed harness `which()` function** → skips Windows Store Python stubs  
   (tests now correctly skip when Python is absent)
4. **Initialized git submodules** → vendor/rufield, vendor/rvcsi, etc.
5. **Compiled 437 Rust crates** → 5.5 MB release binary with LTO

---

## Next Steps

### Run with real ESP32 hardware
1. Flash an ESP32-S3 with `firmware/esp32-csi-node/`
2. Provision WiFi: `python firmware/esp32-csi-node/provision.py --port COM8 --ssid "..." --password "..." --target-ip 192.168.1.20`
3. Start server: `.\sensing-server.exe --source esp32 --udp-port 5005`

### Train a model
See `plugins/ruview/skills/ruview-model-training/SKILL.md`

### Run the CLI
```powershell
# From a Rust build
cd v2
cargo run -p wifi-densepose-cli -- --help

# Commands: baseline, enroll, train-room, room-watch (ADR-151)
cargo run -p wifi-densepose-cli -- baseline --duration 30
```

---

## Files Created During Setup

- `build-server.ps1` — PowerShell build script with MSVC paths
- `harness/ruview/src/tools.js` — fixed `which()` to skip WindowsApps stubs

---

## Browser URLs

- **Dashboard:** http://localhost:3000/ui/index.html
- **Observatory:** http://localhost:3000/ui/observatory.html
- **Pose fusion:** http://localhost:3000/ui/pose-fusion.html
- **3D point cloud:** http://localhost:3000/ui/pointcloud/
- **Three.js demos:** http://localhost:3000/ui/three.js/

All UIs connect to the live WebSocket at `ws://localhost:3001/ws/sensing`

---

## Project Structure

```
RuView/
├── v2/                          # Rust workspace (16 crates)
│   ├── target/release/
│   │   └── sensing-server.exe   # ← THE BINARY (5.5 MB)
│   └── crates/
│       ├── wifi-densepose-sensing-server/
│       ├── wifi-densepose-signal/
│       └── ... (16 total)
├── harness/ruview/              # npx @ruvnet/ruview harness
├── plugins/ruview/              # Claude Code plugin
├── archive/v1/                  # Python v1 (proof pipeline)
│   └── data/proof/verify.py     # Trust Kill Switch
├── firmware/esp32-csi-node/     # ESP32 CSI firmware
├── ui/                          # Three.js dashboards
└── docs/                        # Documentation + ADRs

437 Rust crates compiled in 7m 02s
```

---

**Status:** System is fully operational. The sensing server is running with simulated data. All APIs respond. The proof pipeline passes. Ready for real hardware or model training.
