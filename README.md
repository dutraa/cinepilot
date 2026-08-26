# 🎬 CinePilot

**An Agentic Aerial Cinematography Director**

CinePilot connects a live drone video feed to the **Google Gemini Live API** and turns it into an AI film director. Gemini watches your aerial footage in real time, evaluates framing, gimbal tilt, horizon alignment, composition, and lighting — then maintains an automated shot list and speaks flight corrections to the pilot, all rendered on a dark-mode "Director's Monitor" web dashboard.

## How It Works

```mermaid
flowchart LR
    subgraph Ingest
        A[DJI Drone / RTMP] --> V[VideoStreamManager]
        B[RTSP / Webcam / File] --> V
        C[Synthetic Fallback] -.auto-swap.-> V
    end

    V -- "JPEG frames @ ~1.2 FPS" --> G[Gemini Live API<br/>bidirectional WebSocket]
    G -- "tool calls" --> T[update_shot_list<br/>speak_director_guidance]
    T --> S[AppState]
    T --> L[Grafana Loki<br/>telemetry]

    V -- MJPEG --> W[Director's Monitor<br/>FastAPI + SSE]
    S -- "SSE every 250ms" --> W
    W -- "Web Speech API TTS" --> P((Pilot))
```

1. **`VideoStreamManager`** grabs frames from RTMP, RTSP, a webcam, a local video file, or a synthetic OpenCV-generated aerial scene. If a live source drops, it hot-swaps to the synthetic fallback automatically so the pipeline never stalls.
2. **`DirectorAgent`** streams JPEG frames to Gemini Live at ~1.2 FPS over a bidirectional WebSocket and listens for responses.
3. Gemini calls two tools as it directs the shoot:
   - **`update_shot_list`** — moves the 5-part shot list (Establishing Wide, Top-Down Property, Orbit Pass, Low Reveal, Pull Away) through `PENDING → IN_PROGRESS → COMPLETED / REJECTED` with directorial feedback.
   - **`speak_director_guidance`** — issues spoken flight cues ("Tilt down 15 degrees, subject is drifting off-center") at `INFO` / `WARNING` / `URGENT` priority.
4. Every tool call and rolling frame metric (FPS, latency, frames sent) is pushed to **Grafana Loki** — or printed as structured JSON in Dry Run mode when no credentials are configured.
5. The **Director's Monitor** dashboard shows the live feed with a viewfinder HUD, the real-time shot list, and a guidance banner — and speaks new cues aloud in the browser via the Web Speech API.

## Screenshot Tour

- **Left panel** — live MJPEG monitor with rule-of-thirds grid, corner brackets, and FPS/latency telemetry overlay.
- **Right panel** — the ER2 shot list with color-coded status badges and the director's latest feedback per shot.
- **Bottom banner** — the most recent guidance cue; `WARNING` and `URGENT` cues glow and pulse for visibility.
- **Header** — glowing status pills for Gemini (Connected / Connecting / Disconnected) and Grafana (Live / Dry Run), plus a mute toggle for audio guidance.

## Quick Start

### Prerequisites

