#!/usr/bin/env python
"""
Shared topic names and interfaces for the focus_robot package.

Each node defines its own tunable thresholds internally (CFG dict in
fatigue_monitor.py, ROS params in head_posture.py). This file centralises
the ROS topic names that connect nodes so they stay in sync.
"""

# ── Topic names ────────────────────────────────────────────────────────────

# Module 2 — Vision / Presence
FACE_DETECTION_TOPIC      = "/face_detection/faces"          # subscribed
USER_STATE_TOPIC          = "/vision_and_presence_detection"  # published

# Module 5 — Fatigue Monitor
RAW_IMAGE_TOPIC           = "/usb_cam/image_raw"             # subscribed
VOICE_RECOGNIZER_TOPIC    = "/recognizer/output"             # subscribed
SESSION_ACTIVE_TOPIC      = "/focus_robot/session_active"    # published
FATIGUE_LEVEL_TOPIC       = "/focus_robot/fatigue_level"     # published

# Module 6 — Head Posture
MEDIAPIPE_POSE_TOPIC      = "/mediapipe/pose_landmarks"      # subscribed
HEAD_POSTURE_TOPIC        = "/head_posture_state"            # published

# Module 3 — Voice Command (stub — to be implemented by Member 3)
SESSION_COMMAND_TOPIC     = "/focus_robot/session_command"   # published

# Module 4 — Session Manager (stub — to be implemented by Member 4)
SESSION_STATE_TOPIC       = "/focus_robot/session_state"     # published
