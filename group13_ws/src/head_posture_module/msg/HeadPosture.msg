# Head posture evidence from the MediaPipe pose node.
# Input to the fatigue monitor; does not trigger speech by itself.

bool pose_visible
bool calibrated
bool head_down

float32 posture_score
float32 head_drop_ratio
float32 baseline_ratio

int32 consecutive_droop_frames
time stamp
