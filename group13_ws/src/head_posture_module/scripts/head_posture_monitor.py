#!/usr/bin/env python

import importlib
import sys
import time

import rospy
from std_msgs.msg import Bool

from head_posture_module.msg import HeadPosture


class HeadPostureLogic:
    """Tracks head droop and calibration across consecutive pose callbacks."""

    def __init__(self):
        self.consecutive_droop_frames = 0
        self.droop_frame_threshold = 15
        self.droop_pixel_threshold = 30.0
        self.head_down = False
        self.posture_score = 0.0
        self.head_drop_ratio = 0.0
        self.baseline_ratio = None
        self.pose_visible = False

        self.calibrating = True
        self.calibration_start_time = time.time()
        self.calibration_duration = 30.0
        self.calibration_samples = []

    @property
    def calibrated(self):
        return not self.calibrating

    def reset_calibration(self):
        """Reset baseline collection (call when a focus session starts)."""
        self.calibrating = True
        self.calibration_start_time = time.time()
        self.calibration_samples = []
        self.baseline_ratio = None
        self.consecutive_droop_frames = 0
        self.head_down = False
        self.posture_score = 0.0
        self.head_drop_ratio = 0.0

    def get_ratio(self, nose_y, left_shoulder_y, right_shoulder_y):
        shoulder_midpoint_y = (left_shoulder_y + right_shoulder_y) / 2.0
        return nose_y - shoulder_midpoint_y

    def _finish_calibration(self):
        if not self.calibration_samples:
            self.calibration_start_time = time.time()
            return False

        self.baseline_ratio = (
            sum(self.calibration_samples) / float(len(self.calibration_samples))
        )
        self.calibrating = False
        return True

    def update_calibration(self, nose_y, left_shoulder_y, right_shoulder_y):
        elapsed = time.time() - self.calibration_start_time
        if elapsed < self.calibration_duration:
            ratio = self.get_ratio(nose_y, left_shoulder_y, right_shoulder_y)
            self.calibration_samples.append(ratio)
            return False

        if self.baseline_ratio is None:
            if not self._finish_calibration():
                return False
        else:
            self.calibrating = False
        return True

    def process_frame(self, nose_y, left_shoulder_y, right_shoulder_y):
        self.pose_visible = True

        if self.calibrating:
            self.update_calibration(nose_y, left_shoulder_y, right_shoulder_y)
            return

        if self.baseline_ratio is None:
            return

        current_ratio = self.get_ratio(nose_y, left_shoulder_y, right_shoulder_y)
        self.head_drop_ratio = current_ratio
        droop_amount = current_ratio - self.baseline_ratio

        if droop_amount > self.droop_pixel_threshold:
            self.consecutive_droop_frames += 1
        else:
            self.consecutive_droop_frames = 0

        self.head_down = (
            self.consecutive_droop_frames >= self.droop_frame_threshold
        )

        max_droop = 100.0
        self.posture_score = min(max(droop_amount / max_droop, 0.0), 1.0)

    def set_pose_not_visible(self):
        self.pose_visible = False


