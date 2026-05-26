#!/usr/bin/env python3
"""
ROS -> Server bridge node.

Target: ROS Noetic on Ubuntu 20.04 (Python 3.8).

CHANGES FROM PREVIOUS VERSION:
  - Now subscribes to /focus_robot/fatigue_summary (the JSON topic published
    by fatigue_node) instead of individual fatigue/user_state/head_posture
    topics — the summary already contains all of those fields, so there is
    no need to hold separate subscriptions. This also means the bridge no
    longer depends on vision_presence_module or head_posture_module message
    types at import time.
  - Subscribes to /focus_robot/session_active (Bool) so the server always
    knows whether a session is in progress.
  - Server commands (from GET /commands) are now re-published on
    /focus_robot/server_command (std_msgs/String, JSON) so the decision
    node can react to them. The bridge is the transport; it no longer
    needs to know what the commands mean.

HTTP endpoints:
  POST /telemetry   every TELEMETRY_PERIOD seconds
  POST /image       every IMAGE_PERIOD seconds (heartbeat + on-demand)
  GET  /commands    every COMMAND_POLL_PERIOD seconds
"""

import base64
import json
import threading

import cv2
import requests
import rospy
from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, String


# ─────────────────────────────────────────────────────────
# CONFIG (all overridable via ROS params)
# ─────────────────────────────────────────────────────────
DEFAULTS = {
    "server_url":            "http://raspberrypi.local:8000",
    "device_id":             "robot-01",

    # Topics to subscribe to.
    "fatigue_summary_topic": "/focus_robot/fatigue_summary",
    "session_active_topic":  "/focus_robot/session_active",
    "image_topic":           "/usb_cam/image_raw",

    # Topic to publish server commands onto (decision_node reads this).
    "server_command_topic":  "/focus_robot/server_command",

    # Cadence.
    "telemetry_period":      1.0,
    "image_period":          15.0,
    "command_poll_period":   5.0,

    # Image encoding.
    "image_max_width":       640,
    "image_jpeg_quality":    80,

    # HTTP behaviour.
    "http_timeout":          3.0,
    "http_log_failures":     True,
}


