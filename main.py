"""CinePilot application runner.

Starts the video pipeline, the FastAPI Director's Monitor, and the Gemini
Live DirectorAgent concurrently, and shuts everything down cleanly on
SIGINT / Ctrl+C.

Usage examples:
    python main.py --source synthetic
    python main.py --source synthetic --demo-mode
    python main.py --source rtmp --rtmp-url rtmp://127.0.0.1:1935/live/drone
    python main.py --source file --video-path .\\footage\\flight01.mp4
    python main.py --source webcam --port 8080
"""

import argparse
import asyncio
import contextlib
import logging
import signal
import sys

import uvicorn

import server
from config import settings
from demo_provider import DeterministicDemoProvider
from director_agent import DirectorAgent
from grafana_publisher import GrafanaPublisher
from video_stream import VideoStreamManager

logger = logging.getLogger("cinepilot.main")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cinepilot",
        description="CinePilot — Agentic Aerial Cinematography Director",
    )
    parser.add_argument(
        "--source",
        choices=["rtmp", "rtsp", "webcam", "file", "synthetic"],
        default="rtmp",
        help="Video source to ingest (default: rtmp).",
    )
    parser.add_argument(
        "--stream-url",
        default=None,
        help="RTMP/RTSP ingest URL (default: RTMP_URL / RTSP_URL from .env).",
    )
    parser.add_argument(
        "--rtmp-url",
        default=None,
        help="Backward-compatible alias for --stream-url.",
    )
    parser.add_argument(
        "--video-path",
        default=None,
        help="Path to a local video file (required for --source file).",
    )
    parser.add_argument(
        "--webcam-index",
        type=int,
        default=0,
        help="Webcam device index for --source webcam (default: 0).",
    )
    parser.add_argument(
        "--demo-mode",
        action="store_true",
        help=(
            "Run the explicit deterministic story demo without Gemini or "
            "hardware; also allows synthetic fallback if the source fails."
        ),
    )
    parser.add_argument(
        "--allow-synthetic-fallback",
        action="store_true",
        help=(
            "Allow a failed real source to fall back to synthetic frames. "
            "Off by default: a real-drone failure must be visible, never fake."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Web UI port (default: {settings.PORT}).",
    )
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    # Quiet down noisy third-party loggers.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)


async def run_app(args: argparse.Namespace) -> None:
    port = args.port or settings.PORT

    if args.source == "file" and not args.video_path:
        logger.error("--source file requires --video-path")
        sys.exit(2)

    stream_url = args.stream_url or args.rtmp_url
    if args.source == "rtsp" and not (stream_url or settings.RTSP_URL):
        logger.error("--source rtsp requires --stream-url (or RTSP_URL in .env)")
        sys.exit(2)

    allow_fallback = (
        args.allow_synthetic_fallback
        or args.demo_mode
        or settings.ALLOW_SYNTHETIC_FALLBACK
    )

    # --- Video pipeline ---
    video_manager = VideoStreamManager(
        source=args.source,
        rtmp_url=stream_url,
        rtsp_url=stream_url,
        video_path=args.video_path,
        webcam_index=args.webcam_index,
        allow_synthetic_fallback=allow_fallback,
        on_transition=server.app_state.record_source_transition,
    )
    video_manager.start()
    server.set_video_manager(video_manager)
    server.app_state.set_provenance(
        "deterministic_demo" if args.demo_mode else "live",
        video_manager.active_source,
    )

    demo_provider = DeterministicDemoProvider() if args.demo_mode else None
    server.set_demo_provider(demo_provider)
    if demo_provider is not None:
        demo_provider.seed(server.app_state)

    # --- Telemetry + agent ---
    grafana = GrafanaPublisher()
    agent = DirectorAgent(
        video_manager=video_manager,
        app_state=server.app_state,
        grafana=grafana,
    )

    # --- Web server ---
    uvicorn_config = uvicorn.Config(
        server.app,
        host=settings.HOST,
        port=port,
        log_level="info",
        loop="asyncio",
    )
    web_server = uvicorn.Server(uvicorn_config)
    web_server.install_signal_handlers = lambda: None  # we manage signals

    stop_event = asyncio.Event()

    def request_shutdown(*_: object) -> None:
        logger.info("Shutdown requested — stopping CinePilot...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_shutdown)
        except NotImplementedError:
            # Windows event loops don't support add_signal_handler;
            # fall back to the default KeyboardInterrupt path.
            signal.signal(sig, request_shutdown)

    logger.info(
        "CinePilot Director's Monitor: http://%s:%s (source=%s)",
        settings.HOST,
        port,
        args.source,
    )

    server_task = asyncio.create_task(web_server.serve(), name="uvicorn")
    agent_task = asyncio.create_task(agent.run(), name="director-agent")
    stop_task = asyncio.create_task(stop_event.wait(), name="stop-signal")

    try:
        done, _ = await asyncio.wait(
            [server_task, agent_task, stop_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            if task is not stop_task and task.exception() is not None:
                logger.error("Fatal task error: %s", task.exception())
    finally:
        # --- Graceful teardown ---
        agent.stop()
        web_server.should_exit = True
        for task in (agent_task, server_task):
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(task, timeout=5.0)
        for task in (agent_task, server_task, stop_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(
            agent_task, server_task, stop_task, return_exceptions=True
        )
        video_manager.stop()
        grafana.close()
        logger.info("CinePilot shut down cleanly. That's a wrap.")


def main() -> None:
    configure_logging()
    args = parse_args()
    try:
        asyncio.run(run_app(args))
    except KeyboardInterrupt:
        logger.info("Interrupted — goodbye.")


if __name__ == "__main__":
    main()
