"""VLM interaction.

Given an image + a snapshot of the user's state signals, ask the model
what to say (if anything). The model's job is qualitative interpretation;
the numeric signals already told us *something* is up.
"""
import json
import logging
from typing import Optional

from ollama import AsyncClient

from . import config
from .schemas import Command, Signals

logger = logging.getLogger(__name__)

_client = AsyncClient(host=config.OLLAMA_HOST, timeout=config.OLLAMA_TIMEOUT_SECS)


SYSTEM_PROMPT = """You are a gentle wellness assistant observing a user during a focus session.

You will be given:
- A photo of the user at their workspace
- Numeric signals from sensors describing what the cameras have detected

Your job: decide if the user needs a short verbal nudge, and if so, what to say.

Respond ONLY with valid JSON in exactly this form:

  {"speak": true,  "text": "<one short sentence, under 20 words, warm and non-alarming>"}
  {"speak": false, "text": ""}

Choose speak=false if the user looks fine and the signals are likely a false alarm
(e.g. they're just looking down at a notebook, not actually fatigued).
Choose speak=true if they genuinely look tired, distracted, or absent.

Keep the message brief, kind, and never alarming. Examples of good messages:
  "Looks like a good moment for a short break."
  "Your posture is drifting — a quick stretch might help."
  "Take a breath; you've been at this a while."
"""


def _summarize_signals(signals: Signals) -> str:
    """Compact, human-readable summary of the current signals."""
    parts: list[str] = []

    if signals.fatigue_level is not None:
        labels = {0: "ALERT", 1: "MILD", 2: "MODERATE", 3: "SEVERE"}
        parts.append("fatigue=%s" % labels.get(signals.fatigue_level, "?"))
    if signals.session_active is not None:
        parts.append("session_active=%s" % signals.session_active)
    if signals.user_state:
        us = signals.user_state
        parts.append("user_present=%s" % us.user_present)
        if us.consecutive_eyes_missing:
            parts.append("eyes_missing_frames=%d" % us.consecutive_eyes_missing)
        if us.consecutive_face_absent:
            parts.append("face_absent_frames=%d" % us.consecutive_face_absent)
    if signals.head_posture:
        hp = signals.head_posture
        parts.append("head_down=%s" % hp.head_down)
        parts.append("posture_score=%.2f" % hp.posture_score)
        if not hp.pose_visible:
            parts.append("pose_not_visible")

    return ", ".join(parts) if parts else "(no signals yet)"


def _parse_response(raw: str) -> Optional[Command]:
    """Parse the model's JSON reply. Returns None on any failure or if the
    model elected not to speak."""
    # Strip code fences if the model wrapped its reply.
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON object in the response.
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            logger.warning("VLM reply not JSON: %r", raw[:200])
            return None
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            logger.warning("VLM reply not parseable: %r", raw[:200])
            return None

    if not isinstance(data, dict) or not data.get("speak"):
        return None

    msg = (data.get("text") or "").strip()
    if not msg:
        return None

    return Command(action="speak", text=msg)


async def run_inference(image_b64: str, signals: Signals) -> Optional[Command]:
    """Invoke the VLM. Returns a Command to enqueue, or None to stay silent."""
    signals_summary = _summarize_signals(signals)
    user_prompt = (
        "Sensor signals right now: %s\n\n"
        "Look at the attached photo and decide if the user needs a nudge. "
        "Respond with the JSON format described."
    ) % signals_summary

    try:
        response = await _client.chat(
            model=config.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": user_prompt,
                    "images": [image_b64],
                },
            ],
            options={"temperature": 0.3},
        )
    except Exception as exc:
        logger.exception("VLM call failed: %s", exc)
        return None

    raw = response.get("message", {}).get("content", "")
    logger.info("VLM raw reply: %s", raw[:300])
    return _parse_response(raw)
