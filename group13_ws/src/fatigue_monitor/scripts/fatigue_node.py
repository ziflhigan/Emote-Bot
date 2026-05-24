#!/usr/bin/env python3
"""
Fatigue Detection & Intervention — ROS Node
Member 5 — fatigue_monitor package

Identical behaviour on VM and robot.

Run sequence:
  Terminal 1: roscore
  Terminal 2: roslaunch usb_cam usb_cam-test.launch
  Terminal 3: roslaunch jupiterobot2_voice_ps voice_recognition.launch
              (VM: rostopic pub /recognizer/output std_msgs/String "data: 'move'" --once)
  Terminal 4: rosrun fatigue_monitor fatigue_node.py

Publishes:
  /focus_robot/session_active  std_msgs/Bool
  /focus_robot/fatigue_level   std_msgs/Int32

Subscribes:
  /usb_cam/image_raw           sensor_msgs/Image
  /recognizer/output           std_msgs/String
"""

import os
import rospy
import cv2
import mediapipe as mp
import numpy as np
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from std_msgs.msg import Bool, Int32, String
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from sound_play.libsoundplay import SoundClient

# ─────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────
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
    "WARMUP_SECS"           : 30,    # → 600 for real sessions
    "MIN_INTV_GAP_SECS"     : 30,    # → 300 for real sessions
    "SCORE_MILD"            : 0.30,
    "SCORE_MODERATE"        : 0.55,
    "SCORE_SEVERE"          : 0.80,
    "LOG_INTERVAL_SECS"     : 60,
}

# ─────────────────────────────────────────────────────────
# LANDMARK INDICES
# ─────────────────────────────────────────────────────────
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

LEVEL_LABEL = {0:"ALERT", 1:"MILD", 2:"MODERATE", 3:"SEVERE"}
LEVEL_COLOR = {0:(0,200,0), 1:(0,200,200), 2:(0,140,255), 3:(0,0,220)}

# ─────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────
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
class Session:
    active      : bool  = False
    start_time  : float = 0.0
    elapsed_secs: float = 0.0
    warmup_done : bool  = False

