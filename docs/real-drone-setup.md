# Real-Drone Observation Setup (RTMP/RTSP)

Status: the code path below is implemented and verified with a deterministic
fake source and a local RTMP/RTSP smoke setup. **It has not yet been verified
against real drone hardware.** Do not claim "real-drone support verified"
until the hardware test at the bottom of this document has been performed.

## Safety boundary

CinePilot is advisory only. It observes the stream and recommends creative
adjustments. It never controls the drone: no flight commands, no waypoints,
no gimbal commands, no takeoff/landing, no SDK control calls, and no claims
that a recommendation is safe or executable. The pilot remains responsible
for flight safety and manually acts on recommendations.

## Overview

```text
drone camera
  -> DJI Fly / DJI Pilot (RTMP live streaming) or another streaming bridge
  -> local RTMP/RTSP server (e.g. MediaMTX)
  -> CinePilot VideoStreamManager
  -> live browser feed + Gemini Live frame analysis
  -> validated advisory critique / recommendations
  -> creator manually flies and captures the shot
  -> creator marks the recommendation acted / the shot completed
```

## 1. Publish the drone stream

**DJI Fly / DJI Pilot (most DJI consumer/enterprise drones):**

1. Connect the phone/controller to the drone as usual.
2. In DJI Fly: `Settings → Transmission → Live Streaming → RTMP`
   (DJI Pilot: `... → Live Broadcast → Custom RTMP`).
3. Enter the RTMP publish URL of the machine running the bridge, e.g.
   `rtmp://<pc-ip>:1935/live/drone`. The phone/controller must be on the
   same network as the PC (or reach it through your router).
4. Start the stream in the app.

If your drone/app cannot publish RTMP directly, any bridge that republishes
the feed as RTMP or RTSP works the same way (e.g. an HDMI capture of the
controller into OBS, streamed to the same MediaMTX URL).

## 2. Run a local RTMP/RTSP server (MediaMTX)

On the Windows 11 machine that will run CinePilot:

```powershell
# Download https://github.com/bluenviron/mediamtx/releases (windows_amd64.zip),
# unzip, then:
.\mediamtx.exe
```

MediaMTX listens on `rtmp://<pc-ip>:1935/<path>` and republishes the same
feed as `rtsp://<pc-ip>:8554/<path>` with no extra configuration. With the
DJI app publishing to `rtmp://<pc-ip>:1935/live/drone`, both of these work
as CinePilot sources:

- `rtmp://127.0.0.1:1935/live/drone`
- `rtsp://127.0.0.1:8554/live/drone` (usually lower latency with FFmpeg)

## 3. Launch CinePilot against the real source

```powershell
# RTMP
python main.py --source rtmp --stream-url rtmp://127.0.0.1:1935/live/drone

# or RTSP
python main.py --source rtsp --stream-url rtsp://127.0.0.1:8554/live/drone
```

`--rtmp-url` remains supported as a backward-compatible alias for
`--stream-url`. Do **not** pass `--allow-synthetic-fallback` for a real
flight: with a real source, synthetic fallback is disabled by default so a
stream failure is always visible instead of being papered over with fake
frames.

## 4. Verify the browser feed

Open `http://127.0.0.1:8000`:

- The monitor shows the drone image.
- The source strip under the monitor shows **REAL SOURCE**, status `live`,
  the frame age (should stay under ~1–2 s), capture FPS, and the redacted
  stream URL.
- The `Source` header pill is green and reads `rtmp · live` (or `rtsp`).

## 5. Verify /health

```powershell
curl http://127.0.0.1:8000/health
```

Check `source.status == "live"`, `source.is_real_source == true`,
`source.provenance == "live-rtmp"` (or `live-rtsp`), a recent
`source.last_frame_at`, and a small `source.frame_age_sec`. Credentials and
query strings in the stream URL are redacted here and in every log line.

## 6. Verify Gemini is receiving frames

- The `Gemini` pill shows `Connected` and `frames_sent` in `/health`
  increases over time.
- Only fresh frames are forwarded: if the stream stalls,
  `frames_skipped_stale` increases instead, and no stale frame is presented
  to Gemini as a current observation.
- Set a shot intent in the dashboard; a validated critique with one to three
  advisory tweaks should appear in the critique panel.

## 7. What happens when the stream is interrupted

- The manager reports `disconnected`, then `reconnecting` with exponential
  backoff (`SOURCE_RECONNECT_DELAY_SEC` doubling up to
  `SOURCE_RECONNECT_MAX_DELAY_SEC`).
- The last frame is dropped — the monitor shows a clearly-labeled
  "NO LIVE SIGNAL" status card, never an old frame pretending to be live and
  never synthetic footage (unless fallback was explicitly enabled).
- The dashboard shows the failure reason and the reconnect count, and warns
  that existing recommendations may not reflect the current scene.
- Frames stop flowing to Gemini; the event log records the transitions.

## 8. How to reconnect

Restart the stream from the drone app (or fix the network); CinePilot keeps
retrying and returns to `live` automatically. The reconnect count is visible
in the source strip and `/health`. No CinePilot restart is needed.

## 9. Running safely without synthetic fallback

The default is already safe: for `--source rtmp/rtsp/webcam/file`, synthetic
fallback is **off**. Synthetic frames appear only when:

- you run `--source synthetic` (explicit demo source), or
- you pass `--demo-mode` or `--allow-synthetic-fallback`, or
- `ALLOW_SYNTHETIC_FALLBACK=true` is set in `.env`.

When fallback does engage, it is labeled `SYNTHETIC FALLBACK` in the
dashboard, `fallback` in the status machine, and `synthetic-fallback` in the
event-log provenance — it is never pooled with live-drone evidence.

## Remaining hardware-dependent verification

Perform this checklist with a real drone before claiming hardware support:

1. Start the drone stream (DJI Fly/Pilot → MediaMTX).
2. Start CinePilot with the real RTMP/RTSP source.
3. Confirm the dashboard shows REAL SOURCE / live.
4. Confirm the browser feed shows the drone image.
5. Confirm frame age and FPS update.
6. Confirm Gemini receives live frames (`frames_sent` grows).
7. Confirm a validated critique appears.
8. Select (accept) a recommendation; confirm the manual guidance is shown.
9. Disconnect the stream; confirm `disconnected`/`reconnecting` status and
   that no synthetic footage silently appears.
10. Reconnect; confirm the live flow recovers.
11. Mark the shot completed manually; confirm coverage and the event log
    update with creator provenance.
