# Module 2 Handoff

This document is for the integration lead and for teammates who consume Module 2 output.

## 1. Module Boundary

Module 2 does:

- Subscribe to `/face_detection/faces`
- Convert OpenCV face detection output into structured user-state evidence
- Publish `vision_presence_module/UserState` on `/vision_and_presence_detection`

Module 2 does not:

- Decide fatigue level
- Manage focus sessions
- Parse voice commands
- Use `SoundClient`
- Run MediaPipe head-posture analysis

## 2. Output Contract

Topic name:

```text
/vision_and_presence_detection
```

Message type:

```text
vision_presence_module/UserState
```

Fields:

```text
bool user_present
int32 consecutive_eyes_missing
int32 consecutive_face_absent
time stamp
```

## 3. Input Contract

This module expects the existing OpenCV face detection topic:

```text
/face_detection/faces
opencv_apps/FaceArrayStamped
```

That topic is published by `opencv_apps face_detection.launch`. Module 2 only subscribes to it.

## 4. Build Requirements

The package must live under:

```text
group13_ws/src/vision_presence_module
```

Build from the workspace root:

```bash
cd ~/Emote-Bot/group13_ws
catkin_make
source devel/setup.bash
```

`catkin_make` generates the Python message import used by the node:

```python
from vision_presence_module.msg import UserState
```

If this import fails, rebuild the workspace and source `devel/setup.bash`.

## 5. Launch Order

Start camera and OpenCV face detection before Module 2:

```bash
roslaunch usb_cam usb_cam-test.launch
roslaunch opencv_apps face_detection.launch image:=/usb_cam/image_raw
roslaunch vision_presence_module user_state_monitor.launch
```

## 6. Master Launch Integration

Member 1 can include Module 2 like this:

```xml
<include file="$(find vision_presence_module)/launch/user_state_monitor.launch">
  <arg name="face_topic" value="/face_detection/faces"/>
  <arg name="state_topic" value="/vision_and_presence_detection"/>
</include>
```

## 7. Downstream Use

Downstream modules should subscribe to `/vision_and_presence_detection` and use:

```text
user_present
consecutive_eyes_missing
consecutive_face_absent
stamp
```

Do not reimplement face/eye detection in downstream modules. This node is the shared adapter from OpenCV face detection to the team-level user-state signal.

## 8. Test Commands For Screenshots

```bash
rostopic info /face_detection/faces
rostopic info /vision_and_presence_detection
rostopic echo /vision_and_presence_detection
rostopic hz /vision_and_presence_detection
rosmsg show vision_presence_module/UserState
rosnode info /user_state_monitor
```

For the full mock-test and real-robot runtime guide, see `TEST.md`.
