"""Per-device state, trigger detection, and command queue.

CHANGES FROM PREVIOUS VERSION:
  - DeviceState gains session tracking fields: session_active, session_started_at,
    intervention_count_this_session.
  - New on_session_event() function resets trigger/cooldown on session start,
    and clears the command queue on session end.
  - _is_triggered() now gates on session_active — VLM only fires during active
    sessions.
  - ingest_telemetry() extracts session_active from the incoming signals dict
    (the bridge embeds it from /focus_robot/session_active).
"""
import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from . import config
from .schemas import Command, Signals, TelemetryIn

_now = time.time


@dataclass
class TelemetrySample:
    timestamp: float
    signals: Signals


@dataclass
class DeviceState:
    device_id: str
    history: deque = field(
        default_factory=lambda: deque(maxlen=config.TELEMETRY_HISTORY_LEN))

    trigger_streak_start: Optional[float] = None
    awaiting_image: bool = False
    last_vlm_at: float = 0.0
    pending_commands: deque = field(default_factory=deque)

    # ── Session tracking ──────────────────────────────────
    # Mirrors what the decision_node owns on the robot side.
    # The server tracks this so it can gate VLM triggers and
    # provide session context to the VLM prompt.
    session_active: bool = False
    session_started_at: Optional[float] = None
    intervention_count: int = 0


class DeviceRegistry:
    def __init__(self):
        self._devices: dict[str, DeviceState] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, device_id: str) -> DeviceState:
        async with self._lock:
            if device_id not in self._devices:
                self._devices[device_id] = DeviceState(device_id=device_id)
            return self._devices[device_id]

    async def get(self, device_id: str) -> Optional[DeviceState]:
        async with self._lock:
            return self._devices.get(device_id)

    async def all_ids(self) -> list[str]:
        async with self._lock:
            return list(self._devices.keys())


registry = DeviceRegistry()


# ─────────────────────────────────────────────────────────
# SESSION BOUNDARY HANDLING
# ─────────────────────────────────────────────────────────

async def on_session_event(device_id: str, event: str, **kwargs) -> None:
    """Called when the decision node posts to /session.

    event is one of: "started", "ended", "paused", "resumed"

    On "started":
      - Sets session_active = True, stamps session_started_at.
      - Resets trigger streak and cooldown so the VLM can fire
        promptly if the user is already fatigued at session start.
      - Clears any leftover commands from the previous session.
      - Resets per-session intervention counter.

    On "ended" / "paused":
      - Sets session_active = False.
      - Clears awaiting_image so we don't request a frame
        after the session has closed.
      - Pending commands are cleared — stale nudges from an
        ended session should never reach the robot.

    On "resumed":
      - Sets session_active = True, preserving existing history.
    """
    device = await registry.get_or_create(device_id)

    if event == "started":
        device.session_active = True
        device.session_started_at = _now()
        device.intervention_count = 0
        # Reset gating state so a fresh session gets a clean slate.
        device.trigger_streak_start = None
        device.last_vlm_at = 0.0
        device.awaiting_image = False
        device.pending_commands.clear()

    elif event in ("ended", "paused"):
        device.session_active = False
        device.awaiting_image = False
        device.pending_commands.clear()

    elif event == "resumed":
        device.session_active = True
        device.trigger_streak_start = None  # re-observe after resume


def _session_elapsed(device: DeviceState) -> float:
    """Seconds since session started, or 0."""
    if device.session_started_at is None:
        return 0.0
    return _now() - device.session_started_at


# ─────────────────────────────────────────────────────────
# TRIGGER LOGIC
# ─────────────────────────────────────────────────────────

def _is_triggered(signals: Signals, device: DeviceState) -> bool:
    """Return True if telemetry currently meets a trigger condition.

    Gated on session_active — the VLM never fires outside a session.

    Trigger conditions (any one fires during an active session):
      - fatigue_level >= FATIGUE_LEVEL_TRIGGER (MODERATE+)
      - m6_head_down True (from fatigue_summary JSON, M6 body droop)
      - m2_consecutive_eyes_missing high (face seen, eyes closed)
      - fatigue_level >= 1 AND session has been running > 30 mins
        (mild fatigue becomes more concerning over time)
    """
    if not device.session_active:
        return False

    fl = signals.fatigue_level
    if fl is not None and fl >= config.FATIGUE_LEVEL_TRIGGER:
        return True

    # fatigue_summary fields come through as extra_fields on the signals dict.
    ef = signals.extra_fields
    if ef.get("m6_head_down"):
        return True

    m2_eyes = ef.get("m2_consecutive_eyes_missing", 0) or 0
    if ef.get("m2_user_present") and m2_eyes >= config.EYES_MISSING_TRIGGER:
        return True

    # Mild fatigue sustained into a long session.
    if fl is not None and fl >= 1:
        elapsed = _session_elapsed(device)
        if elapsed >= 30 * 60:  # 30 minutes
            return True

    return False


async def ingest_telemetry(telemetry: TelemetryIn) -> bool:
    """Update device state. Return True if a VLM run should be requested."""
    device = await registry.get_or_create(telemetry.device_id)
    now = _now()

    device.history.append(TelemetrySample(timestamp=now, signals=telemetry.signals))

    # Keep server-side session_active in sync with the bridge's telemetry.
    # This is a fallback — the explicit /session event is authoritative.
    sa = telemetry.signals.extra_fields.get("session_active")
    if sa is not None and isinstance(sa, bool):
        device.session_active = sa

    triggered_now = _is_triggered(telemetry.signals, device)

    if not triggered_now:
        device.trigger_streak_start = None
        return False

    if device.trigger_streak_start is None:
        device.trigger_streak_start = now
        return False

    streak_duration = now - device.trigger_streak_start
    if streak_duration < config.TRIGGER_SUSTAIN_SECS:
        return False

    if now - device.last_vlm_at < config.COOLDOWN_SECS:
        return False

    if device.awaiting_image:
        return False

    device.awaiting_image = True
    return True


# ─────────────────────────────────────────────────────────
# COMMAND QUEUE
# ─────────────────────────────────────────────────────────

async def enqueue_command(device_id: str, command: Command) -> None:
    device = await registry.get_or_create(device_id)
    device.pending_commands.append((_now(), command))
    device.intervention_count += 1


async def drain_commands(device_id: str) -> list[Command]:
    device = await registry.get(device_id)
    if device is None:
        return []
    now = _now()
    out: list[Command] = []
    while device.pending_commands:
        queued_at, cmd = device.pending_commands.popleft()
        if now - queued_at <= config.COMMAND_TTL_SECS:
            out.append(cmd)
    return out


async def should_request_image(device_id: str) -> bool:
    device = await registry.get(device_id)
    if device is None:
        return False
    return device.awaiting_image


async def mark_image_received(device_id: str) -> None:
    device = await registry.get_or_create(device_id)
    device.awaiting_image = False


async def mark_vlm_completed(device_id: str) -> None:
    device = await registry.get_or_create(device_id)
    device.last_vlm_at = _now()


async def latest_signals(device_id: str) -> Optional[Signals]:
    device = await registry.get(device_id)
    if device is None or not device.history:
        return None
    return device.history[-1].signals


async def session_context(device_id: str) -> dict:
    """Return session metadata for use in VLM prompts."""
    device = await registry.get(device_id)
    if device is None:
        return {"session_active": False, "elapsed_mins": 0.0,
                "intervention_count": 0}
    return {
        "session_active":     device.session_active,
        "elapsed_mins":       round(_session_elapsed(device) / 60.0, 1),
        "intervention_count": device.intervention_count,
    }
