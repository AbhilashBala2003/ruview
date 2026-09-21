# Quick Start — See Poses RIGHT NOW

Your RuView server is running with simulated data. Here's how to see it working:

## Option 1: Browser Demo (Instant — No WebSocket needed)

1. Open http://localhost:3000/ui/index.html
2. Click the **"Demo"** tab at the top
3. Click the **purple "Demo"** button under "Human Pose Detection"
4. You'll see **3 animated people** walking, waving, and dancing

**This works immediately** — no WebSocket connection, no Start button, just instant animated skeletons.

---

## Option 2: Live CSI Data (Requires WebSocket fix)

The server is running on port 3000, but the UI's pose WebSocket expects a different endpoint. Quick fix:

### Use the Sensing Tab Instead

1. Open http://localhost:3000/ui/index.html
2. Click the **"Sensing"** tab
3. The 3D Gaussian visualization connects to `ws://localhost:8765/ws/sensing`

The "sensing" tab uses a different WebSocket that may work if the endpoint exists.

---

## Option 3: Use the Observatory (Live 3D Visualization)

1. Open http://localhost:3000/ui/observatory.html
2. This is a standalone viewer that connects directly to `/ws/sensing`
3. You'll see real-time 3D pose visualization

---

## What's Actually Running

```bash
# Server status
Server: http://localhost:3000
WebSocket (sensing): ws://localhost:3001/ws/sensing
WebSocket (pose): ws://localhost:3001/ws/pose

# What the UI expects (mismatch!)
UI pose canvas: /api/v1/stream/pose ← doesn't exist on Rust server
UI sensing tab: uses separate config (check config/api.config.js)
```

---

## Test the API Directly

```powershell
# Get current pose (works!)
Invoke-RestMethod http://localhost:3000/api/v1/pose/current | ConvertTo-Json -Depth 4

# Get vital signs
Invoke-RestMethod http://localhost:3000/api/v1/vital-signs

# Get latest sensing frame
Invoke-RestMethod http://localhost:3000/api/v1/sensing/latest
```

All REST APIs work. The issue is the WebSocket endpoint path mismatch between the UI and the Rust server.

---

## Next Steps

1. **Immediate**: Use the **Demo** tab to see animated poses
2. **Fix WebSocket**: Update `ui/config/api.config.js` to use `/ws/pose` instead of `/api/v1/stream/pose`
3. **Try Observatory**: Open `observatory.html` for live 3D visualization
4. **Check server logs**: The WebSocket connections show in terminal ID 7

---

## The "Blank Screen" Issue Explained

The "Human Pose Detection" canvas on the Demo tab shows:
- A **header** with Start/Stop/Demo buttons
- A **black canvas** (waiting for data)
- You must click **▶ Start** to begin the WebSocket stream OR click **🎭 Demo** for instant animation

**The Demo button gives you instant visual feedback** — it doesn't need the server at all. Click it!