class HeadPostureMonitor:
    DEFAULT_STATE_TOPIC = "/head_posture_state"
    DEFAULT_POSE_TOPIC = "/mediapipe/pose_landmarks"

    def __init__(self):
        rospy.init_node("head_posture_monitor")
        rospy.on_shutdown(self.cleanup)

        self.logic = HeadPostureLogic()
        self._last_session_active = False

        self.logic.calibration_duration = rospy.get_param(
            "~calibration_duration", 30.0
        )
        self.logic.droop_frame_threshold = int(
            rospy.get_param("~droop_frame_threshold", 15)
        )
        self.logic.droop_pixel_threshold = float(
            rospy.get_param("~droop_pixel_threshold", 30.0)
        )
        self.min_visibility = float(
            rospy.get_param("~min_landmark_visibility", 0.5)
        )
        self.image_height = float(rospy.get_param("~image_height", 480.0))
        self.coords_normalized = rospy.get_param("~coords_normalized", True)

        self.pose_topic = rospy.get_param(
            "~pose_topic", self.DEFAULT_POSE_TOPIC
        )
        self.state_topic = rospy.get_param(
            "~state_topic", self.DEFAULT_STATE_TOPIC
        )
        self.session_active_topic = rospy.get_param("~session_active_topic", "")

        self.publisher = rospy.Publisher(
            self.state_topic, HeadPosture, queue_size=10
        )

        pose_msg_module = rospy.get_param("~pose_msg_module", "")
        pose_msg_type = rospy.get_param("~pose_msg_type", "")

        if pose_msg_module and pose_msg_type:
            pose_msg_class = self._load_pose_message_class(
                pose_msg_module, pose_msg_type
            )
            rospy.Subscriber(self.pose_topic, pose_msg_class, self.pose_callback)
            rospy.loginfo(
                "Subscribed to: %s (%s/%s)",
                self.pose_topic,
                pose_msg_module,
                pose_msg_type,
            )
        else:
            rospy.logwarn(
                "MediaPipe subscriber disabled. On the robot, set private params "
                "~pose_msg_module and ~pose_msg_type after running: "
                "rostopic info %s",
                self.pose_topic,
            )

        if self.session_active_topic:
            rospy.Subscriber(
                self.session_active_topic,
                Bool,
                self._on_session_active,
                queue_size=10,
            )
            rospy.loginfo(
                "Session-aware calibration enabled on %s",
                self.session_active_topic,
            )

        rospy.loginfo("HeadPostureMonitor started.")
        rospy.loginfo("Publishing to: %s", self.state_topic)

        self.publish_state(rospy.Time.now())

    def _load_pose_message_class(self, module_name, type_name):
        try:
            msg_module = importlib.import_module("%s.msg" % module_name)
            return getattr(msg_module, type_name)
        except (ImportError, AttributeError) as exc:
            rospy.logfatal(
                "Could not import %s.msg.%s: %s",
                module_name,
                type_name,
                exc,
            )
            raise

    def _on_session_active(self, msg):
        if msg.data and not self._last_session_active:
            self.logic.reset_calibration()
            rospy.loginfo(
                "Focus session started — recalibrating head posture baseline"
            )
        self._last_session_active = msg.data

    def cleanup(self):
        rospy.loginfo("HeadPostureMonitor shutting down.")

    def pose_callback(self, msg):
        now = rospy.Time.now()

        try:
            landmarks = self._extract_landmarks(msg)
            if not landmarks or len(landmarks) < 13:
                self.logic.set_pose_not_visible()
                self.publish_state(now)
                return

            nose = landmarks[0]
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]

            if (
                nose.visibility < self.min_visibility
                or left_shoulder.visibility < self.min_visibility
                or right_shoulder.visibility < self.min_visibility
            ):
                self.logic.set_pose_not_visible()
                self.publish_state(now)
                return

            nose_y = self._scale_coord(nose.y)
            left_shoulder_y = self._scale_coord(left_shoulder.y)
            right_shoulder_y = self._scale_coord(right_shoulder.y)

            self.logic.process_frame(
                nose_y, left_shoulder_y, right_shoulder_y
            )

        except Exception as exc:
            rospy.logwarn_throttle(5.0, "Landmark error: %s", exc)
            self.logic.set_pose_not_visible()

        self.publish_state(now)

    def _scale_coord(self, value):
        if self.coords_normalized:
            return value * self.image_height
        return value

    @staticmethod
    def _extract_landmarks(msg):
        """Support common MediaPipe / pose message field layouts."""
        for attr in ("landmark", "landmarks", "pose_landmarks"):
            landmarks = getattr(msg, attr, None)
            if landmarks:
                return landmarks
        return None

    def publish_state(self, stamp):
        msg = HeadPosture()
        msg.pose_visible = self.logic.pose_visible
        msg.calibrated = self.logic.calibrated
        msg.head_down = self.logic.head_down
        msg.posture_score = self.logic.posture_score
        msg.head_drop_ratio = self.logic.head_drop_ratio
        msg.baseline_ratio = (
            self.logic.baseline_ratio
            if self.logic.baseline_ratio is not None
            else 0.0
        )
        msg.consecutive_droop_frames = self.logic.consecutive_droop_frames
        msg.stamp = stamp
        self.publisher.publish(msg)

        rospy.loginfo_throttle(
            2.0,
            "pose_visible=%s calibrated=%s head_down=%s score=%.2f",
            msg.pose_visible,
            msg.calibrated,
            msg.head_down,
            msg.posture_score,
        )


def print_state_callback(msg):
    print("")
    print("stamp                    : %s" % msg.stamp)
    print("pose_visible             : %s" % msg.pose_visible)
    print("calibrated               : %s" % msg.calibrated)
    print("head_down                : %s" % msg.head_down)
    print("posture_score            : %.3f" % msg.posture_score)
    print("head_drop_ratio          : %.3f" % msg.head_drop_ratio)
    print("baseline_ratio           : %.3f" % msg.baseline_ratio)
    print("consecutive_droop_frames : %d" % msg.consecutive_droop_frames)


def run_debug_printer():
    rospy.init_node("head_posture_debug_printer")
    state_topic = rospy.get_param(
        "~state_topic", HeadPostureMonitor.DEFAULT_STATE_TOPIC
    )
    rospy.Subscriber(state_topic, HeadPosture, print_state_callback)
    rospy.loginfo("Debug printer subscribed to %s", state_topic)
    rospy.spin()


def main():
    args = rospy.myargv(argv=sys.argv)
    if "--print" in args:
        run_debug_printer()
    else:
        HeadPostureMonitor()
        rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
