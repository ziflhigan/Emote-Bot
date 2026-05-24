"""FastAPI entrypoint.

Three endpoints serve the bridge:
  POST /telemetry  — bridge pushes lightweight signals (~1 Hz)
  POST /image      — bridge pushes a JPEG (heartbeat or on request)
  GET  /commands   — bridge polls for things to do (~0.2 Hz)

Plus a few utilities for debugging / health checks.
"""
import logging

from fastapi import BackgroundTasks, FastAPI, HTTPException

from . import config, state, vlm
from .schemas import CommandsOut, ImageIn, TelemetryIn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("vlm-server")

app = FastAPI(title="VLM Wellness Server")


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "model": config.OLLAMA_MODEL,
        "ollama_host": config.OLLAMA_HOST,
        "devices": await state.registry.all_ids(),
    }


@app.post("/telemetry")
async def telemetry_in(payload: TelemetryIn) -> dict:
    """Bridge -> server. Returns fast; no blocking work here."""
    should_request = await state.ingest_telemetry(payload)
    if should_request:
        logger.info(
            "Device %s: trigger sustained for %.1fs — requesting image",
            payload.device_id, config.TRIGGER_SUSTAIN_SECS,
        )
    return {"ok": True, "request_image": should_request}


@app.post("/image")
async def image_in(payload: ImageIn, background: BackgroundTasks) -> dict:
    """Bridge -> server. If the image was requested (not just a heartbeat),
    schedule a VLM run in the background so this endpoint returns immediately."""
    logger.info(
        "Image from %s: reason=%s size=%dx%d bytes=%d",
        payload.device_id, payload.reason,
        payload.width, payload.height, len(payload.data),
    )

    if payload.reason != "requested":
        return {"ok": True, "vlm_scheduled": False}

    signals = await state.latest_signals(payload.device_id)
    if signals is None:
        # Image arrived before any telemetry — odd but harmless.
        await state.mark_image_received(payload.device_id)
        return {"ok": True, "vlm_scheduled": False}

    # Clear the awaiting-image flag so subsequent polls don't keep asking.
    await state.mark_image_received(payload.device_id)

    background.add_task(_run_vlm_and_queue,
                        payload.device_id, payload.data, signals)
    return {"ok": True, "vlm_scheduled": True}


async def _run_vlm_and_queue(device_id: str, image_b64: str, signals) -> None:
    """Background task: invoke the model, queue the result for delivery."""
    try:
        command = await vlm.run_inference(image_b64, signals)
        if command is None:
            logger.info("VLM for %s: no nudge needed", device_id)
        else:
            logger.info("VLM for %s -> %s: %s",
                        device_id, command.action, command.text)
            await state.enqueue_command(device_id, command)
    finally:
        # Always stamp cooldown, even on failure, to avoid hammering Ollama.
        await state.mark_vlm_completed(device_id)


@app.get("/commands", response_model=CommandsOut)
async def commands_out(device_id: str) -> CommandsOut:
    """Server -> bridge. Returns any pending commands plus the request_image
    flag, and clears the queue."""
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id required")

    request_image = await state.should_request_image(device_id)
    commands = await state.drain_commands(device_id)
    return CommandsOut(request_image=request_image, commands=commands)


# ─────────────────────────────────────────────────────────
# DEBUG ENDPOINTS — useful while bringing up the system
# ─────────────────────────────────────────────────────────

@app.get("/debug/state/{device_id}")
async def debug_state(device_id: str) -> dict:
    device = await state.registry.get(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="unknown device")
    return {
        "device_id": device.device_id,
        "history_len": len(device.history),
        "trigger_streak_start": device.trigger_streak_start,
        "awaiting_image": device.awaiting_image,
        "last_vlm_at": device.last_vlm_at,
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
    """Force the server to ask for an image on the next /commands poll —
    useful for testing the VLM path without waiting for a real trigger."""
    device = await state.registry.get_or_create(device_id)
    device.awaiting_image = True
    return {"ok": True}
