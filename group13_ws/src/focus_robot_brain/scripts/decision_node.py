#!/usr/bin/env python3
"""
decision_node.py
================

FOCUS ROBOT BRAIN — SESSION MANAGER + LLM DECISION NODE

This is the integration hub of the focus robot. It:

  1. Listens to /voice_command for session control phrases
     ("start session", "start session for 15 minutes", "end session", etc.)
     and sends natural-language commands to the server LLM for structured
     interpretation — handling any phrasing the user might use.

  2. Manages session state: publishes /focus_robot/session_active (Bool),
     /focus_robot/session_duration_secs (Float32), and tracks session
     elapsed time, pause state, and intervention count.

  3. Subscribes to /focus_robot/fatigue_summary (the JSON topic published
     by fatigue_node) and forwards it to the server bridge — this is the
     telemetry the server uses to decide if/when to trigger the VLM.

  4. Receives command responses from the server (via the bridge's
     /focus_robot/server_command topic) and dispatches them:
       - "speak"         -> /tts_request
       - "end_session"   -> triggers local session end
       - "warn_severe"   -> speaks + flags session for early termination

TOPIC CONTRACT
  Subscribes:
    /voice_command                  std_msgs/String     from voice_command.py
    /focus_robot/fatigue_summary    std_msgs/String     JSON from fatigue_node
    /focus_robot/server_command     std_msgs/String     JSON from bridge node

  Publishes:
    /focus_robot/session_active         std_msgs/Bool
    /focus_robot/session_duration_secs  std_msgs/Float32   planned duration
    /focus_robot/session_elapsed_secs   std_msgs/Float32   current elapsed
    /tts_request                        std_msgs/String

RELATIONSHIP TO BRIDGE NODE
  The bridge node (server_bridge_node.py) handles:
    - POST /telemetry to the FastAPI server (from fatigue_summary)
    - POST /image periodically
    - GET  /commands and re-publishing server commands to /focus_robot/server_command

  This node does NOT call the server for telemetry. It only calls the server
  directly for voice command parsing (POST /parse_command).

ROS Noetic — Python 3.8 — Ubuntu 20.04
"""

import json
import threading
import time

import requests
import rospy
from std_msgs.msg import Bool, Float32, String


# ─────────────────────────────────────────────────────────
# COMMAND PARSING
# ─────────────────────────────────────────────────────────

class CommandParser:
    """
    Fast local pre-parse before hitting the LLM.

    Catches unambiguous short commands locally (start, end, pause, resume,
    status, dismiss) to avoid network round-trips for simple cases.
    Anything that looks like natural language or has a duration goes to LLM.
    """

    # Tokens that clearly signal session start regardless of surrounding words.
    START_TOKENS   = {"start", "begin", "launch", "go", "focus"}
    END_TOKENS     = {"end", "stop", "finish", "quit", "done"}
    PAUSE_TOKENS   = {"pause", "hold", "wait"}
    RESUME_TOKENS  = {"resume", "continue", "unpause", "back"}
    STATUS_TOKENS  = {"status", "how", "time", "progress", "report"}
    DISMISS_TOKENS = {"dismiss", "ok", "okay", "got it", "understood"}

    def local_parse(self, text):
        """
        Returns (action, params) or (None, None) if should escalate to LLM.

        action is one of:
          start_session   params = {"duration_mins": int or None}
          end_session     params = {}
          pause_session   params = {}
          resume_session  params = {}
          status          params = {}
          dismiss         params = {}
          None            -> send to LLM
        """
        t = text.lower().strip()
        words = set(t.split())

        # Dismiss — always local
        if words & self.DISMISS_TOKENS:
            return "dismiss", {}

        # Status — always local
        if words & self.STATUS_TOKENS and not words & self.START_TOKENS:
            return "status", {}

        # Pause / resume — always local
        if words & self.PAUSE_TOKENS:
            return "pause_session", {}
        if words & self.RESUME_TOKENS:
            return "resume_session", {}

        # End — always local
        if words & self.END_TOKENS and "session" in t:
            return "end_session", {}

        # Start — check for duration hint
        if words & self.START_TOKENS:
            duration = self._extract_duration(t)
            # If user said something elaborate like "start a deep work session
            # for 25 minutes with reminders every 10" -> escalate to LLM
            if len(words) > 6 and duration is None:
                return None, None  # escalate
            return "start_session", {"duration_mins": duration}

        # Anything else: escalate
        return None, None

    @staticmethod
    def _extract_duration(text):
        """Pull the first number followed by 'minute(s)' or 'min' from text."""
        import re
        m = re.search(r"(\d+)\s*(?:minute|minutes|min|mins)", text)
        if m:
            return int(m.group(1))
        m = re.search(r"(\d+)\s*(?:hour|hours|hr|hrs)", text)
        if m:
            return int(m.group(1)) * 60
        return None


