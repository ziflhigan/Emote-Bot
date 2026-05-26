"""VLM interaction — fatigue-triggered nudges + voice command parsing.

Two public functions:
  run_inference()      — given image + signals, decide if/what to say
  parse_voice_command() — given free-form text + context, return structured action

CHANGES FROM PREVIOUS VERSION:
  - run_inference() prompt now includes session duration and intervention count.
  - New parse_voice_command() function handles the /parse_command endpoint.
    Uses a separate lightweight prompt; no image needed.
"""
import json
import logging
from typing import Optional

from ollama import AsyncClient

from . import config
from .schemas import Command, FatigueContext, ParseCommandOut, Signals

logger = logging.getLogger(__name__)

_client = AsyncClient(
    host=config.OLLAMA_HOST,
    timeout=None,   # wait indefinitely — Pi 5 CPU inference can be slow
)


# ─────────────────────────────────────────────────────────
# FATIGUE NUDGE INFERENCE
# ─────────────────────────────────────────────────────────

_NUDGE_SYSTEM = """You are a gentle wellness assistant observing a user during a focus session.

You will be given:
- A photo of the user at their workspace
- Sensor signals describing detected fatigue and posture
- Session context: how long the user has been working and how many reminders they have already received

Your job: decide if the user needs a short verbal nudge, and if so what to say.

Respond ONLY with valid JSON in exactly this form:
  {"speak": true,  "text": "<one short sentence, under 20 words, warm and non-alarming>"}
  {"speak": false, "text": ""}

Rules:
- speak=false if the user looks fine or signals are likely a false alarm (looking at notebook, not actually asleep)
- speak=true if they genuinely look tired, distracted, eyes closed, or slumped
- Never alarming. Never repeat the same phrase if intervention_count > 1.
- If intervention_count >= 3 and fatigue is still high, suggest ending the session.
- Keep messages brief and kind.

Good examples:
  "Looks like a good moment for a short break."
  "Your posture is drifting — a quick stretch might help."
  "You've been at this for a while. How about a five-minute pause?"
  "You look quite tired. It might be worth ending the session for today."
"""


def _summarize_signals(signals: Signals, session_ctx: dict) -> str:
    parts: list[str] = []

    if signals.fatigue_level is not None:
        labels = {0: "ALERT", 1: "MILD", 2: "MODERATE", 3: "SEVERE"}
        parts.append("fatigue=%s" % labels.get(signals.fatigue_level, "?"))

    ef = signals.extra_fields
    for key in ("fatigue_score", "perclos", "ear", "face_absent_secs"):
        if ef.get(key) is not None:
            parts.append("%s=%.2f" % (key, ef[key]))

    if ef.get("m6_head_down"):
        parts.append("head_down=True")
    if ef.get("m6_posture_score") is not None:
        parts.append("posture_score=%.2f" % ef["m6_posture_score"])
    if ef.get("m2_user_present") is not None:
        parts.append("user_present=%s" % ef["m2_user_present"])
    if ef.get("m2_consecutive_eyes_missing"):
        parts.append("eyes_missing_frames=%d" % ef["m2_consecutive_eyes_missing"])

    # Session context.
    parts.append("session_elapsed_mins=%.1f" % session_ctx.get("elapsed_mins", 0))
    parts.append("interventions_so_far=%d" % session_ctx.get("intervention_count", 0))

    return ", ".join(parts) if parts else "(no signals)"


def _parse_nudge_response(raw: str) -> Optional[Command]:
    text = raw.strip().strip("`")
    if text.startswith("json"):
        text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            logger.warning("VLM reply not JSON: %r", raw[:200])
            return None
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            logger.warning("VLM reply unparseable: %r", raw[:200])
            return None

    if not isinstance(data, dict) or not data.get("speak"):
        return None
    msg = (data.get("text") or "").strip()
    if not msg:
        return None
    return Command(action="speak", text=msg)


