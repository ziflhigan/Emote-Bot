# Vision Presence Module

Module 2: converts the existing OpenCV face detection topic into a compact user-state topic for the focus robot.

## ROS Contract

Input:

```text
/face_detection/faces
opencv_apps/FaceArrayStamped
```

Output:

```text
/focus_robot/user_state
vision_presence_module/UserState
```

Message fields:

```text
bool user_present
int32 consecutive_eyes_missing
int32 consecutive_face_absent
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

Start the camera and OpenCV face detection first:

```bash
roslaunch usb_cam usb_cam-test.launch
roslaunch opencv_apps face_detection.launch image:=/usb_cam/image_raw
```

Then start this module:

```bash
roslaunch vision_presence_module user_state_monitor.launch
```

## Test And Screenshots

Use these commands for online testing and report screenshots:

```bash
rostopic info /face_detection/faces
rostopic info /focus_robot/user_state
rostopic echo /focus_robot/user_state
rostopic hz /focus_robot/user_state
rosmsg show vision_presence_module/UserState
rosnode info /user_state_monitor
```

For a terminal printer:

```bash
rosrun vision_presence_module user_state_monitor.py --print
```
