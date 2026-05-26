#!/usr/bin/env python3
"""
Fatigue Detection — Data Publisher Node
Member 5 — fatigue_monitor package

Role in integrated system:
  Computes fatigue signals (EAR, PERCLOS, head pitch, face absence).
  Enriches with Member 2 (user state) and Member 6 (head posture).
  Publishes all metrics for LLM brain to consume and act on.
  Does NOT manage sessions — LLM module handles session state.
  Does NOT use SoundClient directly — speech_output_module handles TTS.

TTS integration:
  Default mode:
    LLM brain subscribes to /focus_robot/fatigue_summary
    LLM decides when/what to speak
    LLM publishes speech text to /tts_request

  Standalone fallback mode:
    Run with _local_tts_enabled:=true
    This node publishes simple local intervention messages to /tts_request.
    Since session state is owned by LLM, fallback mode is always-on and
    guarded only by fatigue level and minimum message gap.

Subscribes to:
  /usb_cam/image_raw                 sensor_msgs/Image    own camera pipeline
  /vision_and_presence_detection     UserState            Member 2
  /head_posture_state                HeadPosture          Member 6
  /voice_command                     std_msgs/String      dismiss only

Publishes:
  /focus_robot/fatigue_level         std_msgs/Int32       0-3
  /focus_robot/fatigue_score         std_msgs/Float32     0.0-1.0
  /focus_robot/ear                   std_msgs/Float32     eye aspect ratio
  /focus_robot/perclos               std_msgs/Float32     0.0-1.0
  /focus_robot/head_pitch_deg        std_msgs/Float32     degrees
  /focus_robot/face_absent_secs      std_msgs/Float32     seconds
  /focus_robot/fatigue_summary       std_msgs/String      JSON — for LLM
  /tts_request                       std_msgs/String      speech request to TTS module
"""

import os
import json
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime

import cv2
import mediapipe as mp
import numpy as np
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
from std_msgs.msg import Float32, Int32, String


# ── Member 2 import ───────────────────────────────────────────────────────
try:
    from vision_presence_module.msg import UserState
    _M2_OK = True
except ImportError:
    _M2_OK = False


# ── Member 6 import ───────────────────────────────────────────────────────
try:
    from head_posture_module.msg import HeadPosture
    _M6_OK = True
except ImportError:
    _M6_OK = False


# ─────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────
CFG = {
    "EAR_CLOSE_THRESH"      : 0.20,
    "PERCLOS_WINDOW_SECS"   : 60,
    "PERCLOS_MILD"          : 0.15,
    "PERCLOS_MODERATE"      : 0.25,
    "PERCLOS_SEVERE"        : 0.35,
    "HEAD_PITCH_THRESH_DEG" : -12,
    "HEAD_PITCH_CONFIRM_N"  : 15,
    "FACE_ABSENT_MILD_S"    : 5,
    "FACE_ABSENT_MODERATE_S": 15,
    "SCORE_MILD"            : 0.30,
    "SCORE_MODERATE"        : 0.55,
    "SCORE_SEVERE"          : 0.80,
    "LOG_INTERVAL_SECS"     : 60,

    # Time multiplier breakpoints
    "TIME_MUL_20MIN"        : 1.0,
    "TIME_MUL_40MIN"        : 1.3,
    "TIME_MUL_60PLUS"       : 1.6,
}


# ── Landmark indices ──────────────────────────────────────────────────────
LEFT_EYE  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
HEAD_LM   = [4, 152, 33, 263, 61, 291]

FACE_3D = np.array([
    (  0.0,    0.0,   0.0),
    (  0.0, -330.0, -65.0),
    (-225.0,  170.0,-135.0),
    ( 225.0,  170.0,-135.0),
    (-150.0, -150.0,-125.0),
    ( 150.0, -150.0,-125.0),
], dtype=np.float64)

LEVEL_LABEL = {
    0: "ALERT",
    1: "MILD",
    2: "MODERATE",
    3: "SEVERE",
}

LEVEL_COLOR = {
    0: (0, 200, 0),
    1: (0, 200, 200),
    2: (0, 140, 255),
    3: (0, 0, 220),
}