# ─────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────

class SessionState:
    IDLE    = "idle"
    ACTIVE  = "active"
    PAUSED  = "paused"

    def __init__(self):
        self.state = self.IDLE
        self.started_at     = None   # wall-clock seconds
        self.paused_at      = None
        self.paused_elapsed = 0.0    # accumulated seconds before current pause
        self.duration_mins  = None   # None = no limit
        self.intervention_count = 0

    @property
    def active(self):
        return self.state == self.ACTIVE

    @property
    def paused(self):
        return self.state == self.PAUSED

    @property
    def idle(self):
        return self.state == self.IDLE

    def start(self, duration_mins=None):
        self.state = self.ACTIVE
        self.started_at = time.time()
        self.paused_at = None
        self.paused_elapsed = 0.0
        self.duration_mins = duration_mins
        self.intervention_count = 0

    def pause(self):
        if self.state != self.ACTIVE:
            return False
        self.state = self.PAUSED
        self.paused_at = time.time()
        return True

    def resume(self):
        if self.state != self.PAUSED:
            return False
        self.paused_elapsed += time.time() - self.paused_at
        self.paused_at = None
        self.state = self.ACTIVE
        return True

    def end(self):
        self.state = self.IDLE
        self.started_at = None
        self.paused_at = None
        self.paused_elapsed = 0.0
        self.duration_mins = None
        self.intervention_count = 0

    def elapsed_secs(self):
        if self.started_at is None:
            return 0.0
        if self.state == self.PAUSED:
            return (self.paused_at - self.started_at) - self.paused_elapsed
        return (time.time() - self.started_at) - self.paused_elapsed

    def remaining_secs(self):
        if self.duration_mins is None:
            return None
        return max(0.0, self.duration_mins * 60.0 - self.elapsed_secs())

    def is_overtime(self):
        rem = self.remaining_secs()
        return rem is not None and rem <= 0.0

    def elapsed_display(self):
        secs = int(self.elapsed_secs())
        m, s = divmod(secs, 60)
        return "%d:%02d" % (m, s)


# ─────────────────────────────────────────────────────────
# MAIN NODE
# ─────────────────────────────────────────────────────────

