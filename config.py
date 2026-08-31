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