# ─────────────────────────────────────────────────────────
# MAIN CLASS
# ─────────────────────────────────────────────────────────
class FatigueMonitor:

    def __init__(self):
        rospy.init_node('fatigue_monitor', anonymous=False)
        rospy.on_shutdown(self.cleanup)
        rospy.loginfo("FatigueMonitor: initialising...")

        # Sound client — same pattern as say_hello_ans.py
        self.soundhandle = SoundClient()
        rospy.sleep(1)
        self.soundhandle.stopAll()
        rospy.loginfo("FatigueMonitor: sound_play ready")

        # CvBridge
        self.bridge = CvBridge()

        # MediaPipe FaceMesh
        mp_fm = mp.solutions.face_mesh
        self.face_mesh = mp_fm.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.mp_fm   = mp_fm

        # State
        self.m = Metrics()
        self.s = Session()

        self.perclos_buf         : deque = deque()
        self.last_face_time      : float = time.time()
        self.face_present        : bool  = False
        self.last_intv_time      : float = 0.0
        self.intv_text           : str   = ""
        self.intv_show_until     : float = 0.0
        self.last_metric_log_time: float = 0.0
        self.cam_mat                     = None
        self.dist = np.zeros((4, 1), dtype=np.float64)

        # Log file — home dir resolved at runtime
        log_name = datetime.now().strftime("fatigue_log_%Y%m%d_%H%M%S.txt")
        self.log_path = os.path.join(os.path.expanduser("~"), log_name)
        self._init_log()
        rospy.loginfo(f"FatigueMonitor: logging to {self.log_path}")

        # Publishers
        self.pub_active = rospy.Publisher(
            '/focus_robot/session_active', Bool,  queue_size=1)
        self.pub_level  = rospy.Publisher(
            '/focus_robot/fatigue_level',  Int32, queue_size=1)

        # Subscribers
        rospy.Subscriber(
            '/usb_cam/image_raw', Image, self._image_callback)
        rospy.Subscriber(
            '/recognizer/output', String, self._voice_callback)

        rospy.loginfo("FatigueMonitor: ready — say MOVE to start")

    # ──────────────────────────────────────
    # IMAGE CALLBACK
    # ──────────────────────────────────────

    def _image_callback(self, msg):
        if self.face_mesh is None:
            return
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as e:
            rospy.logwarn(f"CvBridge error: {e}")
            return

        frame = cv2.flip(frame, 1)

        if self.cam_mat is None:
            fh, fw = frame.shape[:2]
            self.cam_mat = np.array([
                [fw,  0, fw/2],
                [ 0, fw, fh/2],
                [ 0,  0,    1]
            ], dtype=np.float64)

        frame = self._process(frame)
        frame = self._draw(frame)
        cv2.imshow("Fatigue Monitor", frame)
        cv2.waitKey(1)

    # ──────────────────────────────────────
    # VOICE CALLBACK
    # ──────────────────────────────────────

    def _voice_callback(self, msg):
        """
        Receives from /recognizer/output (pocketsphinx).
        Matches on last word only — pocketsphinx accumulates words
        in the same string e.g. "half stop move move back stop".

        Supported vocabulary (existing pocketsphinx dictionary):
          MOVE → start session
          STOP → end session
        """
        words = msg.data.upper().split()
        if not words:
            return

        last = words[-1]
        rospy.loginfo(f"Voice: '{msg.data}' → last='{last}'")

        if last == "MOVE" and not self.s.active:
            self._start_session()
        elif last == "STOP" and self.s.active:
            self._stop_session()

    def _start_session(self):
        self.s.active             = True
        self.s.start_time         = time.time()
        self.s.elapsed_secs       = 0.0
        self.s.warmup_done        = False
        self.last_metric_log_time = 0.0
        rospy.loginfo("[SESSION] Started")
        self._write_event("SESSION START")
        self.soundhandle.say(
            "Focus session started. I will check in with you.")

    def _stop_session(self):
        mins = int(self.s.elapsed_secs / 60)
        rospy.loginfo(f"[SESSION] Stopped after {mins} minutes")
        self._write_event(
            f"SESSION STOP | final score {self.m.fatigue_score:.2f}")
        self.soundhandle.say(
            f"Session ended. You focused for {mins} minutes. Good work.")
        self.s.active = False
        self.pub_active.publish(Bool(data=False))

    # ──────────────────────────────────────
    # SIGNAL CALCULATIONS
    # ──────────────────────────────────────

    def _ear(self, pts: np.ndarray) -> float:
        v1 = np.linalg.norm(pts[1] - pts[5])
        v2 = np.linalg.norm(pts[2] - pts[4])
        h  = np.linalg.norm(pts[0] - pts[3])
        return (v1 + v2) / (2.0 * h + 1e-6)

    def _eye_pts(self, lm, idx, w, h) -> np.ndarray:
        return np.array(
            [(lm[i].x * w, lm[i].y * h) for i in idx],
            dtype=np.float64)

    def _update_perclos(self, is_closed: bool) -> float:
        now = time.time()
        self.perclos_buf.append((now, is_closed))
        cutoff = now - CFG["PERCLOS_WINDOW_SECS"]
        while self.perclos_buf and self.perclos_buf[0][0] < cutoff:
            self.perclos_buf.popleft()
        if len(self.perclos_buf) < 5:
            return 0.0
        return sum(1 for _, c in self.perclos_buf if c) / len(
            self.perclos_buf)

    def _head_pitch(self, lm, w, h) -> float:
        if self.cam_mat is None:
            return 0.0
        pts_2d = np.array(
            [(lm[i].x * w, lm[i].y * h) for i in HEAD_LM],
            dtype=np.float64)
        ok, rvec, _ = cv2.solvePnP(
            FACE_3D, pts_2d, self.cam_mat, self.dist,
            flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok:
            return 0.0
        rmat, _ = cv2.Rodrigues(rvec)
        angles, *_ = cv2.RQDecomp3x3(rmat)
        return angles[0]

    def _time_multiplier(self) -> float:
        mins = self.s.elapsed_secs / 60
        if mins < 20: return 1.0
        if mins < 40: return 1.3
        return 1.6

    def _compute_score(self) -> float:
        m = self.m
        perclos_n = min(m.perclos / (CFG["PERCLOS_SEVERE"] + 1e-6), 1.0)
        head_n    = min(
            m.head_down_frames / CFG["HEAD_PITCH_CONFIRM_N"], 1.0)
        absent_n  = min(
            m.face_absent_secs / CFG["FACE_ABSENT_MODERATE_S"], 1.0)
        raw = (perclos_n * 0.50 +
               head_n    * 0.30 +
               absent_n  * 0.20)
        return min(raw * self._time_multiplier(), 1.0)

    def _score_to_level(self, score: float) -> int:
        if score >= CFG["SCORE_SEVERE"]:   return 3
        if score >= CFG["SCORE_MODERATE"]: return 2
        if score >= CFG["SCORE_MILD"]:     return 1
        return 0

    # ──────────────────────────────────────
    # INTERVENTION
    # ──────────────────────────────────────

    MESSAGES = {
        1: "Working hard. Remember to rest your eyes.",
        2: "Losing focus. A short break might help.",
        3: "You look quite tired. Consider taking a break.",
    }

    def _try_intervene(self):
        level = self.m.fatigue_level
        if level == 0 or not self.s.warmup_done:
            return
        if time.time() - self.last_intv_time < CFG["MIN_INTV_GAP_SECS"]:
            return
        msg = self.MESSAGES[level]
        self.soundhandle.say(msg)
        rospy.loginfo(f"[{LEVEL_LABEL[level]}] {msg}")
        self.intv_text       = msg
        self.intv_show_until = time.time() + 5.0
        self.last_intv_time  = time.time()
        self._write_log("INTERVENTION")

    # ──────────────────────────────────────
    # FRAME PROCESSING
    # ──────────────────────────────────────

    def _process(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        result = self.face_mesh.process(
            cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
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
                    color=(60,120,10), thickness=1, circle_radius=1))

            l_pts = self._eye_pts(lm, LEFT_EYE,  w, h)
            r_pts = self._eye_pts(lm, RIGHT_EYE, w, h)
            m.ear_avg    = (self._ear(l_pts) + self._ear(r_pts)) / 2.0
            m.perclos    = self._update_perclos(
                m.ear_avg < CFG["EAR_CLOSE_THRESH"])
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

        if self.s.active:
            self.s.elapsed_secs = now - self.s.start_time
            self.s.warmup_done  = (
                self.s.elapsed_secs > CFG["WARMUP_SECS"])

        m.fatigue_score = self._compute_score()
        m.fatigue_level = self._score_to_level(m.fatigue_score)

        self.pub_active.publish(Bool(data=self.s.active))
        self.pub_level.publish(Int32(data=m.fatigue_level))

        if self.s.active:
            self._try_intervene()
            if (self.s.warmup_done and
                    now - self.last_metric_log_time
                    >= CFG["LOG_INTERVAL_SECS"]):
                self._write_log("METRIC")
                self.last_metric_log_time = now

        return frame

    # ──────────────────────────────────────
    # DISPLAY OVERLAY
    # ──────────────────────────────────────

    def _bar(self, frame, x, y, bw, bh, ratio, color):
        ratio = max(0.0, min(ratio, 1.0))
        cv2.rectangle(frame, (x,y), (x+bw, y+bh), (50,50,50), -1)
        if ratio > 0:
            cv2.rectangle(
                frame, (x,y), (x+int(bw*ratio), y+bh), color, -1)

    def _txt(self, frame, text, y,
             color=(200,200,200), scale=0.52, bold=False):
        cv2.putText(frame, text, (8, y),
                    cv2.FONT_HERSHEY_SIMPLEX, scale,
                    color, 2 if bold else 1, cv2.LINE_AA)

    def _draw(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        m   = self.m
        s   = self.s
        now = time.time()
        lvl = m.fatigue_level
        col = LEVEL_COLOR[lvl]

        cv2.rectangle(frame, (0,0), (w-1, h-1), col, 10)
        cv2.rectangle(frame, (0,0), (255, h), (0,0,0), -1)
        cv2.line(frame, (255,0), (255, h), (50,50,50), 1)

        # Session
        self._txt(frame, "SESSION", 24, (255,255,255), 0.58, True)
        if s.active:
            mm = int(s.elapsed_secs // 60)
            ss = int(s.elapsed_secs  % 60)
            self._txt(frame, f"  {mm:02d}:{ss:02d} elapsed",
                      46, (0,220,0))
            wl = max(0, CFG["WARMUP_SECS"] - s.elapsed_secs)
            if wl > 0:
                self._txt(frame, f"  Warmup: {int(wl)}s",
                          66, (180,180,0))
            else:
                self._txt(frame, "  Monitoring ACTIVE",
                          66, (0,220,120))
        else:
            self._txt(frame, "  Say MOVE to start",
                      46, (120,120,120))

        cv2.line(frame, (0,80), (255,80), (50,50,50), 1)

        # Metrics
        self._txt(frame, "METRICS", 100, (255,255,255), 0.55, True)

        ear_col = (0,80,255) \
            if m.ear_avg < CFG["EAR_CLOSE_THRESH"] else (0,200,100)
        self._txt(frame, f"  EAR      {m.ear_avg:.3f}", 122, ear_col)
        self._bar(frame, 8, 127, 238, 7, m.ear_avg/0.40, (0,180,100))

        pc_col = (0,80,255) \
            if m.perclos > CFG["PERCLOS_MILD"] else (0,200,100)
        self._txt(frame, f"  PERCLOS  {m.perclos*100:.1f}%",
                  152, pc_col)
        self._bar(frame, 8, 157, 238, 7,
                  m.perclos/(CFG["PERCLOS_SEVERE"]+1e-6), (0,120,210))

        pt_col = (0,80,255) \
            if m.head_pitch < CFG["HEAD_PITCH_THRESH_DEG"] \
            else (0,200,100)
        self._txt(frame, f"  Pitch    {m.head_pitch:.1f} deg",
                  182, pt_col)
        self._bar(frame, 8, 187, 238, 7,
                  m.head_down_frames/CFG["HEAD_PITCH_CONFIRM_N"],
                  (0,150,210))

        ab_col = (0,80,255) \
            if m.face_absent_secs > CFG["FACE_ABSENT_MILD_S"] \
            else (0,200,100)
        self._txt(frame, f"  Absent   {m.face_absent_secs:.1f}s",
                  212, ab_col)
        self._bar(frame, 8, 217, 238, 7,
                  m.face_absent_secs/CFG["FACE_ABSENT_MODERATE_S"],
                  (0,160,180))

        cv2.line(frame, (0,230), (255,230), (50,50,50), 1)

        # Fatigue level
        self._txt(frame, "FATIGUE LEVEL", 252,
                  (255,255,255), 0.55, True)
        self._txt(frame, f"  Score : {m.fatigue_score:.2f}", 274)
        self._txt(frame, f"  Level : {LEVEL_LABEL[lvl]}",
                  298, col, 0.62, True)
        self._bar(frame, 8, 307, 238, 10, m.fatigue_score, col)
        self._txt(frame, f"  x{self._time_multiplier():.1f} time weight",
                  328, (120,120,120), 0.45)
        self._txt(frame, "  MOVE=start  STOP=end",
                  348, (80,80,80), 0.40)

        # Intervention banner
        if now < self.intv_show_until and self.intv_text:
            txt = self.intv_text
            (tw, th), _ = cv2.getTextSize(
                txt, cv2.FONT_HERSHEY_SIMPLEX, 0.60, 2)
            cx  = w // 2
            cy  = h - 50
            pad = 10
            cv2.rectangle(frame,
                          (cx-tw//2-pad, cy-th-pad),
                          (cx+tw//2+pad, cy+pad),
                          (0,0,0), -1)
            cv2.rectangle(frame,
                          (cx-tw//2-pad, cy-th-pad),
                          (cx+tw//2+pad, cy+pad),
                          col, 2)
            cv2.putText(frame, txt, (cx-tw//2, cy),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.60, col, 2, cv2.LINE_AA)

        return frame

    # ──────────────────────────────────────
    # LOGGING
    # ──────────────────────────────────────

    def _init_log(self):
        with open(self.log_path, "w") as f:
            f.write("Fatigue Detection Session Log\n")
            f.write(
                f"Started : "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(
                f"CFG     : WARMUP={CFG['WARMUP_SECS']}s  "
                f"MIN_GAP={CFG['MIN_INTV_GAP_SECS']}s  "
                f"EAR={CFG['EAR_CLOSE_THRESH']}\n")
            f.write("-" * 70 + "\n")
            f.write(
                f"{'TIME':>8}  {'TYPE':<14} {'LEVEL':<10} "
                f"{'SCORE':>6} {'PERCLOS':>8} "
                f"{'PITCH':>8} {'ABSENT':>8} {'MULTx':>6}\n")
            f.write("-" * 70 + "\n")

    def _elapsed_str(self) -> str:
        mm = int(self.s.elapsed_secs // 60)
        ss = int(self.s.elapsed_secs  % 60)
        return f"{mm:02d}:{ss:02d}"

    def _write_log(self, entry_type: str):
        m = self.m
        with open(self.log_path, "a") as f:
            f.write(
                f"{self._elapsed_str():>8}  "
                f"{entry_type:<14} "
                f"{LEVEL_LABEL[m.fatigue_level]:<10} "
                f"{m.fatigue_score:>6.2f} "
                f"{m.perclos*100:>7.1f}% "
                f"{m.head_pitch:>7.1f}d "
                f"{m.face_absent_secs:>7.1f}s "
                f"{self._time_multiplier():>5.1f}x\n"
            )

    def _write_event(self, label: str):
        with open(self.log_path, "a") as f:
            f.write(
                f"\n>>> {label} at "
                f"{datetime.now().strftime('%H:%M:%S')} "
                f"| elapsed {self._elapsed_str()}\n\n"
            )

    # ──────────────────────────────────────
    # RUN AND CLEANUP
    # ──────────────────────────────────────

    def run(self):
        rospy.loginfo("FatigueMonitor: spinning — say MOVE to begin")
        rospy.spin()

    def cleanup(self):
        self.soundhandle.stopAll()
        cv2.destroyAllWindows()
        self._write_event("NODE SHUTDOWN")
        rospy.loginfo(f"FatigueMonitor: log saved to {self.log_path}")


if __name__ == "__main__":
    try:
        FatigueMonitor().run()
    except rospy.ROSInterruptException:
        pass