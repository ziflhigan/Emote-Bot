# Module 6 — Head Posture Monitor

Member 6 deliverable: subscribe to MediaPipe pose landmarks, detect sustained head droop, publish evidence on `/head_posture_state` for the fatigue monitor (Member 5).

## Output contract

| Item | Value |
|------|-------|
| Topic | `/head_posture_state` |
| Message | `head_posture_module/HeadPosture` |
| Fields | `pose_visible`, `calibrated`, `head_down`, `posture_score`, `head_drop_ratio`, `baseline_ratio`, `consecutive_droop_frames`, `stamp` |

Equivalent to `rchomeedu_vision/HeadPostureState` in the Module 2 handoff doc (same fields).

## Build

```bash
cd ~/group13_ws
catkin_make
source devel/setup.bash
rosmsg show head_posture_module/HeadPosture
```

## Run (on Juno, after MediaPipe pose is launched)

1. Discover the pose topic and message type:

```bash
rostopic list | grep -i pose
rostopic info /mediapipe/pose_landmarks
rostopic echo /mediapipe/pose_landmarks -n1
```

2. Launch with the real package and type (example — replace with values from `rostopic info`):

```bash
roslaunch head_posture_module head_posture.launch \
  pose_msg_module:=YOUR_PACKAGE \
  pose_msg_type:=YOUR_MESSAGE_TYPE
```

Or set params on the node:

```bash
rosrun head_posture_module head_posture_node.py \
  _pose_msg_module:=YOUR_PACKAGE \
  _pose_msg_type:=YOUR_MESSAGE_TYPE
```

3. Verify output:

```bash
rostopic echo /head_posture_state
```

## Session-aware calibration (optional)

When Member 4 publishes session active as `std_msgs/Bool`, enable recalibration at session start:

```bash
roslaunch head_posture_module head_posture.launch \
  session_active_topic:=/focus_robot/session_active
```

Until then, calibration runs for the first 30 seconds after the node starts (restart the node at session start if needed).

## Tunable parameters

| Param | Default | Meaning |
|-------|---------|---------|
| `~image_height` | 480 | Scale factor when landmarks are normalized 0–1 |
| `~coords_normalized` | true | Multiply y by image_height |
| `~droop_pixel_threshold` | 30 | Pixels below personal baseline to count as droop |
| `~droop_frame_threshold` | 15 | Consecutive droop frames before `head_down=True` |
| `~calibration_duration` | 30 | Seconds to collect upright baseline |
| `~min_landmark_visibility` | 0.5 | Ignore low-confidence landmarks |

## Manual test checklist (screenshots for report)

| Action | Expected on `/head_posture_state` |
|--------|-----------------------------------|
| Sit upright first 30s | `calibrated` becomes true, low `posture_score` |
| Drooping head 3–5s | `consecutive_droop_frames` increases |
| Sustained droop | `head_down=true`, higher `posture_score` |
| Leave camera frame | `pose_visible=false` |

## Handoff to Member 5 (Fatigue Monitor)

Subscribe to `/head_posture_state` and use `head_down` and `posture_score` in the fatigue score. This node does **not** speak or decide fatigue levels.

## Handoff to Member 1 (Integration)

Add this launch file after USB camera and MediaPipe pose in the master launch. Pass `pose_msg_module` and `pose_msg_type` from robot discovery.
