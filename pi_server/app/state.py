"""Per-device state, trigger detection, and command queue.

This module is the only place that knows when to fire the VLM. The route
handlers just push telemetry / images in and pull commands out — they don't
make decisions.
"""
import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from . import config
from .schemas import Command, Signals, TelemetryIn

# All time comparisons on the server use this clock — never bridge-supplied
# timestamps. The bridge's timestamp field is just a sequencing hint and may
# drift slightly from the server's wall clock.
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

    # When the current "trigger condition" streak started, or None if not
    # currently in a trigger condition.
    trigger_streak_start: Optional[float] = None

    # True when we've decided this device needs a VLM run and are waiting
    # for the bridge to deliver an image. Cleared once the image arrives.
    awaiting_image: bool = False

    # When the last VLM run completed (any reason). Used for cooldown.
    last_vlm_at: float = 0.0

    # Outbound command queue (FIFO). Each entry is (queued_at, Command).
    pending_commands: deque = field(default_factory=deque)


class DeviceRegistry:
    """Thread-safe-ish (async-safe) registry of all devices we've heard from."""

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


# Module-level singleton. FastAPI app uses this.
registry = DeviceRegistry()


# ─────────────────────────────────────────────────────────
# TRIGGER LOGIC
# ─────────────────────────────────────────────────────────

def _is_triggered(signals: Signals) -> bool:
    """Return True if telemetry currently meets a trigger condition.

    Trigger conditions (any one fires):
      - fatigue_level >= FATIGUE_LEVEL_TRIGGER (MODERATE or worse)
      - head_posture.head_down sustained (the node itself already has a
        15-frame hysteresis, so trusting head_down=True is fine)
      - user_present AND consecutive_eyes_missing very high (face seen
        but eyes closed — strong sleepy signal)
    """
    if signals.fatigue_level is not None and \
            signals.fatigue_level >= config.FATIGUE_LEVEL_TRIGGER:
        return True

    if signals.head_posture and signals.head_posture.head_down:
        return True

    us = signals.user_state
    if us and us.user_present and \
            us.consecutive_eyes_missing >= config.EYES_MISSING_TRIGGER:
        return True

    return False


async def ingest_telemetry(telemetry: TelemetryIn) -> bool:
    """Update device state. Return True if a VLM run should be requested.

    Caller is responsible for actually setting `awaiting_image` and emitting
    the request_image flag — this function only does pure detection so it's
    easy to test.
    """
    device = await registry.get_or_create(telemetry.device_id)
    now = _now()

    device.history.append(TelemetrySample(timestamp=now, signals=telemetry.signals))

    triggered_now = _is_triggered(telemetry.signals)

    if not triggered_now:
        # Streak broken; reset.
        device.trigger_streak_start = None
        return False

    # We're in a trigger condition.
    if device.trigger_streak_start is None:
        device.trigger_streak_start = now
        return False

    streak_duration = now - device.trigger_streak_start
    if streak_duration < config.TRIGGER_SUSTAIN_SECS:
        return False

    # Sustained trigger. Check cooldown.
    if now - device.last_vlm_at < config.COOLDOWN_SECS:
        return False

    # Already waiting for an image from a previous trigger.
    if device.awaiting_image:
        return False

    # Fire.
    device.awaiting_image = True
    return True


# ─────────────────────────────────────────────────────────
# COMMAND QUEUE
# ─────────────────────────────────────────────────────────

async def enqueue_command(device_id: str, command: Command) -> None:
    device = await registry.get_or_create(device_id)
    device.pending_commands.append((_now(), command))


async def drain_commands(device_id: str) -> list[Command]:
    """Return all pending commands and clear the queue. Filters out
    commands older than COMMAND_TTL_SECS so stale instructions don't
    pile up if the bridge was offline."""
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
    """Called by the /commands handler — does this device owe us an image?"""
    device = await registry.get(device_id)
    if device is None:
        return False
    return device.awaiting_image


async def mark_image_received(device_id: str) -> None:
    """Called by the /image handler once a requested frame arrives."""
    device = await registry.get_or_create(device_id)
    device.awaiting_image = False


async def mark_vlm_completed(device_id: str) -> None:
    """Stamp the cooldown timer once a VLM run finishes (success or fail)."""
    device = await registry.get_or_create(device_id)
    device.last_vlm_at = _now()


async def latest_signals(device_id: str) -> Optional[Signals]:
    """Most recent telemetry signals for this device, or None."""
    device = await registry.get(device_id)
    if device is None or not device.history:
        return None
    return device.history[-1].signals
