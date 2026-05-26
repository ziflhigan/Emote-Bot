"""FastAPI entrypoint.

CHANGES FROM PREVIOUS VERSION:
  - /telemetry: passes session_context to the background VLM task.
  - /image: passes session_context to the background VLM task.
  - NEW /session: receives session boundary events from the decision node
    (started / ended / paused / resumed) and resets server-side gating state.
  - NEW /parse_command: receives a raw voice command string from the decision
    node, asks the VLM to interpret it, and returns a structured action.
  - /debug/state: exposes new session fields.
"""
import logging

from fastapi import BackgroundTasks, FastAPI, HTTPException

from . import config, state, vlm
from .schemas import (Command, CommandsOut, ImageIn, ParseCommandIn,
                      ParseCommandOut, SessionEventIn, TelemetryIn)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("vlm-server")

app = FastAPI(title="VLM Wellness Server")


@app.get("/health")
async def health() -> dict:
    return {
        "status":    "ok",
        "model":     config.OLLAMA_MODEL,
        "ollama":    config.OLLAMA_HOST,
        "devices":   await state.registry.all_ids(),
    }


# ─────────────────────────────────────────────────────────
# TELEMETRY
# ─────────────────────────────────────────────────────────

@app.post("/telemetry")
async def telemetry_in(payload: TelemetryIn) -> dict:
    should_request = await state.ingest_telemetry(payload)
    if should_request:
        logger.info("Device %s: trigger sustained — requesting image",
                    payload.device_id)
    return {"ok": True, "request_image": should_request}


# ─────────────────────────────────────────────────────────
# IMAGE + VLM
# ─────────────────────────────────────────────────────────

@app.post("/image")
async def image_in(payload: ImageIn, background: BackgroundTasks) -> dict:
    logger.info("Image from %s: reason=%s %dx%d",
                payload.device_id, payload.reason, payload.width, payload.height)

    if payload.reason != "requested":
        return {"ok": True, "vlm_scheduled": False}

    signals = await state.latest_signals(payload.device_id)
    if signals is None:
        await state.mark_image_received(payload.device_id)
        return {"ok": True, "vlm_scheduled": False}

    ctx = await state.session_context(payload.device_id)

    # Don't fire the VLM if there's no active session — image may have arrived
    # just after the session ended.
    if not ctx["session_active"]:
        await state.mark_image_received(payload.device_id)
        logger.info("Image for %s received outside session — skipping VLM",
                    payload.device_id)
        return {"ok": True, "vlm_scheduled": False}

    await state.mark_image_received(payload.device_id)
    background.add_task(_run_vlm_and_queue, payload.device_id,
                        payload.data, signals, ctx)
    return {"ok": True, "vlm_scheduled": True}


async def _run_vlm_and_queue(device_id: str, image_b64: str,
                              signals, ctx: dict) -> None:
    try:
        command = await vlm.run_inference(image_b64, signals, ctx)
        if command is None:
            logger.info("VLM for %s: no nudge needed", device_id)
        else:
            logger.info("VLM for %s -> %s: %s",
                        device_id, command.action, command.text)
            await state.enqueue_command(device_id, command)
    finally:
        await state.mark_vlm_completed(device_id)


# ─────────────────────────────────────────────────────────
# COMMANDS (poll)
# ─────────────────────────────────────────────────────────

@app.get("/commands", response_model=CommandsOut)
async def commands_out(device_id: str) -> CommandsOut:
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id required")
    request_image = await state.should_request_image(device_id)
    commands = await state.drain_commands(device_id)
    return CommandsOut(request_image=request_image, commands=commands)


# ─────────────────────────────────────────────────────────
# SESSION BOUNDARY (called by decision_node)
# ─────────────────────────────────────────────────────────

@app.post("/session")
async def session_event(payload: SessionEventIn) -> dict:
    """Receive session lifecycle events from the decision node.

    The decision node POSTs here whenever a session starts, ends, pauses,
    or resumes. The server uses this to reset its trigger state machine and
    to gate VLM calls correctly.
    """
    logger.info("Session event from %s: event=%s",
                payload.device_id, payload.event)
    await state.on_session_event(
        payload.device_id,
        payload.event,
        duration_mins=payload.duration_mins,
        elapsed_secs=payload.elapsed_secs,
    )
    return {"ok": True, "event": payload.event}


# ─────────────────────────────────────────────────────────
# VOICE COMMAND PARSING (called by decision_node)
# ─────────────────────────────────────────────────────────

@app.post("/parse_command", response_model=ParseCommandOut)
async def parse_command(payload: ParseCommandIn) -> ParseCommandOut:
    """Interpret a free-form voice command using the LLM.

    Called by the decision node when its local CommandParser can't
    resolve the command unambiguously (e.g. 'let's do a pomodoro',
    'I need to focus for about half an hour', etc.).

    Returns a structured ParseCommandOut with action + params.
    The decision node uses this to drive session management.
    """
    logger.info("parse_command from %s: %r", payload.device_id, payload.text)
    result = await vlm.parse_voice_command(
        text=payload.text,
        session_active=payload.session_active,
        session_paused=payload.session_paused,
        elapsed_secs=payload.elapsed_secs,
        fatigue_context=payload.fatigue_context,
    )
    logger.info("parse_command result: action=%s params=%s",
                result.action, result.params)
    return result


# ─────────────────────────────────────────────────────────
# DEBUG
# ─────────────────────────────────────────────────────────

@app.get("/debug/state/{device_id}")
async def debug_state(device_id: str) -> dict:
    device = await state.registry.get(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="unknown device")
    return {
        "device_id":            device.device_id,
        "session_active":       device.session_active,
        "session_elapsed_mins": round(state._session_elapsed(device) / 60.0, 1),
        "intervention_count":   device.intervention_count,
        "history_len":          len(device.history),
        "trigger_streak_start": device.trigger_streak_start,
        "awaiting_image":       device.awaiting_image,
        "last_vlm_at":          device.last_vlm_at,
        "pending_commands": [
            {"queued_at": q, "command": c.model_dump()}
            for (q, c) in device.pending_commands
        ],
        "latest_signals": (
            device.history[-1].signals.model_dump()
            if device.history else None
        ),
    }


@app.post("/debug/force_request/{device_id}")
async def debug_force_request(device_id: str) -> dict:
    device = await state.registry.get_or_create(device_id)
    device.awaiting_image = True
    return {"ok": True}