class DecisionNode:

    # Topics this node owns.
    PUB_SESSION_ACTIVE   = "/focus_robot/session_active"
    PUB_SESSION_DURATION = "/focus_robot/session_duration_secs"
    PUB_SESSION_ELAPSED  = "/focus_robot/session_elapsed_secs"
    PUB_TTS              = "/tts_request"

    # Topics this node reads.
    SUB_VOICE_CMD        = "/voice_command"
    SUB_FATIGUE_SUMMARY  = "/focus_robot/fatigue_summary"
    SUB_SERVER_CMD       = "/focus_robot/server_command"

    def __init__(self):
        rospy.init_node("decision_node")
        rospy.on_shutdown(self._on_shutdown)

        # Config.
        self._server_url   = rospy.get_param("~server_url",
                                             "http://raspberrypi.local:8000")
        self._device_id    = rospy.get_param("~device_id", "robot-01")
        # No HTTP timeouts — we wait however long the server needs.
        # parse_command can take 30-90s on a Pi 5 CPU; that is fine.
        self._status_period = float(rospy.get_param("~status_period", 5.0))

        # Max session duration allowed without explicit limit (mins).
        # Server can still trigger early-end via command.
        self._max_session_mins = float(rospy.get_param("~max_session_mins", 120.0))

        self._session = SessionState()
        self._parser  = CommandParser()
        self._http    = requests.Session()
        self._http_lock = threading.Lock()

        # Latest fatigue summary — passed to server alongside voice commands
        # so it has context when parsing intent.
        self._latest_summary = {}
        self._summary_lock = threading.Lock()

        # ── Publishers ───────────────────────────────────────────────────
        self._pub_active   = rospy.Publisher(
            self.PUB_SESSION_ACTIVE, Bool, queue_size=1, latch=True)
        self._pub_duration = rospy.Publisher(
            self.PUB_SESSION_DURATION, Float32, queue_size=1, latch=True)
        self._pub_elapsed  = rospy.Publisher(
            self.PUB_SESSION_ELAPSED, Float32, queue_size=1)
        self._pub_tts      = rospy.Publisher(
            self.PUB_TTS, String, queue_size=10)

        # ── Subscribers ──────────────────────────────────────────────────
        rospy.Subscriber(self.SUB_VOICE_CMD, String,
                         self._on_voice_command, queue_size=5)
        rospy.Subscriber(self.SUB_FATIGUE_SUMMARY, String,
                         self._on_fatigue_summary, queue_size=1)
        rospy.Subscriber(self.SUB_SERVER_CMD, String,
                         self._on_server_command, queue_size=10)

        # ── Timers ───────────────────────────────────────────────────────
        # Status publisher — keeps /session_active latched correctly and
        # checks for overtime.
        rospy.Timer(rospy.Duration(self._status_period), self._tick_status)

        # Publish initial idle state so bridge has something to relay.
        self._publish_session_state()

        rospy.loginfo("DecisionNode started. Server: %s", self._server_url)
        rospy.loginfo("  Voice commands : %s", self.SUB_VOICE_CMD)
        rospy.loginfo("  Fatigue input  : %s", self.SUB_FATIGUE_SUMMARY)
        rospy.loginfo("  Server cmds    : %s", self.SUB_SERVER_CMD)

    # ──────────────────────────────────────
    # SUBSCRIBER CALLBACKS
    # ──────────────────────────────────────

    def _on_voice_command(self, msg):
        text = (msg.data or "").strip()
        if not text:
            return
        rospy.loginfo("Voice command received: %r", text)

        action, params = self._parser.local_parse(text)

        if action is None:
            # Local parse inconclusive — ask the LLM server to interpret.
            rospy.loginfo("Escalating to LLM: %r", text)
            action, params = self._llm_parse_command(text)

        if action is None:
            rospy.logwarn("Could not interpret command: %r", text)
            self._say("Sorry, I did not understand that.")
            return

        self._dispatch_action(action, params or {})

    def _on_fatigue_summary(self, msg):
        """Cache the latest fatigue JSON. The bridge reads from its own
        subscriber on the same topic — we just keep a copy for LLM context."""
        try:
            data = json.loads(msg.data)
            with self._summary_lock:
                self._latest_summary = data
        except (ValueError, TypeError):
            pass

    def _on_server_command(self, msg):
        """Commands arriving from the bridge node (relayed from server)."""
        try:
            cmd = json.loads(msg.data)
        except (ValueError, TypeError):
            rospy.logwarn("Bad server command payload: %r", msg.data)
            return

        action = cmd.get("action", "")
        rospy.loginfo("Server command: %s", cmd)

        if action == "speak":
            text = (cmd.get("text") or "").strip()
            if text:
                self._say(text)
                self._session.intervention_count += 1

        elif action == "end_session":
            if self._session.active or self._session.paused:
                text = cmd.get("text") or "Session ending early on recommendation."
                self._say(text)
                rospy.sleep(3.0)
                self._do_end_session()

        elif action == "warn_severe":
            text = cmd.get("text") or "Your fatigue level is severe. Please take a break."
            self._say(text)
            self._session.intervention_count += 1

        elif action == "none":
            pass

        else:
            rospy.logwarn("Unknown server action: %r", action)

    # ──────────────────────────────────────
    # ACTION DISPATCH
    # ──────────────────────────────────────

    def _dispatch_action(self, action, params):
        rospy.loginfo("Dispatching action: %s %s", action, params)

        if action == "start_session":
            self._do_start_session(params.get("duration_mins"))
        elif action == "end_session":
            self._do_end_session()
        elif action == "pause_session":
            self._do_pause()
        elif action == "resume_session":
            self._do_resume()
        elif action == "status":
            self._do_status()
        elif action == "dismiss":
            self._say("Noted.")
        else:
            rospy.logwarn("Unknown action: %r", action)
            self._say("Sorry, I did not understand that.")

    # ──────────────────────────────────────
    # SESSION OPERATIONS
    # ──────────────────────────────────────

    def _do_start_session(self, duration_mins):
        if self._session.active:
            self._say("A session is already running.")
            return
        if self._session.paused:
            # User probably said "start session" when they meant "resume".
            self._do_resume()
            return

        # Clamp to max allowed duration.
        if duration_mins is not None:
            duration_mins = min(duration_mins, self._max_session_mins)

        self._session.start(duration_mins=duration_mins)
        self._publish_session_state()

        # Notify server of new session.
        self._post_session_event("started", duration_mins=duration_mins)

        if duration_mins:
            msg = "Session started. Focus mode is on. Duration: %d minutes." \
                  % duration_mins
        else:
            msg = "Session started. Focus mode is on."
        self._say(msg)
        rospy.loginfo("Session started. duration_mins=%s", duration_mins)

    def _do_end_session(self):
        if self._session.idle:
            self._say("No session is currently active.")
            return

        elapsed = self._session.elapsed_secs()
        count   = self._session.intervention_count
        self._session.end()
        self._publish_session_state()

        # Notify server.
        self._post_session_event("ended",
                                 elapsed_secs=elapsed,
                                 intervention_count=count)

        mins = int(elapsed / 60)
        secs = int(elapsed % 60)
        msg = "Session ended. You worked for %d minutes and %d seconds." \
              % (mins, secs)
        self._say(msg)
        rospy.loginfo("Session ended. elapsed=%.1fs interventions=%d",
                      elapsed, count)

    def _do_pause(self):
        if not self._session.pause():
            self._say("No active session to pause." if self._session.idle
                      else "Session is already paused.")
            return
        self._publish_session_state()
        self._post_session_event("paused",
                                 elapsed_secs=self._session.elapsed_secs())
        self._say("Session paused.")

    def _do_resume(self):
        if not self._session.resume():
            self._say("No paused session to resume." if self._session.idle
                      else "Session is already running.")
            return
        self._publish_session_state()
        self._post_session_event("resumed",
                                 elapsed_secs=self._session.elapsed_secs())
        self._say("Session resumed.")

    def _do_status(self):
        if self._session.idle:
            self._say("No session is currently running.")
            return
        state_word = "paused" if self._session.paused else "running"
        elapsed = self._session.elapsed_secs()
        mins    = int(elapsed / 60)
        secs    = int(elapsed % 60)
        rem     = self._session.remaining_secs()
        if rem is not None:
            rem_mins = int(rem / 60)
            msg = "Session %s. Elapsed: %d minutes %d seconds. " \
                  "Remaining: %d minutes." % (state_word, mins, secs, rem_mins)
        else:
            msg = "Session %s. Elapsed: %d minutes and %d seconds." \
                  % (state_word, mins, secs)
        self._say(msg)

    # ──────────────────────────────────────
    # TIMER TICK
    # ──────────────────────────────────────

    def _tick_status(self, _event):
        """Runs every status_period seconds. Re-publishes elapsed time
        and checks for overtime."""
        if not self._session.idle:
            self._pub_elapsed.publish(Float32(data=self._session.elapsed_secs()))

        # Check if a timed session has run over.
        if self._session.active and self._session.is_overtime():
            rospy.loginfo("Session timer expired — ending automatically.")
            self._say("Your focus session time is up. Great work!")
            rospy.sleep(3.5)
            self._do_end_session()

    # ──────────────────────────────────────
    # LLM COMMAND PARSING (server round-trip)
    # ──────────────────────────────────────

    def _llm_parse_command(self, text):
        """POST natural-language command text to /parse_command.
        Returns (action, params) or (None, None) on failure."""
        with self._summary_lock:
            summary_snapshot = dict(self._latest_summary)

        payload = {
            "device_id":      self._device_id,
            "text":           text,
            "session_active": self._session.active,
            "session_paused": self._session.paused,
            "elapsed_secs":   self._session.elapsed_secs(),
            "fatigue_context": {
                "fatigue_level": summary_snapshot.get("fatigue_level"),
                "fatigue_label": summary_snapshot.get("fatigue_label"),
                "m6_head_down":  summary_snapshot.get("m6_head_down"),
            },
        }
        try:
            with self._http_lock:
                r = self._http.post(
                    self._server_url + "/parse_command",
                    json=payload,
                    timeout=None,
                )
            if r.status_code != 200:
                rospy.logwarn("parse_command -> %d", r.status_code)
                return None, None
            data = r.json()
            action = data.get("action")
            params = data.get("params", {})
            rospy.loginfo("LLM parsed %r -> action=%s params=%s",
                          text, action, params)
            return action, params
        except Exception as exc:
            rospy.logwarn_throttle(10.0, "parse_command failed: %s", exc)
            return None, None

    # ──────────────────────────────────────
    # SESSION EVENT NOTIFICATION
    # ──────────────────────────────────────

    def _post_session_event(self, event_type, **kwargs):
        """Fire-and-forget POST to /session so the server can reset
        its trigger state machine on session boundaries."""
        payload = {
            "device_id":  self._device_id,
            "event":      event_type,
            "timestamp":  time.time(),
        }
        payload.update(kwargs)
        try:
            with self._http_lock:
                r = self._http.post(
                    self._server_url + "/session",
                    json=payload,
                    timeout=None,
                )
            if r.status_code >= 400:
                rospy.logwarn_throttle(
                    10.0, "POST /session -> %d", r.status_code)
        except Exception as exc:
            rospy.logwarn_throttle(10.0, "POST /session failed: %s", exc)

    # ──────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────

    def _say(self, text):
        rospy.loginfo("TTS: %s", text)
        self._pub_tts.publish(String(data=text))

    def _publish_session_state(self):
        self._pub_active.publish(Bool(data=self._session.active))
        duration_secs = (self._session.duration_mins * 60.0
                         if self._session.duration_mins else 0.0)
        self._pub_duration.publish(Float32(data=duration_secs))

    def _on_shutdown(self):
        if not self._session.idle:
            rospy.loginfo("Shutdown during active session — notifying server.")
            self._post_session_event("ended",
                                     elapsed_secs=self._session.elapsed_secs(),
                                     reason="shutdown")
        try:
            self._http.close()
        except Exception:
            pass
        rospy.loginfo("DecisionNode shutting down.")


# ─────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────

def main():
    DecisionNode()
    rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
