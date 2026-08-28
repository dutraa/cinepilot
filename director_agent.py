"""Core Gemini Live orchestration agent for CinePilot.

Maintains a bidirectional WebSocket session with the Gemini Live API:

  * `frame_sender`      — samples JPEG frames from the VideoStreamManager at
                          ~1.2 FPS and streams them as realtime media input.
  * `response_receiver` — consumes server turns, executes tool calls
                          (`update_shot_list`, `speak_director_guidance`),
                          publishes telemetry to Grafana, updates AppState,
                          and returns tool results to Gemini.

The agent reconnects automatically with exponential backoff on any session
failure and degrades gracefully when no API key is configured.
"""

import asyncio
import logging
import time
import traceback
from typing import Any, Optional

from google import genai
from google.genai import types

from config import settings
from grafana_publisher import GrafanaPublisher
from tools import DIRECTOR_TOOLS, execute_tool
from video_stream import VideoStreamManager

logger = logging.getLogger("cinepilot.agent")

SYSTEM_INSTRUCTION = (
    "You are CinePilot, an expert aerial cinematography director for high-end "
    "film production. You watch incoming drone video frames continuously. You "
    "evaluate framing, rule-of-thirds, gimbal tilt, horizon alignment, "
    "lighting, and pacing. You actively maintain the 5-part shot list by "
    "calling `update_shot_list` when a shot succeeds or needs re-attempting, "
    "and you issue direct, vocal flight commands to the pilot via "
    "`speak_director_guidance`."
)

RECONNECT_BASE_DELAY = 2.0
RECONNECT_MAX_DELAY = 30.0
METRICS_PUBLISH_INTERVAL = 5.0

# Prebuilt Gemini Live voice used for spoken director responses.
DEFAULT_VOICE_NAME = "Puck"


