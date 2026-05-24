"""Server configuration. All values overridable via env vars."""
import os


def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


# Ollama connection (set by docker-compose).
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5-64k:0.8b")

# How long the VLM call is allowed to take before we give up.
OLLAMA_TIMEOUT_SECS = _env_float("OLLAMA_TIMEOUT_SECS", 60.0)

# Per-device telemetry history.
TELEMETRY_HISTORY_LEN = _env_int("TELEMETRY_HISTORY_LEN", 60)

# How long a trigger condition must hold continuously before we fire the VLM.
# "Tens of seconds" intervention timescale from the user.
TRIGGER_SUSTAIN_SECS = _env_float("TRIGGER_SUSTAIN_SECS", 10.0)

# Minimum gap between VLM invocations on the same device.
COOLDOWN_SECS = _env_float("COOLDOWN_SECS", 30.0)

# Thresholds. Trigger if ANY of these conditions hold continuously.
FATIGUE_LEVEL_TRIGGER = _env_int("FATIGUE_LEVEL_TRIGGER", 2)  # MODERATE+
EYES_MISSING_TRIGGER = _env_int("EYES_MISSING_TRIGGER", 30)  # frames

# Time-to-live for queued commands. If the bridge never polls, drop after this.
COMMAND_TTL_SECS = _env_float("COMMAND_TTL_SECS", 60.0)
