# Module 6 Handoff — Head Posture (Ragavendran)

## For Member 1 (Integration)

- Package: `head_posture_module` in `group13_ws/src/`
- Launch: `roslaunch head_posture_module head_posture_monitor.launch`
- Start **after** USB camera and MediaPipe pose (user guide §3.6)
- Required launch args on robot (from `rostopic info`):
  - `pose_msg_module` — ROS package name containing the pose message
  - `pose_msg_type` — message class name (e.g. `PoseLandmarks`)

## For Member 5 (Fatigue Monitor)

Subscribe to:

```text
/head_posture_state
head_posture_module/HeadPosture
```

Use in fatigue score:

- `head_down` (bool) — sustained droop detected
- `posture_score` (float32, 0–1) — continuous droop severity
- Ignore updates when `pose_visible` is false or `calibrated` is false

## Robot setup (Monday)

```bash
rostopic list | grep -i pose
rostopic info /mediapipe/pose_landmarks
rostopic echo /mediapipe/pose_landmarks -n1
```

Then:

```bash
cd ~/group13_ws && catkin_make && source devel/setup.bash
roslaunch head_posture_module head_posture_monitor.launch \
  pose_msg_module:=<from_rostopic_info> \
  pose_msg_type:=<from_rostopic_info>
```

Debug output without parsing pose (another terminal):

```bash
rosrun head_posture_module head_posture_monitor.py --print
```
