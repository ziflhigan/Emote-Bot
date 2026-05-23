#!/usr/bin/env python

import sys

import rospy
from opencv_apps.msg import FaceArrayStamped
from vision_presence_module.msg import UserState


class UserStateLogic:
    """Tracks face and eye presence across consecutive callbacks."""

    def __init__(self):
        self.user_present = False
        self.consecutive_eyes_missing = 0
        self.consecutive_face_absent = 0
        self.last_face_seen = None
        self.last_eyes_seen = None

    def update(self, faces_exist, eyes_exist, timestamp):
        if not faces_exist:
            eyes_exist = False

        if faces_exist and eyes_exist:
            self.user_present = True
            self.consecutive_eyes_missing = 0
            self.consecutive_face_absent = 0
            self.last_face_seen = timestamp
            self.last_eyes_seen = timestamp
        elif faces_exist:
            self.user_present = True
            self.consecutive_eyes_missing += 1
            self.consecutive_face_absent = 0
            self.last_face_seen = timestamp
        else:
            self.user_present = False
            self.consecutive_face_absent += 1


class UserStateMonitor:
    def __init__(self):
        rospy.init_node("user_state_monitor")
        rospy.on_shutdown(self.cleanup)

        self.logic = UserStateLogic()
        self.face_topic = rospy.get_param(
            "~face_topic", "/face_detection/faces"
        )
        self.state_topic = rospy.get_param(
            "~state_topic", "/focus_robot/user_state"
        )

        self.publisher = rospy.Publisher(
            self.state_topic, UserState, queue_size=10
        )
        rospy.Subscriber(
            self.face_topic, FaceArrayStamped, self.face_callback
        )

        rospy.loginfo("UserStateMonitor started.")
        rospy.loginfo("Subscribed to: %s", self.face_topic)
        rospy.loginfo("Publishing to: %s", self.state_topic)

    def cleanup(self):
        rospy.loginfo("UserStateMonitor shutting down.")

    def _eyes_exist(self, faces):
        for face_item in faces:
            if face_item.eyes:
                return True
        return False

    def face_callback(self, msg):
        faces = msg.faces
        faces_exist = len(faces) > 0
        eyes_exist = self._eyes_exist(faces) if faces_exist else False

        self.logic.update(
            faces_exist=faces_exist,
            eyes_exist=eyes_exist,
            timestamp=rospy.Time.now().to_sec(),
        )
        self.publish_state()

    def publish_state(self):
        msg = UserState()
        msg.user_present = self.logic.user_present
        msg.consecutive_eyes_missing = self.logic.consecutive_eyes_missing
        msg.consecutive_face_absent = self.logic.consecutive_face_absent
        self.publisher.publish(msg)

        rospy.loginfo_throttle(
            2.0,
            "user_present=%s eyes_missing=%d face_absent=%d",
            self.logic.user_present,
            self.logic.consecutive_eyes_missing,
            self.logic.consecutive_face_absent,
        )


def print_state_callback(msg):
    print("")
    print("user_present             : %s" % msg.user_present)
    print("consecutive_eyes_missing : %d" % msg.consecutive_eyes_missing)
    print("consecutive_face_absent  : %d" % msg.consecutive_face_absent)


def run_debug_printer():
    rospy.init_node("user_state_debug_printer")
    state_topic = rospy.get_param(
        "~state_topic", "/focus_robot/user_state"
    )
    rospy.Subscriber(state_topic, UserState, print_state_callback)
    rospy.loginfo("Debug printer subscribed to %s", state_topic)
    rospy.spin()


def main():
    args = rospy.myargv(argv=sys.argv)
    if "--print" in args:
        run_debug_printer()
    else:
        UserStateMonitor()
        rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