# ─────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────
@dataclass
class Metrics:
    ear_avg         : float = 0.0
    perclos         : float = 0.0
    head_pitch      : float = 0.0
    head_down_frames: int   = 0
    face_absent_secs: float = 0.0
    fatigue_score   : float = 0.0
    fatigue_level   : int   = 0



@dataclass
class M2State:
    """Data received from Member 2 user_state_monitor."""
    user_present             : bool = False
    consecutive_eyes_missing : int  = 0
    consecutive_face_absent  : int  = 0
    received                 : bool = False


@dataclass
class M6State:
    """Data received from Member 6 head_posture_node."""
    pose_visible    : bool  = False
    calibrated      : bool  = False
    head_down       : bool  = False
    posture_score   : float = 0.0
    received        : bool  = False


# ─────────────────────────────────────────────────────────────────────────
# MAIN CLASS
# ─────────────────────────────────────────────────────────────────────────
class FatigueMonitor:

    LOCAL_TTS_MESSAGES = {
        1: "Working hard. Remember to rest your eyes.",
        2: "Losing focus. A short break might help.",
        3: "You look quite tired. Consider taking a break.",
    }

    def __init__(self):
        rospy.init_node("fatigue_monitor", anonymous=False)
        rospy.on_shutdown(self.cleanup)
        rospy.loginfo("FatigueMonitor: initialising...")

        rospy.loginfo(
            "Member 2 (UserState) import: %s",
            "OK" if _M2_OK else "MISSING — vision_presence_module not found"
        )
        rospy.loginfo(
            "Member 6 (HeadPosture) import: %s",
            "OK" if _M6_OK else "MISSING — head_posture_module not found"
        )

        # ── MediaPipe FaceMesh ────────────────────────────────────────────
        mp_fm = mp.solutions.face_mesh
        self.face_mesh = mp_fm.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.mp_fm   = mp_fm

        # ── CvBridge ──────────────────────────────────────────────────────
        self.bridge  = CvBridge()
        self.cam_mat = None
        self.dist    = np.zeros((4, 1), dtype=np.float64)

        # ── Internal state ────────────────────────────────────────────────
        self.m   = Metrics()
        self.m2  = M2State()
        self.m6  = M6State()

        self.perclos_buf         : deque = deque()
        self.last_face_time      : float = time.time()
        self.face_present        : bool  = False
        self.last_metric_log_time: float = 0.0

        # Overlay message. Used by local fallback TTS and dismiss.
        self.overlay_msg   : str   = ""
        self.overlay_until : float = 0.0

        # ── Local TTS fallback config ─────────────────────────────────────
        self.local_tts = rospy.get_param("~local_tts_enabled", False)
        self.last_intv_time      : float = 0.0
        self.MIN_INTV_GAP = float(rospy.get_param("~min_intv_gap_secs", 30.0))

        rospy.loginfo(
            "FatigueMonitor: local_tts_enabled=%s "
            "(LLM handles interventions when False)",
            self.local_tts
        )

        # ── Log file ──────────────────────────────────────────────────────
        log_name = datetime.now().strftime("fatigue_log_%Y%m%d_%H%M%S.txt")
        self.log_path = os.path.join(os.path.expanduser("~"), log_name)
        self._init_log()
        rospy.loginfo("FatigueMonitor: logging to %s", self.log_path)

        # ── Publishers ────────────────────────────────────────────────────
        self.pub_level   = rospy.Publisher(
            "/focus_robot/fatigue_level", Int32, queue_size=1)
        self.pub_score   = rospy.Publisher(
            "/focus_robot/fatigue_score", Float32, queue_size=1)
        self.pub_ear     = rospy.Publisher(
            "/focus_robot/ear", Float32, queue_size=1)
        self.pub_perclos = rospy.Publisher(
            "/focus_robot/perclos", Float32, queue_size=1)
        self.pub_pitch   = rospy.Publisher(
            "/focus_robot/head_pitch_deg", Float32, queue_size=1)
        self.pub_absent  = rospy.Publisher(
            "/focus_robot/face_absent_secs", Float32, queue_size=1)

        # JSON summary — primary input for LLM brain node
        self.pub_summary = rospy.Publisher(
            "/focus_robot/fatigue_summary", String, queue_size=1)

        # TTS request — handled by speech_output_module
        self.pub_tts = rospy.Publisher(
            "/tts_request", String, queue_size=10)

        # ── Subscribers ───────────────────────────────────────────────────
        rospy.Subscriber(
            "/usb_cam/image_raw", Image, self._image_callback)


        # Voice command module — dismiss only
        rospy.Subscriber(
            "/voice_command", String, self._voice_callback)

        # Member 2 — user state monitor
        if _M2_OK:
            rospy.Subscriber(
                "/vision_and_presence_detection",
                UserState,
                self._m2_callback
            )
            rospy.loginfo(
                "FatigueMonitor: subscribed to /vision_and_presence_detection")
        else:
            rospy.logwarn(
                "FatigueMonitor: Member 2 unavailable — "
                "running without UserState data")

        # Member 6 — head posture monitor
        if _M6_OK:
            m6_topic = rospy.get_param(
                "~head_posture_topic", "/head_posture_state")
            rospy.Subscriber(
                m6_topic,
                HeadPosture,
                self._m6_callback
            )
            rospy.loginfo(
                "FatigueMonitor: subscribed to %s", m6_topic)
        else:
            rospy.logwarn(
                "FatigueMonitor: Member 6 unavailable — "
                "running without body posture data")

        rospy.loginfo(
            "FatigueMonitor: ready — always monitoring; LLM manages session state")

    # ──────────────────────────────────────────────────────────────────────
    # MEMBER 2 CALLBACK
    # ──────────────────────────────────────────────────────────────────────
    def _m2_callback(self, msg):
        """Receives UserState from Member 2 user_state_monitor."""
        self.m2.user_present             = msg.user_present
        self.m2.consecutive_eyes_missing = msg.consecutive_eyes_missing
        self.m2.consecutive_face_absent  = msg.consecutive_face_absent
        self.m2.received                 = True

    # ──────────────────────────────────────────────────────────────────────
    # MEMBER 6 CALLBACK
    # ──────────────────────────────────────────────────────────────────────
    def _m6_callback(self, msg):
        """Receives HeadPosture from Member 6 head_posture_monitor."""
        self.m6.pose_visible  = msg.pose_visible
        self.m6.calibrated    = msg.calibrated
        self.m6.head_down     = msg.head_down
        self.m6.posture_score = msg.posture_score
        self.m6.received      = True

    # ──────────────────────────────────────────────────────────────────────
    # TTS REQUEST HELPER
    # ──────────────────────────────────────────────────────────────────────
    def _say(self, text: str):
        """
        Publish speech request to /tts_request.
        speech_output_module handles SoundClient/sound_play and deduplication.
        """
        if not text:
            return

        self.pub_tts.publish(String(data=text))
        rospy.loginfo("TTS request: %r", text)

    # ──────────────────────────────────────────────────────────────────────
    # LOCAL TTS FALLBACK
    # ──────────────────────────────────────────────────────────────────────
    def _try_local_tts(self):
        """
        Fallback TTS used only when local_tts_enabled=True.

        Session timing is owned by LLM, so this fallback is always-on and
        only uses two guards:
          1. fatigue_level must be > 0
          2. minimum intervention gap must have passed
        """
        level = self.m.fatigue_level
        if level == 0:
            return

        now = time.time()
        if now - self.last_intv_time < self.MIN_INTV_GAP:
            return

        msg = self.LOCAL_TTS_MESSAGES.get(level)
        if not msg:
            return

        self._say(msg)

        self.overlay_msg    = msg
        self.overlay_until  = now + 5.0
        self.last_intv_time = now
        self._write_log("LOCAL_TTS")


    # ──────────────────────────────────────────────────────────────────────
    # VOICE CALLBACK — dismiss only
    # ──────────────────────────────────────────────────────────────────────
    def _voice_callback(self, msg):
        """
        Only handles 'dismiss' from the voice module.
        All other commands are handled by the LLM module.
        """
        cmd = msg.data.strip().lower()

        if cmd == "dismiss":
            self.overlay_msg   = ""
            self.overlay_until = 0.0
            self._write_event("USER DISMISSED alert")
            self._say("Noted.")
            rospy.loginfo("[VOICE] Dismiss received — overlay cleared")
        else:
            rospy.logdebug(
                "FatigueMonitor received voice cmd '%s' — "
                "LLM module handles session commands",
                cmd
            )

    # ──────────────────────────────────────────────────────────────────────
    # IMAGE CALLBACK
    # ──────────────────────────────────────────────────────────────────────
    def _image_callback(self, msg):
        if self.face_mesh is None:
            return

        try:
            frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as e:
            rospy.logwarn_throttle(5.0, "CvBridge error: %s", e)
            return

        frame = cv2.flip(frame, 1)

        if self.cam_mat is None:
            fh, fw = frame.shape[:2]
            self.cam_mat = np.array([
                [fw,  0, fw / 2],
                [ 0, fw, fh / 2],
                [ 0,  0,      1],
            ], dtype=np.float64)

        frame = self._process(frame)
        frame = self._draw(frame)

        cv2.imshow("Fatigue Monitor", frame)
        cv2.waitKey(1)

    # ──────────────────────────────────────────────────────────────────────
    # SIGNAL CALCULATIONS
    # ──────────────────────────────────────────────────────────────────────
    def _ear(self, pts: np.ndarray) -> float:
        v1 = np.linalg.norm(pts[1] - pts[5])
        v2 = np.linalg.norm(pts[2] - pts[4])
        h  = np.linalg.norm(pts[0] - pts[3])

        return (v1 + v2) / (2.0 * h + 1e-6)

    def _eye_pts(self, lm, idx, w, h) -> np.ndarray:
        return np.array(
            [(lm[i].x * w, lm[i].y * h) for i in idx],
            dtype=np.float64
        )

    def _update_perclos(self, is_closed: bool) -> float:
        now = time.time()
        self.perclos_buf.append((now, is_closed))

        cutoff = now - CFG["PERCLOS_WINDOW_SECS"]
        while self.perclos_buf and self.perclos_buf[0][0] < cutoff:
            self.perclos_buf.popleft()

        if len(self.perclos_buf) < 5:
            return 0.0

        return sum(1 for _, closed in self.perclos_buf if closed) / len(
            self.perclos_buf
        )

    def _head_pitch(self, lm, w, h) -> float:
        if self.cam_mat is None:
            return 0.0

        pts_2d = np.array(
            [(lm[i].x * w, lm[i].y * h) for i in HEAD_LM],
            dtype=np.float64
        )

        ok, rvec, _ = cv2.solvePnP(
            FACE_3D,
            pts_2d,
            self.cam_mat,
            self.dist,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        if not ok:
            return 0.0

        rmat, _ = cv2.Rodrigues(rvec)
        angles, *_ = cv2.RQDecomp3x3(rmat)
        pitch = angles[0]

        # Flip ambiguity correction.
        if pitch > 90:
            pitch = pitch - 180
        elif pitch < -90:
            pitch = pitch + 180

        return pitch

    def _time_multiplier(self) -> float:
        """
        Session duration is owned by LLM.
        No local time scaling is applied here.
        """
        return 1.0

    # ──────────────────────────────────────────────────────────────────────
    # FATIGUE SCORE — integrates own signals, M2, and updated M6 logic
    # ──────────────────────────────────────────────────────────────────────
    def _compute_score(self) -> float:
        m = self.m

        # ── PERCLOS (50% weight) ──────────────────────────────────────────
        # Primary eye-based fatigue signal.
        perclos_n = min(m.perclos / (CFG["PERCLOS_SEVERE"] + 1e-6), 1.0)

        # ── Head signal (30% weight) ──────────────────────────────────────
        #
        # Two independent measurements:
        #
        # 1. Our face-mesh pitch:
        #    Measures angular head tilt using face landmarks.
        #    Works when only the face is visible.
        #
        # 2. M6 head posture:
        #    Measures physical body droop using MediaPipe Pose:
        #    ratio = nose_y - shoulder_midpoint_y
        #    posture_score = droop_amount / 100.0
        #
        # M6 is valid only when:
        #   pose_visible=True
        #   calibrated=True
        #
        # If M6 head_down=True, it means sustained droop was detected.
        # If M6 head_down=False, posture_score may be transient leaning,
        # so its effect is attenuated.
        face_pitch_n = min(
            m.head_down_frames / CFG["HEAD_PITCH_CONFIRM_N"], 1.0
        )

        if (self.m6.received
                and self.m6.calibrated
                and self.m6.pose_visible):

            if self.m6.head_down:
                # Confirmed sustained body droop.
                m6_head_n = self.m6.posture_score
            else:
                # Possible transient lean, reduce its effect.
                m6_head_n = self.m6.posture_score * 0.35

            # Use stronger signal because M6 body droop and our face pitch
            # measure different physical fatigue cues.
            head_n = min(max(m6_head_n, face_pitch_n), 1.0)

            rospy.logdebug_throttle(
                5.0,
                "head_n=%.2f (m6=%.2f head_down=%s, face=%.2f)",
                head_n,
                m6_head_n,
                self.m6.head_down,
                face_pitch_n
            )

        else:
            # M6 missing, not calibrated, or pose not visible.
            # Fall back to our own face-mesh pitch only.
            head_n = face_pitch_n

            if self.m6.received and not self.m6.calibrated:
                rospy.logdebug_throttle(
                    10.0,
                    "M6 still calibrating — using face pitch only"
                )

        # ── Face absence (20% weight) ─────────────────────────────────────
        absent_n = min(
            m.face_absent_secs / CFG["FACE_ABSENT_MODERATE_S"], 1.0
        )

        # If M2 also confirms face absence, boost slightly.
        if self.m2.received and self.m2.consecutive_face_absent > 10:
            absent_n = min(absent_n * 1.2, 1.0)

        # ── Weighted sum with time scaling ────────────────────────────────
        raw = (
            perclos_n * 0.50 +
            head_n    * 0.30 +
            absent_n  * 0.20
        )

        return min(raw * self._time_multiplier(), 1.0)

    def _score_to_level(self, score: float) -> int:
        if score >= CFG["SCORE_SEVERE"]:
            return 3
        if score >= CFG["SCORE_MODERATE"]:
            return 2
        if score >= CFG["SCORE_MILD"]:
            return 1
        return 0

    # ──────────────────────────────────────────────────────────────────────
    # FRAME PROCESSING
    # ──────────────────────────────────────────────────────────────────────
    def _process(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        result = self.face_mesh.process(
            cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        )

        m   = self.m
        now = time.time()

        if result.multi_face_landmarks:
            self.face_present   = True
            self.last_face_time = now
            m.face_absent_secs  = 0.0

            lm = result.multi_face_landmarks[0].landmark

            self.mp_draw.draw_landmarks(
                frame,
                result.multi_face_landmarks[0],
                self.mp_fm.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=self.mp_draw.DrawingSpec(
                    color=(60, 120, 10),
                    thickness=1,
                    circle_radius=1
                )
            )

            l_pts = self._eye_pts(lm, LEFT_EYE,  w, h)
            r_pts = self._eye_pts(lm, RIGHT_EYE, w, h)

            m.ear_avg = (self._ear(l_pts) + self._ear(r_pts)) / 2.0
            m.perclos = self._update_perclos(
                m.ear_avg < CFG["EAR_CLOSE_THRESH"]
            )
            m.head_pitch = self._head_pitch(lm, w, h)

            if m.head_pitch < CFG["HEAD_PITCH_THRESH_DEG"]:
                m.head_down_frames += 1
            else:
                m.head_down_frames = max(0, m.head_down_frames - 1)

        else:
            self.face_present   = False
            m.face_absent_secs  = now - self.last_face_time
            m.head_down_frames  = max(0, m.head_down_frames - 1)

            self._update_perclos(False)

        # Always-on monitoring. Session state is handled by LLM.

        # Score and level.
        m.fatigue_score = self._compute_score()
        m.fatigue_level = self._score_to_level(m.fatigue_score)

        # Publish all metrics every frame.
        self._publish_all()

        # Local TTS fallback only.
        if self.local_tts:
            self._try_local_tts()

        # Periodic logging, independent of session state.
        if now - self.last_metric_log_time >= CFG["LOG_INTERVAL_SECS"]:
            self._write_log("METRIC")
            self.last_metric_log_time = now

        return frame

    # ──────────────────────────────────────────────────────────────────────
    # PUBLISH ALL METRICS
    # ──────────────────────────────────────────────────────────────────────
    def _publish_all(self):
        """
        Publishes individual metric topics and JSON summary.
        LLM brain subscribes to /focus_robot/fatigue_summary for all data.
        """
        m = self.m

        self.pub_level.publish(Int32(data=m.fatigue_level))
        self.pub_score.publish(Float32(data=m.fatigue_score))
        self.pub_ear.publish(Float32(data=m.ear_avg))
        self.pub_perclos.publish(Float32(data=m.perclos))
        self.pub_pitch.publish(Float32(data=m.head_pitch))
        self.pub_absent.publish(Float32(data=m.face_absent_secs))

        summary = {
            # Core fatigue assessment
            "fatigue_level"      : m.fatigue_level,
            "fatigue_label"      : LEVEL_LABEL[m.fatigue_level],
            "fatigue_score"      : round(m.fatigue_score, 3),
            "time_multiplier"    : self._time_multiplier(),

            # Own camera signals
            "ear"                : round(m.ear_avg, 3),
            "perclos"            : round(m.perclos, 3),
            "head_pitch_deg"     : round(m.head_pitch, 1),
            "head_down_frames"   : m.head_down_frames,
            "face_absent_secs"   : round(m.face_absent_secs, 1),
            "face_present"       : self.face_present,

            # Member 2 data
            "m2_available"                : self.m2.received,
            "m2_user_present"             : self.m2.user_present,
            "m2_consecutive_eyes_missing" : self.m2.consecutive_eyes_missing,
            "m2_consecutive_face_absent"  : self.m2.consecutive_face_absent,

            # Member 6 data
            "m6_available"      : self.m6.received,
            "m6_calibrated"     : self.m6.calibrated,
            "m6_pose_visible"   : self.m6.pose_visible,
            "m6_head_down"      : self.m6.head_down,
            "m6_posture_score"  : round(self.m6.posture_score, 3),

            # Session info intentionally omitted. LLM owns session state.

            # TTS mode info
            "local_tts_enabled" : self.local_tts,
            "tts_topic"         : "/tts_request",
        }

        self.pub_summary.publish(String(data=json.dumps(summary)))

    # ──────────────────────────────────────────────────────────────────────
    # DISPLAY OVERLAY
    # ──────────────────────────────────────────────────────────────────────
    def _bar(self, frame, x, y, bw, bh, ratio, color):
        ratio = max(0.0, min(ratio, 1.0))

        cv2.rectangle(frame, (x, y), (x + bw, y + bh), (50, 50, 50), -1)

        if ratio > 0:
            cv2.rectangle(
                frame,
                (x, y),
                (x + int(bw * ratio), y + bh),
                color,
                -1
            )

    def _txt(self, frame, text, y,
             color=(200, 200, 200), scale=0.50, bold=False):
        cv2.putText(
            frame,
            text,
            (8, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            color,
            2 if bold else 1,
            cv2.LINE_AA
        )

    def _status_dot(self, frame, x, y, ok):
        color = (0, 200, 0) if ok else (60, 60, 60)
        cv2.circle(frame, (x, y), 5, color, -1)

    def _draw(self, frame: np.ndarray) -> np.ndarray:
        h, w  = frame.shape[:2]
        m     = self.m
        now   = time.time()
        lvl   = m.fatigue_level
        col   = LEVEL_COLOR[lvl]

        # Border colour = fatigue level.
        cv2.rectangle(frame, (0, 0), (w - 1, h - 1), col, 10)

        # Dark left panel.
        cv2.rectangle(frame, (0, 0), (270, h), (0, 0, 0), -1)
        cv2.line(frame, (270, 0), (270, h), (50, 50, 50), 1)

        # Status.
        self._txt(frame, "STATUS", 22, (255, 255, 255), 0.55, True)
        self._txt(frame, "  Always monitoring", 42, (0, 220, 0))
        self._txt(frame, "  LLM manages session", 60, (80, 80, 80), 0.40)

        cv2.line(frame, (0, 72), (270, 72), (50, 50, 50), 1)

        # Own metrics.
        self._txt(frame, "OUR SIGNALS", 90, (255, 255, 255), 0.52, True)

        ear_col = (
            (0, 80, 255)
            if m.ear_avg < CFG["EAR_CLOSE_THRESH"]
            else (0, 200, 100)
        )
        self._txt(frame, f"  EAR      {m.ear_avg:.3f}", 110, ear_col)
        self._bar(frame, 8, 115, 252, 6, m.ear_avg / 0.40, (0, 180, 100))

        pc_col = (
            (0, 80, 255)
            if m.perclos > CFG["PERCLOS_MILD"]
            else (0, 200, 100)
        )
        self._txt(frame, f"  PERCLOS  {m.perclos * 100:.1f}%", 135, pc_col)
        self._bar(
            frame,
            8,
            140,
            252,
            6,
            m.perclos / (CFG["PERCLOS_SEVERE"] + 1e-6),
            (0, 120, 210)
        )

        pt_col = (
            (0, 80, 255)
            if m.head_pitch < CFG["HEAD_PITCH_THRESH_DEG"]
            else (0, 200, 100)
        )
        self._txt(frame, f"  Pitch    {m.head_pitch:.1f} deg", 160, pt_col)
        self._bar(
            frame,
            8,
            165,
            252,
            6,
            m.head_down_frames / CFG["HEAD_PITCH_CONFIRM_N"],
            (0, 150, 210)
        )

        ab_col = (
            (0, 80, 255)
            if m.face_absent_secs > CFG["FACE_ABSENT_MILD_S"]
            else (0, 200, 100)
        )
        self._txt(frame, f"  Absent   {m.face_absent_secs:.1f}s", 185, ab_col)
        self._bar(
            frame,
            8,
            190,
            252,
            6,
            m.face_absent_secs / CFG["FACE_ABSENT_MODERATE_S"],
            (0, 160, 180)
        )

        cv2.line(frame, (0, 200), (270, 200), (50, 50, 50), 1)

        # Member 2 status.
        self._txt(frame, "M2 USER STATE", 217, (255, 255, 255), 0.50, True)
        self._status_dot(frame, 255, 213, self.m2.received)

        if self.m2.received:
            p_col = (0, 200, 100) if self.m2.user_present else (0, 80, 255)
            self._txt(
                frame,
                f"  Present  {'YES' if self.m2.user_present else 'NO'}",
                235,
                p_col
            )
            self._txt(
                frame,
                f"  Eyes miss {self.m2.consecutive_eyes_missing}  "
                f"Face abs {self.m2.consecutive_face_absent}",
                252,
                (180, 180, 180),
                0.42
            )
        else:
            self._txt(frame, "  Not connected", 235, (80, 80, 80))

        cv2.line(frame, (0, 262), (270, 262), (50, 50, 50), 1)

        # Member 6 status.
        self._txt(frame, "M6 HEAD POSTURE", 279, (255, 255, 255), 0.50, True)
        self._status_dot(frame, 255, 275, self.m6.received)

        if self.m6.received:
            cal_col = (0, 200, 100) if self.m6.calibrated else (180, 180, 0)
            self._txt(
                frame,
                f"  {'Calibrated' if self.m6.calibrated else 'Calibrating...'}",
                297,
                cal_col
            )
            hd_col = (0, 80, 255) if self.m6.head_down else (0, 200, 100)
            self._txt(
                frame,
                f"  Down:{'YES' if self.m6.head_down else 'NO'} "
                f"Score:{self.m6.posture_score:.2f}",
                314,
                hd_col
            )
        else:
            self._txt(frame, "  Not connected", 297, (80, 80, 80))

        cv2.line(frame, (0, 325), (270, 325), (50, 50, 50), 1)

        # Fatigue output.
        self._txt(frame, "FATIGUE OUTPUT", 343, (255, 255, 255), 0.52, True)
        self._txt(frame, f"  Score : {m.fatigue_score:.2f}", 363)
        self._txt(
            frame,
            f"  Level : {LEVEL_LABEL[lvl]}",
            383,
            col,
            0.60,
            True
        )
        self._bar(frame, 8, 390, 252, 10, m.fatigue_score, col)

        tts_mode = "LOCAL TTS" if self.local_tts else "LLM TTS"
        self._txt(
            frame,
            f"  x{self._time_multiplier():.1f} time weight  [{tts_mode}]",
            410,
            (80, 80, 80),
            0.38
        )

        # Overlay message.
        if now < self.overlay_until and self.overlay_msg:
            txt = self.overlay_msg
            (tw, th), _ = cv2.getTextSize(
                txt,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                2
            )
            cx, cy, pad = w // 2, h - 50, 10

            cv2.rectangle(
                frame,
                (cx - tw // 2 - pad, cy - th - pad),
                (cx + tw // 2 + pad, cy + pad),
                (0, 0, 0),
                -1
            )
            cv2.rectangle(
                frame,
                (cx - tw // 2 - pad, cy - th - pad),
                (cx + tw // 2 + pad, cy + pad),
                col,
                2
            )
            cv2.putText(
                frame,
                txt,
                (cx - tw // 2, cy),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                col,
                2,
                cv2.LINE_AA
            )

        self._txt(
            frame,
            "Publishing /focus_robot/fatigue_summary + /tts_request",
            h - 8,
            (60, 60, 60),
            0.38
        )

        return frame

    # ──────────────────────────────────────────────────────────────────────
    # LOGGING
    # ──────────────────────────────────────────────────────────────────────
    def _init_log(self):
        with open(self.log_path, "w") as f:
            f.write("Fatigue Detection Session Log — Integrated with TTS\n")
            f.write(
                f"Started : "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            f.write(
                f"M2 available: {_M2_OK} | "
                f"M6 available: {_M6_OK} | "
                f"local_tts_enabled: {self.local_tts}\n"
            )
            f.write("-" * 72 + "\n")
            f.write(
                f"{'TIME':>8}  {'TYPE':<14} {'LEVEL':<10} "
                f"{'SCORE':>6} {'PERCLOS':>8} "
                f"{'PITCH':>8} {'ABSENT':>8} "
                f"{'M6SCORE':>8}\n"
            )
            f.write("-" * 72 + "\n")

    def _elapsed_str(self) -> str:
        return "--:--"

    def _write_log(self, entry_type: str):
        m = self.m

        with open(self.log_path, "a") as f:
            f.write(
                f"{self._elapsed_str():>8}  "
                f"{entry_type:<14} "
                f"{LEVEL_LABEL[m.fatigue_level]:<10} "
                f"{m.fatigue_score:>6.2f} "
                f"{m.perclos * 100:>7.1f}% "
                f"{m.head_pitch:>7.1f}d "
                f"{m.face_absent_secs:>7.1f}s "
                f"{self.m6.posture_score:>7.3f}\n"
            )

    def _write_event(self, label: str):
        with open(self.log_path, "a") as f:
            f.write(
                f"\n>>> {label} at "
                f"{datetime.now().strftime('%H:%M:%S')} "
                f"| elapsed {self._elapsed_str()}\n\n"
            )

    # ──────────────────────────────────────────────────────────────────────
    # RUN AND CLEANUP
    # ──────────────────────────────────────────────────────────────────────
    def run(self):
        rospy.loginfo(
            "FatigueMonitor: spinning — publishing to "
            "/focus_robot/fatigue_summary"
        )
        rospy.spin()

    def cleanup(self):
        cv2.destroyAllWindows()
        self._write_event("NODE SHUTDOWN")
        rospy.loginfo("FatigueMonitor: log saved to %s", self.log_path)


if __name__ == "__main__":
    try:
        FatigueMonitor().run()
    except rospy.ROSInterruptException:
        pass