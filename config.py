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
