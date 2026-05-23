#!/usr/bin/env python

import time


class HeadPostureMonitor:
    """Pure logic for head droop detection (no ROS dependencies)."""

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
