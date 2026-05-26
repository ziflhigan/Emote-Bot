#!/usr/bin/env python3

"""
voice_command.py
================

VOICE INPUT AND COMMAND PARSING MODULE - ROS NODE

This node listens to the user's microphone, transcribes spoken
phrases into text using the SpeechRecognition library already
installed on the shared robot, and publishes the parsed command
text on /voice_command for the session manager (Module 7) to
consume.

A wake-word prefix ("robot ...") is enforced for safety: any
machine on the local network can publish to a ROS topic, so we
only act on phrases that begin with the configured wake word.
The wake word itself is stripped before publishing, so downstream
nodes only see the command body (e.g. user says "robot start
session" -> /voice_command publishes "start session").

INPUTS
    Microphone audio (default ALSA capture device).
    No ROS subscribers - this is a sensor-edge node.

OUTPUTS
    /voice_command  (std_msgs/String)
        Lowercased, wake-word-stripped command body. Published
        only when a full phrase has been recognised AND has
        passed the wake-word gate.

PARAMS
    ~wake_word        (string, default: "robot")
        Set to "" to disable the gate (NOT recommended on a
        shared network).
    ~ambient_seconds  (float,  default: 2.0)
        How long to sample background noise on startup.
    ~phrase_limit     (float,  default: 5.0)
        Max seconds of a single utterance before recognition
        is forced to run.
    ~command_topic    (string, default: "/voice_command")

LAUNCH ORDER (no new packages required):
    $ roscore
    $ rosrun emote_bot voice_command.py

MODULE BOUNDARY
    This node REPORTS what the user said. It does not decide
    what to do with the command, does not move the robot, and
    does not start or end sessions. The session manager
    consumes /voice_command and acts on it.

DEPENDENCIES (all already installed on the shared robot)
    - rospy                   1.16.0   (Noetic, Python 3)
    - std_msgs                1.13.1
    - SpeechRecognition       3.10.4
    - PyAudio                 0.2.14
    - sounddevice             0.4.6    (used to enumerate input
                                        devices for diagnostics)
    - requests                2.31.0   (used internally by
                                        recognize_google())

    No pip install, no apt install. Shared-robot-safe.

NETWORK NOTE
    recognize_google() reaches the public Google Web Speech
    endpoint. Internet must be reachable from the robot. No API
    key is required for development-volume traffic.
"""

import sys

import rospy
import sounddevice as sd
import speech_recognition as sr
from std_msgs.msg import String


class VoiceCommandLogic:
    """Wake-word filtering and text normalisation for spoken phrases."""

    def __init__(self, wake_word):
        self.wake_word = (wake_word or "").lower().strip()

    def normalise(self, raw_text):
        """Lowercase + strip. Returns '' if input is None/empty."""
        if not raw_text:
            return ""
        return raw_text.lower().strip()

    def extract_command(self, raw_text):
        """
        Apply the wake-word gate.

        Returns (accepted, payload):
            accepted (bool) - True if the phrase passed the gate
            payload  (str)  - text AFTER the wake word, stripped.
                              Empty string means: heard the wake
                              word but no command body followed.
        """
        text = self.normalise(raw_text)
        if not text:
            return False, ""
        if not self.wake_word:
            return True, text
        if not text.startswith(self.wake_word):
            return False, text
        payload = text[len(self.wake_word):].strip()
        return True, payload


class VoiceCommandNode:
    def __init__(self):
        rospy.init_node("voice_command")
        rospy.on_shutdown(self.cleanup)

        self.wake_word = rospy.get_param("~wake_word", "robot")
        self.ambient_seconds = float(rospy.get_param("~ambient_seconds", 2.0))
        self.phrase_limit = float(rospy.get_param("~phrase_limit", 5.0))
        self.command_topic = rospy.get_param("~command_topic", "/voice_command")

        self.logic = VoiceCommandLogic(self.wake_word)
        self.pub = rospy.Publisher(self.command_topic, String, queue_size=10)

        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

        rospy.loginfo("VoiceCommandNode started.")
        rospy.loginfo("  Wake word     : '%s'", self.wake_word)
        rospy.loginfo("  Publishing to : %s", self.command_topic)
        rospy.loginfo("  Phrase limit  : %.1fs", self.phrase_limit)
        self._log_input_devices()
        self._calibrate()

    def cleanup(self):
        rospy.loginfo("VoiceCommandNode shutting down.")

    def _log_input_devices(self):
        """Use sounddevice to enumerate capture devices for diagnostics."""
        try:
            devices = sd.query_devices()
        except Exception as exc:
            rospy.logwarn("Could not query audio devices: %s", exc)
            return
        inputs = [
            (i, d["name"]) for i, d in enumerate(devices)
            if d.get("max_input_channels", 0) > 0
        ]
        if not inputs:
            rospy.logwarn("No microphone input devices detected!")
            return
        rospy.loginfo("Detected %d input device(s):", len(inputs))
        for idx, name in inputs:
            rospy.loginfo("    [%d] %s", idx, name)

    def _calibrate(self):
        with self.microphone as source:
            rospy.loginfo("Calibrating microphone (%.1fs)...", self.ambient_seconds)
            self.recognizer.adjust_for_ambient_noise(
                source, duration=self.ambient_seconds
            )
        rospy.loginfo(
            "Calibration complete. Say '%s <command>' to talk.",
            self.wake_word,
        )

    def _transcribe(self, audio_data):
        """
        Run Google Web Speech on the captured audio.
        Returns the text or None on any recoverable failure.
        """
        try:
            return self.recognizer.recognize_google(audio_data)
        except sr.UnknownValueError:
            rospy.logwarn_throttle(2.0, "Could not understand the audio.")
        except sr.RequestError as exc:
            rospy.logerr(
                "Speech engine request failed (check internet): %s", exc
            )
        return None

    def listen_once(self):
        """Capture one utterance from the mic and publish it if accepted."""
        with self.microphone as source:
            try:
                audio_data = self.recognizer.listen(
                    source,
                    timeout=None,
                    phrase_time_limit=self.phrase_limit,
                )
            except sr.WaitTimeoutError:
                return

        raw_text = self._transcribe(audio_data)
        if raw_text is None:
            return

        accepted, payload = self.logic.extract_command(raw_text)
        rospy.loginfo(
            "Heard: '%s' -> accepted=%s payload='%s'",
            raw_text, accepted, payload,
        )

        if accepted and payload:
            self.pub.publish(payload)

    def run(self):
        while not rospy.is_shutdown():
            self.listen_once()


def print_command_callback(msg):
    print("voice_command : %s" % msg.data)


def run_debug_printer():
    rospy.init_node("voice_command_debug_printer")
    topic = rospy.get_param("~command_topic", "/voice_command")
    rospy.Subscriber(topic, String, print_command_callback)
    rospy.loginfo("Voice command debug printer subscribed to %s", topic)
    rospy.spin()


def main():
    args = rospy.myargv(argv=sys.argv)
    if "--print" in args:
        run_debug_printer()
    else:
        VoiceCommandNode().run()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        rospy.loginfo("voice_command node terminated.")
