#!/usr/bin/env python
"""
Session Manager Node — Member 4
Owns session lifecycle and synthesises fatigue signals into a unified SessionState.

TODO (Member 4):
  - Subscribe to SessionCommand (from voice_command) to start/stop sessions
  - Subscribe to fatigue_level and user_state to build a holistic picture
  - Publish SessionState with current session status and aggregated fatigue level
  - Drive robot behaviour (LED, motion, TTS) based on session state

Subscriptions:
  /focus_robot/session_command       focus_robot/SessionCommand
  /focus_robot/fatigue_level         std_msgs/Int32
  /vision_and_presence_detection     focus_robot/UserState
  /head_posture_state                focus_robot/HeadPosture

Publications:
  /focus_robot/session_state         focus_robot/SessionState
"""

import rospy
from std_msgs.msg import Int32
from focus_robot.msg import SessionCommand, SessionState, UserState, HeadPosture
from constants import (
    SESSION_COMMAND_TOPIC,
    FATIGUE_LEVEL_TOPIC,
    USER_STATE_TOPIC,
    HEAD_POSTURE_TOPIC,
    SESSION_STATE_TOPIC,
)


class SessionManagerNode:
    def __init__(self):
        rospy.init_node("session_manager")

        self.pub = rospy.Publisher(
            SESSION_STATE_TOPIC, SessionState, queue_size=10
        )

        rospy.Subscriber(SESSION_COMMAND_TOPIC, SessionCommand, self._on_command)
        rospy.Subscriber(FATIGUE_LEVEL_TOPIC, Int32, self._on_fatigue)
        rospy.Subscriber(USER_STATE_TOPIC, UserState, self._on_user_state)
        rospy.Subscriber(HEAD_POSTURE_TOPIC, HeadPosture, self._on_head_posture)

        rospy.loginfo("SessionManagerNode started")

    def _on_command(self, msg):
        # TODO: implement session start/stop logic
        rospy.loginfo_throttle(5.0, "session_manager stub — command: %s", msg.command)

    def _on_fatigue(self, msg):
        pass  # TODO: use fatigue level in session state

    def _on_user_state(self, msg):
        pass  # TODO: use presence info

    def _on_head_posture(self, msg):
        pass  # TODO: use head posture info

    def run(self):
        rospy.spin()


if __name__ == "__main__":
    try:
        SessionManagerNode().run()
    except rospy.ROSInterruptException:
        pass
