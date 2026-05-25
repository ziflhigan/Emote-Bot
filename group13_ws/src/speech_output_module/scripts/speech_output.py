#!/usr/bin/env python3

"""
speech_output.py
================

TEXT-TO-SPEECH OUTPUT MODULE - ROS NODE

This node is the robot-side adapter for the Text-to-Speech
Output Module. It subscribes to /tts_request and asks the
sound_play server to speak whatever text arrives.

It is the symmetric counterpart of voice_command.py:
    voice_command   : microphone -> /voice_command (text)
    speech_output   : /tts_request (text) -> speakers

INPUTS
    /tts_request  (std_msgs/String)
        The text the robot should speak. Typically published
        by session_manager (e.g. "Session started.") or
        fatigue_monitor (e.g. "Take a break.").

OUTPUTS
    Audio on the robot's speakers, via the sound_play server.
    No ROS publishers - this is a sink node.

LAUNCH ORDER
    A single launch file brings up both the sound_play server
    AND this client:

        roslaunch speech_output_module speech_output.launch

    The launch file starts soundplay_node alongside, exactly
    like say_hello_ans.launch does for the kids module.

MODULE BOUNDARY
    This node SPEAKS what it is told. It does not decide what
    to say, does not detect fatigue, does not manage sessions,
    does not parse voice commands. Those are other modules'
    responsibilities.

DEPENDENCIES
    Only packages already installed on the shared robot:
      - rospy
      - std_msgs
      - sound_play           (ROS package, used by say_hello_ans.py)
    No pip install, no apt install. Shared-robot-safe.
"""

import sys

import rospy
from sound_play.libsoundplay import SoundClient
from std_msgs.msg import String


class SpeechOutputNode:
    def __init__(self):
        rospy.init_node("speech_output")
        rospy.on_shutdown(self.cleanup)

        self.tts_topic = rospy.get_param("~tts_topic", "/tts_request")
        self.dedupe_seconds = float(rospy.get_param("~dedupe_seconds", 5.0))
        self.connect_delay = float(rospy.get_param("~connect_delay", 1.0))
        self.voice = rospy.get_param("~voice", "")  # empty = sound_play default
        self.volume = float(rospy.get_param("~volume", 1.0))

        # SoundClient is the python wrapper around soundplay_node.
        # blocking=False so this node's callback returns immediately
        # and ROS keeps processing other messages while audio plays.
        self.soundhandle = SoundClient()

        # Give the client time to discover and connect to soundplay_node.
        # Same pattern as say_hello_ans.py.
        rospy.sleep(self.connect_delay)
        self.soundhandle.stopAll()

        self._last_text = None
        self._last_time = None

        rospy.Subscriber(self.tts_topic, String, self.on_request)

        rospy.loginfo("SpeechOutputNode started.")
        rospy.loginfo("  Subscribing to : %s", self.tts_topic)
        rospy.loginfo("  Dedupe window  : %.1fs", self.dedupe_seconds)
        rospy.loginfo("  Voice          : %r", self.voice or "(default)")
        rospy.loginfo("  Volume         : %.2f", self.volume)
        rospy.loginfo("Ready. Publish to %s to make the robot speak.",
                      self.tts_topic)

    def cleanup(self):
        rospy.loginfo("SpeechOutputNode shutting down. Stopping all audio.")
        try:
            self.soundhandle.stopAll()
        except Exception as exc:
            rospy.logwarn("stopAll failed during shutdown: %s", exc)

    def on_request(self, msg):
        text = (msg.data or "").strip()
        if not text:
            rospy.logwarn("Ignoring empty TTS request.")
            return

        now = rospy.Time.now()
        if self._is_duplicate(text, now):
            rospy.loginfo_throttle(
                2.0,
                "Suppressed duplicate TTS within %.1fs: %r" % (
                    self.dedupe_seconds, text,
                ),
            )
            return

        self._last_text = text
        self._last_time = now

        rospy.loginfo("Speaking: %r", text)
        try:
            # SoundClient.say(text, voice='', volume=1.0)
            # Empty voice -> sound_play default (festival on Ubuntu).
            self.soundhandle.say(text, self.voice, self.volume)
        except Exception as exc:
            rospy.logerr("SoundClient.say() failed: %s", exc)

    def _is_duplicate(self, text, now):
        if self._last_text != text:
            return False
        if self._last_time is None:
            return False
        elapsed = (now - self._last_time).to_sec()
        return elapsed < self.dedupe_seconds


def main():
    SpeechOutputNode()
    rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        rospy.loginfo("speech_output node terminated.")
