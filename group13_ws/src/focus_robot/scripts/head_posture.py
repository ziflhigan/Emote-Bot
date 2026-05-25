#!/usr/bin/env python

import importlib
import sys

import rospy
from std_msgs.msg import Bool

from focus_robot.msg import HeadPosture
from head_posture_monitor import HeadPostureMonitor


def _scale_coord(value, image_height, coords_normalized):
    if coords_normalized:
        return value * image_height
    return value


def _extract_landmarks(msg):
    """Support common MediaPipe / pose message field layouts."""
    for attr in ("landmark", "landmarks", "pose_landmarks"):
        landmarks = getattr(msg, attr, None)
        if landmarks:
            return landmarks
    return None


class HeadPostureNode:
    DEFAULT_STATE_TOPIC = "/head_posture_state"
    DEFAULT_POSE_TOPIC = "/mediapipe/pose_landmarks"

    def __init__(self):
        rospy.init_node("head_posture_node")
        rospy.on_shutdown(self._on_shutdown)

        self.monitor = HeadPostureMonitor()
        self._last_session_active = False

        self.monitor.calibration_duration = rospy.get_param(
            "~calibration_duration",
            rospy.get_param("head_posture/calibration_duration", 30.0),
        )
        self.monitor.droop_frame_threshold = int(
            rospy.get_param(
                "~droop_frame_threshold",
                rospy.get_param("head_posture/droop_frame_threshold", 15),
            )
        )
        self.monitor.droop_pixel_threshold = float(
            rospy.get_param(
                "~droop_pixel_threshold",
                rospy.get_param("head_posture/droop_pixel_threshold", 30.0),
            )
        )
        self.min_visibility = float(
            rospy.get_param(
                "~min_landmark_visibility",
                rospy.get_param("head_posture/min_landmark_visibility", 0.5),
            )
        )
        self.image_height = float(
            rospy.get_param(
                "~image_height",
                rospy.get_param("head_posture/image_height", 480.0),
            )
        )
        self.coords_normalized = rospy.get_param(
            "~coords_normalized",
            rospy.get_param("head_posture/coords_normalized", True),
        )

        self.pose_topic = rospy.get_param(
            "~pose_topic",
            rospy.get_param("head_posture/pose_topic", self.DEFAULT_POSE_TOPIC),
        )
        self.state_topic = rospy.get_param(
            "~state_topic",
            rospy.get_param("head_posture/state_topic", self.DEFAULT_STATE_TOPIC),
        )
        self.session_active_topic = rospy.get_param("~session_active_topic", "")

        self.pub = rospy.Publisher(self.state_topic, HeadPosture, queue_size=10)

        pose_msg_module = rospy.get_param("~pose_msg_module", "")
        pose_msg_type = rospy.get_param("~pose_msg_type", "")

        if pose_msg_module and pose_msg_type:
            pose_msg_class = self._load_pose_message_class(
                pose_msg_module, pose_msg_type
            )
            rospy.Subscriber(self.pose_topic, pose_msg_class, self.callback)
            rospy.loginfo(
                "Subscribed to %s (%s/%s)",
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

        rospy.loginfo("HeadPostureNode started")
        rospy.loginfo("Publishing to: %s", self.state_topic)

        self._publish(rospy.Time.now())

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
            self.monitor.reset_calibration()
            rospy.loginfo("Focus session started — recalibrating head posture baseline")
        self._last_session_active = msg.data

    def _on_shutdown(self):
        rospy.loginfo("HeadPostureNode shutting down")

    def callback(self, msg):
        now = rospy.Time.now()

        try:
            landmarks = _extract_landmarks(msg)
            if not landmarks or len(landmarks) < 13:
                self.monitor.set_pose_not_visible()
                self._publish(now)
                return

            nose = landmarks[0]
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]

            if (
                nose.visibility < self.min_visibility
                or left_shoulder.visibility < self.min_visibility
                or right_shoulder.visibility < self.min_visibility
            ):
                self.monitor.set_pose_not_visible()
                self._publish(now)
                return

            nose_y = _scale_coord(
                nose.y, self.image_height, self.coords_normalized
            )
            left_shoulder_y = _scale_coord(
                left_shoulder.y, self.image_height, self.coords_normalized
            )
            right_shoulder_y = _scale_coord(
                right_shoulder.y, self.image_height, self.coords_normalized
            )

            self.monitor.process_frame(
                nose_y, left_shoulder_y, right_shoulder_y
            )

        except Exception as exc:
            rospy.logwarn_throttle(5.0, "Landmark error: %s", exc)
            self.monitor.set_pose_not_visible()

        self._publish(now)

    def _publish(self, stamp):
        out = HeadPosture()
        out.pose_visible = self.monitor.pose_visible
        out.calibrated = self.monitor.calibrated
        out.head_down = self.monitor.head_down
        out.posture_score = self.monitor.posture_score
        out.head_drop_ratio = self.monitor.head_drop_ratio
        out.baseline_ratio = (
            self.monitor.baseline_ratio
            if self.monitor.baseline_ratio is not None
            else 0.0
        )
        out.consecutive_droop_frames = self.monitor.consecutive_droop_frames
        out.stamp = stamp
        self.pub.publish(out)

        rospy.loginfo_throttle(
            2.0,
            "pose_visible=%s calibrated=%s head_down=%s score=%.2f",
            out.pose_visible,
            out.calibrated,
            out.head_down,
            out.posture_score,
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
    state_topic = rospy.get_param("~state_topic", HeadPostureNode.DEFAULT_STATE_TOPIC)
    rospy.Subscriber(state_topic, HeadPosture, print_state_callback)
    rospy.loginfo("Debug printer subscribed to %s", state_topic)
    rospy.spin()


def main():
    args = rospy.myargv(argv=sys.argv)
    if "--print" in args:
        run_debug_printer()
    else:
        HeadPostureNode()
        rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
