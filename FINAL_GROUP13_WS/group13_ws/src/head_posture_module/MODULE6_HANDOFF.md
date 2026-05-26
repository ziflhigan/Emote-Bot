# Module 6 Handoff — Head Posture (Ragavendran)

## For Member 1 (Integration)

- Package: `head_posture_module` in `group13_ws/src/`
- Launch: `roslaunch head_posture_module head_posture_monitor.launch`
- Start **after** USB camera (`usb_cam`), same as fatigue_monitor
- Default: subscribes to `/usb_cam/image_raw` and runs MediaPipe Pose on-board
- Optional external pose topic: set `use_external_pose:=true` plus `pose_msg_module` / `pose_msg_type` from `rostopic info`

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
cd ~/group13_ws && catkin_make && source devel/setup.bash
roslaunch usb_cam usb_cam-test.launch
roslaunch head_posture_module head_posture_monitor.launch
```

Debug output without parsing pose (another terminal):

```bash
rosrun head_posture_module head_posture_monitor.py --print
```
