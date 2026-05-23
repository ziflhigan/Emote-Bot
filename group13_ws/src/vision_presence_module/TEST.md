# Vision Presence Module Test And Runtime Guide

This guide explains how to test Module 2 in isolation and how to run it on the real robot.

## 1. What This Module Needs

Input topic:

```text
/face_detection/faces
opencv_apps/FaceArrayStamped
```

Output topic:

```text
/vision_and_presence_detection
vision_presence_module/UserState
```

This module does not publish `/face_detection/faces`. That topic is published by `opencv_apps face_detection.launch`. Module 2 subscribes to it and publishes `/vision_and_presence_detection`.

## 2. Build The Workspace

Run this from the workspace root:

```bash
cd ~/Emote-Bot/group13_ws
catkin_make
source devel/setup.bash
```

Every new terminal must source the workspace before using this package:

```bash
cd ~/Emote-Bot/group13_ws
source devel/setup.bash
```

Verify that ROS can find the package and generated message:

```bash
rospack find vision_presence_module
rosmsg show vision_presence_module/UserState
```

Expected message:

```text
bool user_present
int32 consecutive_eyes_missing
int32 consecutive_face_absent
time stamp
```

## 3. Test Without Camera

Use this test when the camera or robot is not available. It checks that the node can subscribe, process an empty face-detection message, and publish user state.

Terminal 1:

```bash
roscore
```

Terminal 2:

```bash
cd ~/Emote-Bot/group13_ws
source devel/setup.bash
roslaunch vision_presence_module user_state_monitor.launch
```

Terminal 3:

```bash
cd ~/Emote-Bot/group13_ws
source devel/setup.bash
rostopic echo /vision_and_presence_detection
```

Terminal 4:

```bash
cd ~/Emote-Bot/group13_ws
source devel/setup.bash
rostopic pub -r 2 /face_detection/faces opencv_apps/FaceArrayStamped "{header: {frame_id: 'camera'}, faces: []}"
```

Expected output on `/vision_and_presence_detection`:

```text
user_present: False
consecutive_eyes_missing: 0
consecutive_face_absent: increasing
stamp: current ROS time
```

If `stamp` stays at zero, check simulated time:

```bash
rosparam get /use_sim_time
rostopic echo /clock
```

If `/use_sim_time` is `true` but `/clock` is not publishing, ROS time can remain zero. For normal robot testing without simulation clock, set:

```bash
rosparam set /use_sim_time false
```

Then restart the node.

## 4. Run On The Real Robot

Use separate terminals. Source `devel/setup.bash` in every terminal before running package commands.

Terminal 1: start the robot camera. Use the command that matches the robot setup.

For USB camera:

```bash
roslaunch usb_cam usb_cam-test.launch
```

For the robot Astra camera, use the robot's existing camera launch. The reference `say_hello_ans.py` mentions:

```bash
roslaunch astra_camera astra.launch
```

After starting the camera, find the image topic:

```bash
rostopic list | grep image_raw
```

Terminal 2: start OpenCV face detection using the correct image topic.

For USB camera:

```bash
roslaunch opencv_apps face_detection.launch image:=/usb_cam/image_raw
```

For Astra camera, the reference topic is usually:

```bash
roslaunch opencv_apps face_detection.launch image:=/camera/rgb/image_raw
```

Verify that face detection is publishing:

```bash
rostopic info /face_detection/faces
rostopic hz /face_detection/faces
```

Terminal 3: start Module 2.

```bash
cd ~/Emote-Bot/group13_ws
source devel/setup.bash
roslaunch vision_presence_module user_state_monitor.launch
```

Terminal 4: watch Module 2 output.

```bash
cd ~/Emote-Bot/group13_ws
source devel/setup.bash
rostopic echo /vision_and_presence_detection
```

## 5. Runtime Acceptance Checks

Use these scenarios on the real robot:

| Scenario | Expected output |
|---|---|
| Face and eyes visible | `user_present: True`, both counters reset to `0` |
| Face visible but eyes not detected | `user_present: True`, `consecutive_eyes_missing` increases |
| No face in frame | `user_present: False`, `consecutive_face_absent` increases |
| Face and eyes visible again | `user_present: True`, both counters reset to `0` |

## 6. Screenshot Checklist

Capture these for the report:

```bash
rosmsg show vision_presence_module/UserState
rostopic info /face_detection/faces
rostopic info /vision_and_presence_detection
rostopic echo /vision_and_presence_detection
rostopic hz /vision_and_presence_detection
rosnode info /user_state_monitor
```

## 7. Integration Notes

Member 1 can include this module in a master launch file after camera and face detection:

```xml
<include file="$(find vision_presence_module)/launch/user_state_monitor.launch">
  <arg name="face_topic" value="/face_detection/faces"/>
  <arg name="state_topic" value="/vision_and_presence_detection"/>
</include>
```

Do not start this module before `/face_detection/faces` exists if you need immediate output. The node can start first, but it will publish only after messages arrive on `/face_detection/faces`.

## 8. Troubleshooting

Package not found:

```bash
cd ~/Emote-Bot/group13_ws
source devel/setup.bash
rospack find vision_presence_module
```

Message import error:

```bash
cd ~/Emote-Bot/group13_ws
catkin_make
source devel/setup.bash
```

No output on `/vision_and_presence_detection`:

```bash
rostopic info /face_detection/faces
rostopic hz /face_detection/faces
```

If `/face_detection/faces` has no publisher, start `opencv_apps face_detection.launch` with the correct image topic.
