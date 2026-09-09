"""CinePilot configuration.

All settings are loaded from environment variables (or a local `.env` file)
via pydantic-settings. Import the `settings` singleton from this module.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings for CinePilot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Gemini ---
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    # The primary product loop is explicit between-takes analysis. The legacy
    # continuous Gemini Live path remains available only as an opt-in.
    ENABLE_CONTINUOUS_LIVE: bool = False
    ANALYSIS_TIMEOUT_SEC: float = 30.0

    # --- Visual previsualization renderer ---
    # The deterministic screen-space renderer is the default and the test
    # double. "google" enables provider-backed AI previsualization; it stays
    # off unless a key is configured, and it never fabricates Google
    # provenance for deterministic output.
    VISUALIZATION_PROVIDER: str = "deterministic"
    ENABLE_GENERATED_PREVISUALIZATION: bool = False
    # Falls back to GEMINI_API_KEY when empty.
    GOOGLE_VIDEO_API_KEY: str = ""
    # Gemini Omni Flash is the first candidate because it accepts a source
    # frame plus text and returns one short video through the Interactions
    # API. Veo 3.1 remains a configurable alternative for image-to-video.
    GOOGLE_VIDEO_BACKEND: str = "interactions"
    GOOGLE_VIDEO_MODEL: str = "gemini-omni-1.1-flash"
    GOOGLE_VIDEO_TIMEOUT_SEC: float = 180.0
    GOOGLE_VIDEO_POLL_INTERVAL_SEC: float = 3.0
    # Hard ceiling for one generated clip; larger responses are rejected.
    GOOGLE_VIDEO_MAX_BYTES: int = 33554432
    # Providers currently emit 4, 6, or 8 second clips. The requested 10-second
    # deterministic duration is never relabeled onto a shorter generated clip.
    GOOGLE_VIDEO_DURATION_SEC: int = 8
    GOOGLE_VIDEO_RESOLUTION: str = "720p"
    GOOGLE_VIDEO_ASPECT_RATIO: str = "16:9"

    # --- Video ingest ---
    RTMP_URL: str = "rtmp://127.0.0.1:1935/live/drone"
    RTSP_URL: str = ""
    # Seconds to wait for a real RTMP/RTSP source to open before treating the
    # attempt as failed.
    SOURCE_CONNECT_TIMEOUT_SEC: float = 10.0
    # Reconnect backoff after a real source disconnects (exponential, capped).
    SOURCE_RECONNECT_DELAY_SEC: float = 2.0
    SOURCE_RECONNECT_MAX_DELAY_SEC: float = 30.0
    # A live source whose newest frame is older than this is reported "stale".
    SOURCE_STALE_AFTER_SEC: float = 3.0
    # Frames older than this are never sent to Gemini as current observations.
    SOURCE_MAX_FRAME_AGE_SEC: float = 2.0
    # How often the dashboard/health surfaces should consider source state.
    SOURCE_HEALTH_INTERVAL_SEC: float = 2.0
    # Request low-latency capture behavior (minimal driver-side buffering).
    SOURCE_LOW_LATENCY: bool = True
    # A failed real source must never silently become synthetic footage.
    # Only explicit opt-in (--allow-synthetic-fallback / demo mode) enables it.
    ALLOW_SYNTHETIC_FALLBACK: bool = False

    # --- Grafana Loki telemetry ---
    GRAFANA_URL: str = ""
    GRAFANA_USER: str = ""
    GRAFANA_API_KEY: str = ""

    # --- Sampling / serving ---
    # ~1.2 FPS sampling rate of frames pushed to Gemini Live.
    FRAME_INTERVAL_SEC: float = 0.8
    CRITIQUE_COOLDOWN_SEC: float = 5.0
    EVENT_LOG_PATH: str = "runs/cinepilot-events.jsonl"
    HOST: str = "127.0.0.1"
    PORT: int = 8000


settings = Settings()
