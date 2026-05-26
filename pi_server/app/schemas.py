"""Request/response schemas.

CHANGES FROM PREVIOUS VERSION:
  - Signals now has an extra_fields dict that absorbs the flat JSON keys from
    fatigue_summary (fatigue_score, ear, perclos, m2_*, m6_*, etc.) without
    needing individual Pydantic fields for each one. The server's trigger logic
    reads from extra_fields for the richer fatigue_summary signals.
  - TelemetryIn.signals uses the updated Signals model.
  - New ParseCommandIn / ParseCommandOut schemas for the /parse_command endpoint.
  - New SessionEventIn schema for the /session endpoint.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class Signals(BaseModel):
    # Core fields — always present if sent.
    fatigue_level: Optional[int] = None
    session_active: Optional[bool] = None

    # Legacy structured sub-objects (kept for backwards compatibility
    # with any client still sending them).
    user_state: Optional[Any] = None
    head_posture: Optional[Any] = None

    # Absorbs all flat fatigue_summary keys: fatigue_score, ear, perclos,
    # head_pitch_deg, face_absent_secs, face_present, m2_*, m6_*, etc.
    # Also absorbs session_active when embedded in the summary dict.
    extra_fields: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}

    def model_post_init(self, __context: Any) -> None:
        """Move any extra keys that Pydantic captured into extra_fields."""
        extra = self.__pydantic_extra__ or {}
        for k, v in extra.items():
            self.extra_fields[k] = v


class TelemetryIn(BaseModel):
    device_id: str
    sequence: int
    timestamp: float
    signals: Signals


class ImageIn(BaseModel):
    device_id: str
    sequence: int
    timestamp: float
    reason: str
    encoding: str
    width: int
    height: int
    data: str  # base64 JPEG


class Command(BaseModel):
    action: str
    text: Optional[str] = None
    extras: dict[str, Any] = Field(default_factory=dict)


class CommandsOut(BaseModel):
    request_image: bool = False
    commands: list[Command] = Field(default_factory=list)


# ── /parse_command ────────────────────────────────────────

class FatigueContext(BaseModel):
    fatigue_level: Optional[int] = None
    fatigue_label: Optional[str] = None
    m6_head_down: Optional[bool] = None


class ParseCommandIn(BaseModel):
    device_id: str
    text: str                          # raw voice command after wake-word strip
    session_active: bool = False
    session_paused: bool = False
    elapsed_secs: float = 0.0
    fatigue_context: Optional[FatigueContext] = None


class ParseCommandOut(BaseModel):
    action: str                        # start_session / end_session / etc.
    params: dict[str, Any] = Field(default_factory=dict)
    response_text: Optional[str] = None  # optional TTS acknowledgement


# ── /session ─────────────────────────────────────────────

class SessionEventIn(BaseModel):
    device_id: str
    event: str            # started / ended / paused / resumed
    timestamp: float
    duration_mins: Optional[float] = None
    elapsed_secs: Optional[float] = None
    intervention_count: Optional[int] = None
    reason: Optional[str] = None      # e.g. "shutdown"