class ServerBridge:

    def __init__(self):
        rospy.init_node("server_bridge")
        rospy.on_shutdown(self._on_shutdown)

        self.cfg = {k: rospy.get_param("~" + k, v) for k, v in DEFAULTS.items()}
        rospy.loginfo("ServerBridge config: %s", json.dumps(self.cfg, indent=2))

        self.bridge = CvBridge()
        self.session = requests.Session()
        self._http_lock = threading.Lock()

        self._seq = 0
        self._seq_lock = threading.Lock()

        self._state_lock = threading.Lock()
        self._latest = {
            # Full fatigue_summary JSON dict (from fatigue_node).
            "fatigue_summary":   None,
            # From decision_node.
            "session_active":    None,
            # Raw sensor_msgs/Image, stashed for encode-on-demand.
            "latest_image_msg":  None,
        }

        # ── Publisher: server commands -> decision node ──
        self._pub_server_cmd = rospy.Publisher(
            self.cfg["server_command_topic"], String,
            queue_size=10)

        # ── Subscribers ──
        rospy.Subscriber(
            self.cfg["fatigue_summary_topic"], String,
            self._on_fatigue_summary, queue_size=1)

        rospy.Subscriber(
            self.cfg["session_active_topic"], Bool,
            self._on_session_active, queue_size=1)

        rospy.Subscriber(
            self.cfg["image_topic"], Image,
            self._on_image, queue_size=1,
            buff_size=2 ** 24)

        # ── Timers ──
        rospy.Timer(rospy.Duration(self.cfg["telemetry_period"]),
                    self._tick_telemetry)
        rospy.Timer(rospy.Duration(self.cfg["image_period"]),
                    self._tick_image)
        rospy.Timer(rospy.Duration(self.cfg["command_poll_period"]),
                    self._tick_commands)

        rospy.loginfo("ServerBridge started; talking to %s",
                      self.cfg["server_url"])
        rospy.loginfo("  Fatigue summary : %s",
                      self.cfg["fatigue_summary_topic"])
        rospy.loginfo("  Session active  : %s",
                      self.cfg["session_active_topic"])
        rospy.loginfo("  Server commands : %s",
                      self.cfg["server_command_topic"])

    # ──────────────────────────────────────
    # SUBSCRIBER CALLBACKS
    # ──────────────────────────────────────

    def _on_fatigue_summary(self, msg):
        """Parse the fatigue_summary JSON and stash it.
        Latest-wins — we only ever send the most recent snapshot."""
        try:
            data = json.loads(msg.data)
        except (ValueError, TypeError):
            rospy.logwarn_throttle(10.0, "Bad fatigue_summary JSON")
            return
        with self._state_lock:
            self._latest["fatigue_summary"] = data

    def _on_session_active(self, msg):
        with self._state_lock:
            self._latest["session_active"] = bool(msg.data)

    def _on_image(self, msg):
        with self._state_lock:
            self._latest["latest_image_msg"] = msg

    # ──────────────────────────────────────
    # TIMERS
    # ──────────────────────────────────────

    def _tick_telemetry(self, _event):
        with self._state_lock:
            summary  = self._latest["fatigue_summary"]
            sess_act = self._latest["session_active"]

        # Build signals dict for the server. The fatigue_summary already
        # has everything (fatigue_level, score, EAR, PERCLOS, m2/m6 fields),
        # so we embed it wholesale plus the session flag which the decision
        # node owns and fatigue_node no longer publishes.
        signals = {}
        if summary is not None:
            signals.update(summary)
        signals["session_active"] = sess_act

        payload = {
            "device_id": self.cfg["device_id"],
            "sequence":  self._next_seq(),
            "timestamp": rospy.Time.now().to_sec(),
            "signals":   signals,
        }
        response = self._post_json("/telemetry", payload)
        if isinstance(response, dict) and response.get("request_image"):
            self._send_image(reason="requested")

    def _tick_image(self, _event):
        self._send_image(reason="heartbeat")

    def _tick_commands(self, _event):
        try:
            with self._http_lock:
                r = self.session.get(
                    self.cfg["server_url"] + "/commands",
                    params={"device_id": self.cfg["device_id"]},
                    timeout=self.cfg["http_timeout"],
                )
            if r.status_code != 200:
                if self.cfg["http_log_failures"]:
                    rospy.logwarn_throttle(
                        10.0, "GET /commands -> %d", r.status_code)
                return
            data = r.json()
        except Exception as exc:
            if self.cfg["http_log_failures"]:
                rospy.logwarn_throttle(10.0, "GET /commands failed: %s", exc)
            return

        if isinstance(data, dict) and data.get("request_image"):
            self._send_image(reason="requested")

        commands = data.get("commands") if isinstance(data, dict) else None
        if commands:
            for cmd in commands:
                self._relay_command(cmd)

    # ──────────────────────────────────────
    # IMAGE SENDING
    # ──────────────────────────────────────

    def _send_image(self, reason):
        with self._state_lock:
            img_msg = self._latest["latest_image_msg"]
        if img_msg is None:
            rospy.logdebug("no image yet — skipping (%s)", reason)
            return

        try:
            cv_img = self.bridge.imgmsg_to_cv2(img_msg, "bgr8")
        except CvBridgeError as exc:
            rospy.logwarn("cv_bridge error: %s", exc)
            return

        h, w = cv_img.shape[:2]
        max_w = int(self.cfg["image_max_width"])
        if w > max_w:
            scale = max_w / float(w)
            cv_img = cv2.resize(cv_img, (max_w, int(h * scale)),
                                interpolation=cv2.INTER_AREA)

        ok, jpeg = cv2.imencode(
            ".jpg", cv_img,
            [int(cv2.IMWRITE_JPEG_QUALITY), int(self.cfg["image_jpeg_quality"])])
        if not ok:
            rospy.logwarn("JPEG encode failed")
            return

        payload = {
            "device_id": self.cfg["device_id"],
            "sequence":  self._next_seq(),
            "timestamp": rospy.Time.now().to_sec(),
            "reason":    reason,
            "encoding":  "jpeg",
            "width":     cv_img.shape[1],
            "height":    cv_img.shape[0],
            "data":      base64.b64encode(jpeg.tobytes()).decode("ascii"),
        }
        self._post_json("/image", payload)

    # ──────────────────────────────────────
    # COMMAND RELAY
    # ──────────────────────────────────────

    def _relay_command(self, cmd):
        """Re-publish the server command as JSON on /focus_robot/server_command.
        The decision node owns all logic about what to do with it — the bridge
        is pure transport."""
        if not isinstance(cmd, dict):
            rospy.logwarn("ignoring non-dict command: %s", cmd)
            return
        action = cmd.get("action", "")
        if action == "none":
            return
        try:
            self._pub_server_cmd.publish(String(data=json.dumps(cmd)))
            rospy.loginfo("Relayed server command: %s", action)
        except Exception as exc:
            rospy.logwarn("relay_command publish failed: %s", exc)

    # ──────────────────────────────────────
    # HTTP HELPERS
    # ──────────────────────────────────────

    def _post_json(self, path, payload):
        url = self.cfg["server_url"] + path
        try:
            with self._http_lock:
                r = self.session.post(
                    url, json=payload, timeout=self.cfg["http_timeout"])
            if r.status_code >= 400:
                if self.cfg["http_log_failures"]:
                    rospy.logwarn_throttle(
                        10.0, "POST %s -> %d", path, r.status_code)
                return None
            try:
                return r.json()
            except ValueError:
                return None
        except Exception as exc:
            if self.cfg["http_log_failures"]:
                rospy.logwarn_throttle(
                    10.0, "POST %s failed: %s", path, exc)
            return None

    def _next_seq(self):
        with self._seq_lock:
            self._seq += 1
            return self._seq

    def _on_shutdown(self):
        rospy.loginfo("ServerBridge shutting down")
        try:
            self.session.close()
        except Exception:
            pass


def main():
    ServerBridge()
    rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
