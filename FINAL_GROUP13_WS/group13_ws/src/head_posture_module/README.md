# Head Posture Module

Module 6: runs MediaPipe Pose on the USB camera and publishes compact head-posture evidence for the focus robot (same camera path as `fatigue_monitor`).

## ROS Contract

Input (default):

```text
/usb_cam/image_raw
sensor_msgs/Image
```

Optional external pose (set `use_external_pose:=true`):

```text
/mediapipe/pose_landmarks
<package>/<PoseMessageType>
```

Output:

```text
Topic name:   /head_posture_state
Message type: head_posture_module/HeadPosture
```

Message fields:

```text
bool pose_visible
bool calibrated
bool head_down
float32 posture_score
float32 head_drop_ratio
float32 baseline_ratio
int32 consecutive_droop_frames
time stamp
```

This module only reports camera evidence. It does not decide fatigue, manage sessions, parse voice commands, or speak.

## Build

From the workspace root:

```bash
cd ~/Emote-Bot/group13_ws
catkin_make
source devel/setup.bash
```

## Run

```bash
roslaunch usb_cam usb_cam-test.launch
roslaunch head_posture_module head_posture_monitor.launch
```

Session-aware recalibration listens on `/focus_robot/session_active` by default (same topic as `fatigue_monitor`).

Optional debug preview window:

```bash
roslaunch head_posture_module head_posture_monitor.launch show_window:=true
```

## Test And Screenshots

Use these commands for online testing and report screenshots:

```bash
rostopic info /usb_cam/image_raw
rostopic info /head_posture_state
rostopic echo /head_posture_state
rostopic hz /head_posture_state
rosmsg show head_posture_module/HeadPosture
rosnode info /head_posture_monitor
```

For a terminal printer:

```bash
rosrun head_posture_module head_posture_monitor.py --print
```

For teammate handoff, see `MODULE6_HANDOFF.md`.
