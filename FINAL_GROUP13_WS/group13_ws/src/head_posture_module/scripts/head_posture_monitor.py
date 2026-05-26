#!/usr/bin/env python3
"""
Head Posture Monitor — ROS Node
Module 6 — head_posture_module package

Same camera stack as fatigue_monitor (usb_cam + MediaPipe on board).

Run sequence:
  Terminal 1: roscore
  Terminal 2: roslaunch usb_cam usb_cam-test.launch
  Terminal 3: roslaunch head_posture_module head_posture_monitor.launch

Publishes:
  /head_posture_state  head_posture_module/HeadPosture

Subscribes:
  /usb_cam/image_raw              sensor_msgs/Image   (default)
  /focus_robot/session_active     std_msgs/Bool       (optional recalibration)
"""

import importlib
import sys
import time

import cv2
import mediapipe as mp
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
from std_msgs.msg import Bool

from head_posture_module.msg import HeadPosture

# MediaPipe Pose landmark indices
NOSE = 0
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12


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
    DEFAULT_IMAGE_TOPIC = "/usb_cam/image_raw"
    DEFAULT_POSE_TOPIC = "/mediapipe/pose_landmarks"
    DEFAULT_SESSION_TOPIC = "/focus_robot/session_active"

    def __init__(self):
        rospy.init_node("head_posture_monitor")
        rospy.on_shutdown(self.cleanup)

        self.logic = HeadPostureLogic()
        self._last_session_active = False
        self.bridge = CvBridge()
        self.pose_detector = None
        self.show_window = False

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
        self.coords_normalized = rospy.get_param("~coords_normalized", True)

        self.image_topic = rospy.get_param(
            "~image_topic", self.DEFAULT_IMAGE_TOPIC
        )
        self.state_topic = rospy.get_param(
            "~state_topic", self.DEFAULT_STATE_TOPIC
        )
        self.session_active_topic = rospy.get_param(
            "~session_active_topic", self.DEFAULT_SESSION_TOPIC
        )
        self.use_external_pose = rospy.get_param("~use_external_pose", False)
        self.show_window = rospy.get_param("~show_window", False)

        self.pose_topic = rospy.get_param(
            "~pose_topic", self.DEFAULT_POSE_TOPIC
        )

        self.publisher = rospy.Publisher(
            self.state_topic, HeadPosture, queue_size=10
        )

        if self.use_external_pose:
            self._setup_external_pose_subscriber()
        else:
            self._setup_camera_subscriber()

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

    def _setup_camera_subscriber(self):
        mp_pose = mp.solutions.pose
        self.pose_detector = mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        rospy.Subscriber(
            self.image_topic, Image, self.image_callback, queue_size=1
        )
        rospy.loginfo("Subscribed to camera: %s", self.image_topic)

    def _setup_external_pose_subscriber(self):
        pose_msg_module = rospy.get_param("~pose_msg_module", "")
        pose_msg_type = rospy.get_param("~pose_msg_type", "")

        if not pose_msg_module or not pose_msg_type:
            rospy.logfatal(
                "use_external_pose is true but ~pose_msg_module / "
                "~pose_msg_type are not set. Run: rostopic info %s",
                self.pose_topic,
            )
            raise rospy.ROSException("Missing pose message type parameters")

        pose_msg_class = self._load_pose_message_class(
            pose_msg_module, pose_msg_type
        )
        rospy.Subscriber(self.pose_topic, pose_msg_class, self.pose_callback)
        rospy.loginfo(
            "Subscribed to external pose: %s (%s/%s)",
            self.pose_topic,
            pose_msg_module,
            pose_msg_type,
        )

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
        if self.pose_detector is not None:
            self.pose_detector.close()
            self.pose_detector = None
        cv2.destroyAllWindows()
        rospy.loginfo("HeadPostureMonitor shutting down.")

    def image_callback(self, msg):
        if self.pose_detector is None:
            return

        now = rospy.Time.now()
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as exc:
            rospy.logwarn_throttle(5.0, "CvBridge error: %s", exc)
            return

        frame = cv2.flip(frame, 1)
        image_height = frame.shape[0]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose_detector.process(rgb)

        if not results.pose_landmarks:
            self.logic.set_pose_not_visible()
            self.publish_state(now)
            self._maybe_show(frame)
            return

        landmarks = results.pose_landmarks.landmark
        if len(landmarks) < 13:
            self.logic.set_pose_not_visible()
            self.publish_state(now)
            self._maybe_show(frame)
            return

        nose = landmarks[NOSE]
        left_shoulder = landmarks[LEFT_SHOULDER]
        right_shoulder = landmarks[RIGHT_SHOULDER]

        if (
            nose.visibility < self.min_visibility
            or left_shoulder.visibility < self.min_visibility
            or right_shoulder.visibility < self.min_visibility
        ):
            self.logic.set_pose_not_visible()
            self.publish_state(now)
            self._maybe_show(frame)
            return

        nose_y = self._scale_coord(nose.y, image_height)
        left_shoulder_y = self._scale_coord(
            left_shoulder.y, image_height
        )
        right_shoulder_y = self._scale_coord(
            right_shoulder.y, image_height
        )

        self.logic.process_frame(
            nose_y, left_shoulder_y, right_shoulder_y
        )
        self.publish_state(now)
        self._maybe_show(frame)

    def _maybe_show(self, frame):
        if not self.show_window:
            return
        cv2.imshow("Head Posture Monitor", frame)
        cv2.waitKey(1)

    def pose_callback(self, msg):
        now = rospy.Time.now()
        image_height = float(rospy.get_param("~image_height", 480.0))

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

            nose_y = self._scale_coord(nose.y, image_height)
            left_shoulder_y = self._scale_coord(
                left_shoulder.y, image_height
            )
            right_shoulder_y = self._scale_coord(
                right_shoulder.y, image_height
            )

            self.logic.process_frame(
                nose_y, left_shoulder_y, right_shoulder_y
            )

        except Exception as exc:
            rospy.logwarn_throttle(5.0, "Landmark error: %s", exc)
            self.logic.set_pose_not_visible()

        self.publish_state(now)

    def _scale_coord(self, value, image_height):
        if self.coords_normalized:
            return value * image_height
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
