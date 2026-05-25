# Head Posture Module

Module 6: converts MediaPipe pose landmarks into a compact head-posture topic for the focus robot.

## ROS Contract

Input (on robot — discover with `rostopic info`):

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

Start the camera and MediaPipe pose first, then discover the pose message type:

```bash
rostopic list | grep -i pose
rostopic info /mediapipe/pose_landmarks
rostopic echo /mediapipe/pose_landmarks -n1
```

Then start this module (replace package and type from `rostopic info`):

```bash
roslaunch head_posture_module head_posture_monitor.launch \
  pose_msg_module:=YOUR_PACKAGE \
  pose_msg_type:=YOUR_MESSAGE_TYPE
```

Optional session-aware recalibration when Member 4 publishes `std_msgs/Bool`:

```bash
roslaunch head_posture_module head_posture_monitor.launch \
  pose_msg_module:=YOUR_PACKAGE \
  pose_msg_type:=YOUR_MESSAGE_TYPE \
  session_active_topic:=/focus_robot/session_active
```

## Test And Screenshots

Use these commands for online testing and report screenshots:

```bash
rostopic info /mediapipe/pose_landmarks
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
