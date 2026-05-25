#!/usr/bin/env python
"""
Integration test — verifies that all focus_robot nodes publish on expected topics.

Run after launching focus_session.launch:
  rosrun focus_robot test_integration.py

Checks:
  - /vision_and_presence_detection  (focus_robot/UserState)
  - /head_posture_state             (focus_robot/HeadPosture)
  - /focus_robot/session_active     (std_msgs/Bool)
  - /focus_robot/fatigue_level      (std_msgs/Int32)
"""

import sys
import rospy
from std_msgs.msg import Bool, Int32
from focus_robot.msg import UserState, HeadPosture

TIMEOUT = 10.0  # seconds to wait per topic

received = {}


def make_cb(key):
    def cb(msg):
        if key not in received:
            rospy.loginfo("PASS: received on %s", key)
        received[key] = True
    return cb


def main():
    rospy.init_node("test_integration", anonymous=True)

    checks = [
        ("/vision_and_presence_detection", UserState),
        ("/head_posture_state",            HeadPosture),
        ("/focus_robot/session_active",    Bool),
        ("/focus_robot/fatigue_level",     Int32),
    ]

    subs = []
    for topic, msg_type in checks:
        subs.append(rospy.Subscriber(topic, msg_type, make_cb(topic)))

    deadline = rospy.Time.now() + rospy.Duration(TIMEOUT)
    rate = rospy.Rate(2)

    while not rospy.is_shutdown() and rospy.Time.now() < deadline:
        if all(t in received for t, _ in checks):
            break
        rate.sleep()

    passed = all(t in received for t, _ in checks)
    for topic, _ in checks:
        status = "PASS" if topic in received else "FAIL"
        rospy.loginfo("[%s] %s", status, topic)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