async def run_inference(image_b64: str, signals: Signals,
                        session_ctx: dict) -> Optional[Command]:
    """Run VLM fatigue nudge inference. Returns a Command or None."""
    summary = _summarize_signals(signals, session_ctx)
    user_prompt = (
        "Sensor signals: %s\n\n"
        "Look at the photo and decide if the user needs a nudge. "
        "Reply with the JSON format."
    ) % summary

    try:
        response = await _client.chat(
            model=config.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": _NUDGE_SYSTEM},
                {"role": "user",   "content": user_prompt,
                 "images": [image_b64]},
            ],
            options={"temperature": 0.3},
            think=False,
            keep_alive=-1,
        )
    except Exception as exc:
        logger.exception("VLM nudge call failed: %s", exc)
        return None

    raw = response.message.content or ""
    logger.info("VLM nudge reply: %s", raw[:300])
    return _parse_nudge_response(raw)


# ─────────────────────────────────────────────────────────
# VOICE COMMAND PARSING
# ─────────────────────────────────────────────────────────

_PARSE_SYSTEM = """You are a command parser for a focus-session robot assistant.

The user has spoken a command (wake word already removed). Your job is to
interpret it and return a structured action.

Valid actions:
  start_session   params: {"duration_mins": <int or null>}
  end_session     params: {}
  pause_session   params: {}
  resume_session  params: {}
  status          params: {}
  dismiss         params: {}
  unknown         params: {}   (use when the command doesn't fit any above)

Respond ONLY with valid JSON:
  {"action": "<action>", "params": {<params>}, "response_text": "<optional short TTS ack>"}

Examples:
  "start a pomodoro"        -> {"action": "start_session", "params": {"duration_mins": 25}, "response_text": "Starting a 25-minute pomodoro session."}
  "let's work for an hour"  -> {"action": "start_session", "params": {"duration_mins": 60}, "response_text": "Starting a 60-minute session."}
  "I'm done for today"      -> {"action": "end_session",   "params": {}, "response_text": "Ending your session. Great work!"}
  "how long have I been on" -> {"action": "status",        "params": {}, "response_text": null}
  "never mind"              -> {"action": "dismiss",       "params": {}, "response_text": "Noted."}
  "play some music"         -> {"action": "unknown",       "params": {}, "response_text": "Sorry, I cannot help with that."}
"""


def _parse_command_response(raw: str) -> Optional[ParseCommandOut]:
    text = raw.strip().strip("`")
    if text.startswith("json"):
        text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            logger.warning("parse_command reply not JSON: %r", raw[:200])
            return None
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None

    if not isinstance(data, dict):
        return None
    return ParseCommandOut(
        action=data.get("action", "unknown"),
        params=data.get("params", {}),
        response_text=data.get("response_text"),
    )


async def parse_voice_command(
        text: str,
        session_active: bool,
        session_paused: bool,
        elapsed_secs: float,
        fatigue_context: Optional[FatigueContext],
) -> ParseCommandOut:
    """Ask the LLM to interpret a free-form voice command.
    Returns ParseCommandOut; never raises (falls back to 'unknown')."""

    fatigue_str = ""
    if fatigue_context:
        fatigue_str = " (current fatigue: %s)" % (
            fatigue_context.fatigue_label or
            ("level %d" % fatigue_context.fatigue_level
             if fatigue_context.fatigue_level is not None else "unknown")
        )

    context_line = "Session state: %s. Elapsed: %.0f mins.%s" % (
        "active" if session_active else ("paused" if session_paused else "idle"),
        elapsed_secs / 60.0,
        fatigue_str,
    )

    user_prompt = 'Context: %s\n\nUser said: "%s"\n\nParse into a structured action.' \
                  % (context_line, text)

    try:
        response = await _client.chat(
            model=config.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": _PARSE_SYSTEM},
                {"role": "user",   "content": user_prompt},
            ],
            options={"temperature": 0.1},
            think=False,
            keep_alive=-1,
        )
    except Exception as exc:
        logger.exception("parse_voice_command failed: %s", exc)
        return ParseCommandOut(action="unknown", params={},
                               response_text="Sorry, I could not process that.")

    raw = response.message.content or ""
    logger.info("parse_command reply: %s", raw[:300])
    result = _parse_command_response(raw)
    if result is None:
        return ParseCommandOut(action="unknown", params={},
                               response_text="Sorry, I did not understand.")
    return result
