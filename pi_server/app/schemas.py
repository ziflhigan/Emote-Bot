"""Request/response schemas. Field names and shapes match server_bridge_node.py."""
from typing import Any, Optional

from pydantic import BaseModel, Field


class UserStateSignal(BaseModel):
    user_present: bool
    consecutive_eyes_missing: int
    consecutive_face_absent: int
    stamp: float


class HeadPostureSignal(BaseModel):
    pose_visible: bool
    calibrated: bool
    head_down: bool
    posture_score: float
    head_drop_ratio: float
    baseline_ratio: float
    consecutive_droop_frames: int
    stamp: float


class Signals(BaseModel):
    fatigue_level: Optional[int] = None
    session_active: Optional[bool] = None
    user_state: Optional[UserStateSignal] = None
    head_posture: Optional[HeadPostureSignal] = None


class TelemetryIn(BaseModel):
    device_id: str
    sequence: int
    timestamp: float
    signals: Signals


class ImageIn(BaseModel):
    device_id: str
    sequence: int
    timestamp: float
    reason: str  # "heartbeat" or "requested"
    encoding: str
    width: int
    height: int
    data: str  # base64-encoded JPEG bytes


class Command(BaseModel):
    action: str
    text: Optional[str] = None
    # Catch-all for future fields without breaking the bridge.
    extras: dict[str, Any] = Field(default_factory=dict)


class CommandsOut(BaseModel):
    request_image: bool = False
    commands: list[Command] = Field(default_factory=list)