class DirectorAgent:
    """Runs the Gemini Live session loop until stopped."""

    def __init__(
        self,
        video_manager: VideoStreamManager,
        app_state: Any,
        grafana: Optional[GrafanaPublisher] = None,
    ) -> None:
        self.video_manager = video_manager
        self.app_state = app_state
        self.grafana = grafana or GrafanaPublisher()
        self._stop_event = asyncio.Event()

        self._frames_sent = 0
        self._last_frame_sent_at = 0.0
        self._rolling_fps = 0.0
        self._latency_ms = 0.0

        self.app_state.update_metrics(grafana_status=self.grafana.status)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        """Main loop: connect, stream, and reconnect on failure."""
        if not settings.GEMINI_API_KEY:
            logger.error(
                "GEMINI_API_KEY is not set. The Director's Monitor will run, "
                "but no AI direction will occur. Set the key in .env and restart."
            )
            self.app_state.update_metrics(gemini_status="No API Key")
            await self._stop_event.wait()
            return

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        delay = RECONNECT_BASE_DELAY

        while not self._stop_event.is_set():
            try:
                self.app_state.update_metrics(gemini_status="Connecting")
                await self._run_session(client)
                delay = RECONNECT_BASE_DELAY  # clean exit — reset backoff
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - reconnect on any failure
                logger.error("Gemini Live session error: %s", exc)
                logger.debug("%s", traceback.format_exc())
                self.app_state.update_metrics(gemini_status="Disconnected")
                if self._stop_event.is_set():
                    break
                logger.info("Reconnecting to Gemini Live in %.1fs...", delay)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
                delay = min(delay * 2.0, RECONNECT_MAX_DELAY)

        self.app_state.update_metrics(gemini_status="Disconnected")
        logger.info("DirectorAgent stopped")

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------

    async def _run_session(self, client: genai.Client) -> None:
        config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=DEFAULT_VOICE_NAME
                    )
                )
            ),
            # Transcribe the model's spoken output so the receiver can log it
            # (and we can discard the raw PCM chunks without losing content).
            output_audio_transcription=types.AudioTranscriptionConfig(),
            system_instruction=types.Content(
                parts=[types.Part(text=SYSTEM_INSTRUCTION)]
            ),
            tools=DIRECTOR_TOOLS,
        )
        logger.info(
            "Connecting to Gemini Live (model=%s)...", settings.GEMINI_MODEL
        )
        async with client.aio.live.connect(
            model=settings.GEMINI_MODEL, config=config
        ) as session:
            logger.info("Gemini Live session established")
            self.app_state.update_metrics(gemini_status="Connected")

            sender = asyncio.create_task(self._frame_sender(session))
            receiver = asyncio.create_task(self._response_receiver(session))
            metrics = asyncio.create_task(self._metrics_publisher())

            tasks = [sender, receiver, metrics]
            try:
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_EXCEPTION
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    exc = task.exception()
                    if exc is not None and not isinstance(
                        exc, asyncio.CancelledError
                    ):
                        raise exc
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    # ------------------------------------------------------------------
    # Frame streaming
    # ------------------------------------------------------------------

    async def _frame_sender(self, session: Any) -> None:
        """Sample frames at FRAME_INTERVAL_SEC and stream them to Gemini."""
        interval = max(settings.FRAME_INTERVAL_SEC, 0.1)
        while not self._stop_event.is_set():
            started = time.monotonic()
            jpeg = await asyncio.to_thread(
                self.video_manager.get_jpeg_bytes, 80, 1024
            )
            if jpeg is not None:
                await self._send_frame(session, jpeg)
                self._frames_sent += 1
                now = time.monotonic()
                if self._last_frame_sent_at > 0:
                    instant_fps = 1.0 / max(now - self._last_frame_sent_at, 1e-6)
                    # Exponential moving average keeps the HUD readable.
                    self._rolling_fps = (
                        0.8 * self._rolling_fps + 0.2 * instant_fps
                        if self._rolling_fps > 0
                        else instant_fps
                    )
                self._last_frame_sent_at = now
                self.app_state.update_metrics(
                    fps=round(self._rolling_fps, 2),
                    frames_sent=self._frames_sent,
                )
            elapsed = time.monotonic() - started
            await asyncio.sleep(max(interval - elapsed, 0.05))

    async def _send_frame(self, session: Any, jpeg: bytes) -> None:
        """Send one JPEG frame as realtime video input.

        Uses the `video` field of `send_realtime_input` — the legacy
        `media_chunks` path is deprecated in the Gemini Live API.
        """
        await session.send_realtime_input(
            video=types.Blob(data=jpeg, mime_type="image/jpeg")
        )

    # ------------------------------------------------------------------
    # Response handling
    # ------------------------------------------------------------------

    async def _response_receiver(self, session: Any) -> None:
        """Consume Gemini server turns and execute tool calls.

        With AUDIO response modality, model turns arrive as raw PCM chunks in
        `inline_data`. We discard those bytes (browser-side TTS handles spoken
        guidance) and rely on `output_audio_transcription` to log what the
        director said.
        """
        while not self._stop_event.is_set():
            turn_started = time.monotonic()
            transcript_parts: list[str] = []
            async for response in session.receive():
                self._latency_ms = (time.monotonic() - turn_started) * 1000.0
                self.app_state.update_metrics(
                    latency_ms=round(self._latency_ms, 1)
                )

                # Tool calls are the primary control channel — handle first.
                if getattr(response, "tool_call", None):
                    await self._handle_tool_call(session, response.tool_call)

                server_content = getattr(response, "server_content", None)
                if server_content is not None:
                    # Streaming transcript of the model's spoken output.
                    transcription = getattr(
                        server_content, "output_transcription", None
                    )
                    if transcription is not None and getattr(
                        transcription, "text", None
                    ):
                        transcript_parts.append(transcription.text)

                    model_turn = getattr(server_content, "model_turn", None)
                    if model_turn is not None and getattr(model_turn, "parts", None):
                        for part in model_turn.parts:
                            # Raw audio chunk — discard the bytes.
                            inline_data = getattr(part, "inline_data", None)
                            if inline_data is not None:
                                data = getattr(inline_data, "data", b"") or b""
                                logger.debug(
                                    "Discarding %d bytes of model audio (%s)",
                                    len(data),
                                    getattr(inline_data, "mime_type", "audio"),
                                )
                                continue
                            text = getattr(part, "text", None)
                            if text:
                                logger.info("Director notes: %s", text.strip())

                    if getattr(server_content, "turn_complete", False):
                        if transcript_parts:
                            logger.info(
                                "Director (spoken): %s",
                                "".join(transcript_parts).strip(),
                            )
                            transcript_parts = []
                turn_started = time.monotonic()

    async def _handle_tool_call(self, session: Any, tool_call: Any) -> None:
        function_responses = []
        for fc in getattr(tool_call, "function_calls", None) or []:
            name = fc.name
            args = dict(fc.args or {})
            logger.info("Tool call from Gemini: %s(%s)", name, args)
            result = execute_tool(self.app_state, name, args)
            self.grafana.publish_tool_call(name, args, result)
            function_responses.append(
                types.FunctionResponse(id=fc.id, name=name, response=result)
            )

        if not function_responses:
            return

        if hasattr(session, "send_tool_response"):
            await session.send_tool_response(function_responses=function_responses)
        else:
            await session.send(
                input=types.LiveClientToolResponse(
                    function_responses=function_responses
                )
            )

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    async def _metrics_publisher(self) -> None:
        """Periodically push frame metrics to Grafana Loki."""
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=METRICS_PUBLISH_INTERVAL
                )
                return
            except asyncio.TimeoutError:
                pass
            self.grafana.publish_frame_metrics(
                fps=self._rolling_fps,
                latency_ms=self._latency_ms,
                frames_sent=self._frames_sent,
            )