- Python 3.10+
- A [Gemini API key](https://aistudio.google.com/apikey)
- (Optional) An RTMP server receiving your drone feed, e.g. [MediaMTX](https://github.com/bluenviron/mediamtx) or nginx-rtmp
- (Optional) Grafana Cloud Loki credentials for telemetry

### Install

```bash
git clone https://github.com/<you>/cinepilot.git
cd cinepilot
pip install -r requirements.txt
```

### Configure

Copy the example environment file and add your key:

```bash
cp .env.example .env
```

```ini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
RTMP_URL=rtmp://127.0.0.1:1935/live/drone
GRAFANA_URL=
GRAFANA_USER=
GRAFANA_API_KEY=
```

### Run

No drone handy? Start with the built-in synthetic aerial scene:

```bash
python main.py --source synthetic
```

Then open **http://127.0.0.1:8000** in your browser.

Other sources:

```bash
# Live DJI drone feed via RTMP
python main.py --source rtmp --rtmp-url rtmp://127.0.0.1:1935/live/drone

# An RTSP camera
python main.py --source rtsp --rtmp-url rtsp://192.168.1.50:554/stream

# A local video file (loops forever)
python main.py --source file --video-path footage/flight01.mp4

# Your webcam, on a different port
python main.py --source webcam --port 8080
```

If an RTMP/webcam source fails or disconnects mid-flight, CinePilot logs a warning and switches to the synthetic fallback rather than going dark.

## Configuration Reference

All settings are read from `.env` (or environment variables) via pydantic-settings:

| Variable | Default | Description |
| --- | --- | --- |
| `GEMINI_API_KEY` | *(empty)* | Google Gemini API key. Without it, the monitor UI still runs but no AI direction occurs. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini Live model to connect to. |
| `RTMP_URL` | `rtmp://127.0.0.1:1935/live/drone` | Default RTMP ingest URL. |
| `GRAFANA_URL` | *(empty)* | Grafana Loki push endpoint (`.../loki/api/v1/push`). |
| `GRAFANA_USER` | *(empty)* | Grafana Cloud Loki username / tenant ID. |
| `GRAFANA_API_KEY` | *(empty)* | Grafana Cloud API token. |
| `FRAME_INTERVAL_SEC` | `0.8` | Seconds between frames sent to Gemini (~1.2 FPS). |
| `HOST` | `127.0.0.1` | Web UI bind host. |
| `PORT` | `8000` | Web UI port (overridable with `--port`). |

Leave the three `GRAFANA_*` values empty to run telemetry in **Dry Run** mode — structured JSON events are printed to stdout instead of being pushed to Loki.

## HTTP API

| Endpoint | Description |
| --- | --- |
| `GET /` | The Director's Monitor dashboard. |
| `GET /video_feed` | Live MJPEG stream (`multipart/x-mixed-replace`). |
| `GET /events` | Server-Sent Events stream of the full app state (shot list, guidance, metrics), pushed on change or every 250 ms. |
| `GET /health` | JSON system status: video source, Gemini/Grafana status, frames sent. |

## Project Structure

```
cinepilot/
├── main.py               # CLI runner: video + web server + agent, graceful shutdown
├── director_agent.py     # Gemini Live session: frame sender, response receiver, reconnection
├── tools.py              # Tool declarations (update_shot_list, speak_director_guidance) + executors
├── video_stream.py       # Hot-swappable video sources with synthetic aerial fallback
├── server.py             # FastAPI app, thread-safe AppState, MJPEG + SSE endpoints
├── grafana_publisher.py  # Non-blocking Loki telemetry (background thread / dry-run mode)
├── config.py             # pydantic-settings configuration
├── templates/
│   └── index.html        # Dark-mode Director's Monitor dashboard
├── requirements.txt
└── .env.example
```

## Telemetry

When Grafana credentials are set, CinePilot streams two event types to Loki with labels `{app="cinepilot", env="production"}` and nanosecond timestamps:

- **`tool_call`** — every Gemini tool invocation with its arguments and result.
- **`frame_metrics`** — rolling FPS, response latency (ms), and total frames sent, published every 5 seconds.

A simple LogQL query to see the director at work:

```
{app="cinepilot", event="tool_call"} | json
```

## Notes & Tips

- **Audio guidance** uses the browser's native `speechSynthesis` — most browsers require one user interaction (a click anywhere) before audio will play. Use the header button to mute/unmute.
- **DJI drones** can stream RTMP directly from the DJI Fly / Pilot app to a local RTMP server; point `RTMP_URL` at it.
- The synthetic source is great for demos and development — it renders a moving subject, tilting horizon, and composition guides, which gives Gemini real material to critique.
- Frame sampling rate, JPEG quality (80), and max frame dimension (1024 px) are tuned to keep Gemini Live latency low; adjust `FRAME_INTERVAL_SEC` if you want tighter or looser direction.

## License

MIT — see [LICENSE](LICENSE). (Add a `LICENSE` file before publishing, or swap in your preferred license.)
