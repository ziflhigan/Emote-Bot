#!/usr/bin/env python
"""
Voice Command Node — Member 3
Subscribes to the speech recogniser and publishes structured SessionCommand messages.

TODO (Member 3):
  - Parse recognised phrases into discrete commands (START, STOP, PAUSE, …)
  - Publish focus_robot/SessionCommand on SESSION_COMMAND_TOPIC
  - Optionally gate commands on session state from session_manager

Subscriptions:
  /recognizer/output   std_msgs/String   (pocketsphinx raw output)

Publications:
  /focus_robot/session_command   focus_robot/SessionCommand
"""

import rospy
from std_msgs.msg import String
from focus_robot.msg import SessionCommand
from constants import VOICE_RECOGNIZER_TOPIC, SESSION_COMMAND_TOPIC


class VoiceCommandNode:
    def __init__(self):
        rospy.init_node("voice_command")

        self.pub = rospy.Publisher(
            SESSION_COMMAND_TOPIC, SessionCommand, queue_size=10
        )
        rospy.Subscriber(VOICE_RECOGNIZER_TOPIC, String, self._callback)

        rospy.loginfo("VoiceCommandNode started — listening on %s", VOICE_RECOGNIZER_TOPIC)

    def _callback(self, msg):
        # TODO: implement command parsing
        rospy.loginfo_throttle(5.0, "voice_command stub received: %s", msg.data)

    def run(self):
        rospy.spin()


if __name__ == "__main__":
    try:
        VoiceCommandNode().run()
    except rospy.ROSInterruptException:
        pass
