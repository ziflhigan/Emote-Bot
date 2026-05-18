# Module 2 Handoff

This document is for Member 1 and for the members who will consume the output of Module 2.

## 1. Module Boundary

Module 2 does:

- Subscribe to `/face_detection/faces`
- Convert raw face-detection output into structured user-state evidence
- Publish `rchomeedu_vision/UserState` on `/vision_and_presence_detection`

Module 2 does not:

- Decide fatigue level
- Manage sessions
- Parse voice commands
- Use `SoundClient`
- Run MediaPipe head-posture analysis directly

Phase 8 head posture should be a separate evidence node. It should publish `/head_posture_state` with `rchomeedu_vision/HeadPostureState`. The fatigue monitor consumes both topics.

## 2. Output Contract

Topic name:

```text
/vision_and_presence_detection
```

Message type:

```text
rchomeedu_vision/UserState
```

Fields:

```text
bool user_present
int32 consecutive_eyes_missing
int32 consecutive_face_absent
time stamp
```

Related Phase 8 posture topic:

```text
/head_posture_state
```

Message type:

```text
rchomeedu_vision/HeadPostureState
```

Fields:

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

## 3. Required ROS Package Config

Member 1 must update the existing `rchomeedu_vision/package.xml` and `rchomeedu_vision/CMakeLists.txt`.

Required `package.xml` dependencies:

```xml
<buildtool_depend>catkin</buildtool_depend>

<build_depend>rospy</build_depend>
<build_depend>std_msgs</build_depend>
<build_depend>opencv_apps</build_depend>
<build_depend>message_generation</build_depend>

<exec_depend>rospy</exec_depend>
<exec_depend>std_msgs</exec_depend>
<exec_depend>opencv_apps</exec_depend>
<exec_depend>message_runtime</exec_depend>
```

Required `CMakeLists.txt` key blocks:

```cmake
find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  opencv_apps
  message_generation
)

add_message_files(
  FILES
  UserState.msg
  HeadPostureState.msg
)

generate_messages(
  DEPENDENCIES
  std_msgs
)

catkin_package(
  CATKIN_DEPENDS rospy std_msgs opencv_apps message_runtime
)
```

## 4. Why IDE Import Warnings Are Expected

The ROS scripts import:

```python
from rchomeedu_vision.msg import UserState
from rchomeedu_vision.msg import HeadPostureState
```

Those Python modules are generated only after:

```bash
catkin_make
source devel/setup.bash
```

So a local IDE warning such as `Cannot find module rchomeedu_vision.msg` is expected before deployment and build.

## 5. Master Launch Integration

Member 1 should start this module after camera and OpenCV face detection:

```xml
<include file="$(find rchomeedu_vision)/launch/user_state_monitor.launch">
  <arg name="face_topic" value="/face_detection/faces"/>
  <arg name="state_topic" value="/vision_and_presence_detection"/>
</include>
```

If Phase 8 head posture is included, start the MediaPipe pose launch and the head-posture node after the camera is available:

```text
usb_cam
opencv_apps face_detection
user_state_monitor
MediaPipe pose launch
head_posture_monitor_node
session manager / fatigue monitor
```

## 6. How Downstream Modules Should Use It

Session manager should subscribe to `/vision_and_presence_detection` and use:

```text
user_present
stamp
```

Fatigue monitor should subscribe to `/vision_and_presence_detection` and use:

```text
user_present
consecutive_eyes_missing
consecutive_face_absent
stamp
```

For Phase 8, fatigue monitor should also subscribe to `/head_posture_state` and use:

```text
pose_visible
calibrated
head_down
posture_score
consecutive_droop_frames
stamp
```

Do not reimplement face/eyes detection in downstream modules.

Do not put head posture into `UserStateLogic`. `UserStateLogic` remains valid for Module 2 because it is the pure face/eye state tracker. Head posture should be combined later in the fatigue monitor.
