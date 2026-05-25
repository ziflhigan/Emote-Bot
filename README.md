# Emote-Bot — WID3010 AR Group Project

## Branch Overview

| Branch | Contents |
|--------|----------|
| `main` | Module 2 — Vision / Presence detection |
| `feat/mediapipe-head-detection` | Module 6 — Head posture |
| `fatigue-detection` | Module 5 — Fatigue detection |
| **`dev`** | **Unified workspace — all modules merged here** |

> **All integration work happens on `dev`.  
> Each member develops their module here and opens a PR back into `dev`.**

---

## Workspace Layout (`dev` branch)

```
group13_ws/
└── src/
    └── focus_robot/               ← single catkin package
        ├── CMakeLists.txt
        ├── package.xml
        ├── msg/
        │   ├── UserState.msg      ← Module 2 output
        │   ├── HeadPosture.msg    ← Module 6 output
        │   ├── SessionCommand.msg ← Module 3 output  (stub)
        │   └── SessionState.msg   ← Module 4 output  (stub)
        ├── launch/
        │   └── focus_session.launch
        ├── scripts/
        │   ├── constants.py           ← shared topic-name constants
        │   ├── user_state_monitor.py  ← Module 2  ✅ implemented
        │   ├── fatigue_monitor.py     ← Module 5  ✅ implemented
        │   ├── head_posture.py        ← Module 6  ✅ implemented
        │   ├── head_posture_monitor.py← Module 6 helper (pure logic)
        │   ├── voice_command.py       ← Module 3  🚧 stub — TODO
        │   ├── session_manager.py     ← Module 4  🚧 stub — TODO
        │   └── test_integration.py   ← smoke test
        └── config/
            └── params.yaml           ← tunable thresholds
```

---

## Prerequisites

Install on the robot / VM before building:

```bash
# ROS Noetic (or Melodic) + catkin
sudo apt install ros-noetic-opencv-apps ros-noetic-cv-bridge \
                 ros-noetic-usb-cam ros-noetic-sound-play

# Python libraries used by fatigue_monitor.py
pip install mediapipe opencv-python
```

---

## Build

```bash
cd ~/group13_ws
catkin_make
source devel/setup.bash
```

---

## Run

Launch prerequisites in separate terminals first, then start the focus session:

```bash
# Terminal 1 — ROS core
roscore

# Terminal 2 — USB camera
roslaunch usb_cam usb_cam-test.launch

# Terminal 3 — Face detection (feeds Module 2)
roslaunch opencv_apps face_detection.launch image:=/usb_cam/image_raw

# Terminal 4 — Voice recognition (feeds Module 5)
roslaunch jupiterobot2_voice_ps voice_recognition.launch

# Terminal 5 — All focus_robot nodes
roslaunch focus_robot focus_session.launch
```

> **Head posture (Module 6)** also needs a MediaPipe pose node running.  
> Before launching, run `rostopic info /mediapipe/pose_landmarks` to find the  
> message type, then set `pose_msg_module` and `pose_msg_type` in  
> `launch/focus_session.launch`.

---

## ROS Topic Interface

```
[usb_cam]                /usb_cam/image_raw  ──────────────────────► fatigue_monitor.py
[opencv_apps]  /face_detection/faces  ────────────────────────────► user_state_monitor.py
[mediapipe]    /mediapipe/pose_landmarks  ────────────────────────► head_posture.py
[pocketsphinx] /recognizer/output  ──────────────────────────────► fatigue_monitor.py
                                                                  ► voice_command.py (M3)

user_state_monitor.py  ──►  /vision_and_presence_detection  (UserState)
head_posture.py        ──►  /head_posture_state             (HeadPosture)
fatigue_monitor.py     ──►  /focus_robot/session_active     (std_msgs/Bool)
                       ──►  /focus_robot/fatigue_level      (std_msgs/Int32)
voice_command.py (M3)  ──►  /focus_robot/session_command    (SessionCommand)
session_manager.py(M4) ──►  /focus_robot/session_state      (SessionState)
```

**Integration note:** `fatigue_monitor.py` publishes `/focus_robot/session_active`.
`head_posture.py` subscribes to it (via `session_active_topic` param) and resets
its calibration baseline every time a new session starts.

---

## Message Definitions

### `UserState.msg` — published by Module 2
```
bool  user_present             # face visible in camera
int32 consecutive_eyes_missing # frames with face but no eyes detected
int32 consecutive_face_absent  # frames with no face at all
time  stamp
```

### `HeadPosture.msg` — published by Module 6
```
bool    pose_visible             # MediaPipe landmarks visible
bool    calibrated               # baseline established
bool    head_down                # sustained droop detected
float32 posture_score            # severity 0–1
float32 head_drop_ratio          # current nose-to-shoulder distance (px)
float32 baseline_ratio           # calibrated upright baseline (px)
int32   consecutive_droop_frames # frame counter
time    stamp
```

### `SessionCommand.msg` — to be published by Module 3
```
string command   # e.g. "START", "STOP"
time   stamp
```

### `SessionState.msg` — to be published by Module 4
```
bool    session_active
float32 elapsed_secs
int32   fatigue_level
time    stamp
```

---

## Guide for Each Member

### Module 2 — Vision / Presence (✅ done)
**File:** `scripts/user_state_monitor.py`  
No action needed. Publishes `UserState` on `/vision_and_presence_detection`.

---

### Module 3 — Voice Command 🚧
**File to edit:** `scripts/voice_command.py`

What to implement:
1. Subscribe to `/recognizer/output` (`std_msgs/String`) — already wired up in the stub.
2. Parse the recognised text into a command string (`"START"`, `"STOP"`, etc.).
3. Publish a `SessionCommand` message on `/focus_robot/session_command`.

```python
from focus_robot.msg import SessionCommand
from constants import SESSION_COMMAND_TOPIC

msg = SessionCommand()
msg.command = "START"        # or "STOP", etc.
msg.stamp   = rospy.Time.now()
self.pub.publish(msg)
```

If you need to add new message fields, edit `msg/SessionCommand.msg`, then run `catkin_make`.

---

### Module 4 — Session Manager 🚧
**File to edit:** `scripts/session_manager.py`

What to implement:
1. Subscribe to `/focus_robot/session_command` (`SessionCommand`) — already wired.
2. On `"START"` command: start timing, publish session state.
3. Subscribe to `/focus_robot/fatigue_level`, `/vision_and_presence_detection`,
   `/head_posture_state` to build a unified picture.
4. Publish `SessionState` on `/focus_robot/session_state`.
5. Drive robot behaviour (LED, TTS, motion) from here.

```python
from focus_robot.msg import SessionState
from constants import SESSION_STATE_TOPIC

msg = SessionState()
msg.session_active = True
msg.elapsed_secs   = self.elapsed
msg.fatigue_level  = self.fatigue_level
msg.stamp          = rospy.Time.now()
self.pub.publish(msg)
```

Also uncomment the `session_manager` node block in `launch/focus_session.launch`.

---

### Module 5 — Fatigue Monitor (✅ done)
**File:** `scripts/fatigue_monitor.py`  
Publishes `/focus_robot/session_active` (Bool) and `/focus_robot/fatigue_level` (Int32).  
Tunable thresholds are in the `CFG` dict at the top of the file and mirrored in `config/params.yaml`.

---

### Module 6 — Head Posture (✅ done)
**File:** `scripts/head_posture.py` + `scripts/head_posture_monitor.py`  
Publishes `HeadPosture` on `/head_posture_state`.

**One manual step required on the robot:**
```bash
rostopic info /mediapipe/pose_landmarks
# note the Type field, e.g.  mediapipe_ros/Poses
```
Then set in `launch/focus_session.launch`:
```xml
<param name="pose_msg_module" value="mediapipe_ros"/>
<param name="pose_msg_type"   value="Poses"/>
```

Droop thresholds can be tuned via ROS params (see `config/params.yaml`) without touching the code.

---

## Smoke Test

After launching all nodes:
```bash
rosrun focus_robot test_integration.py
```
Prints `PASS` / `FAIL` for each expected topic and exits 0 if all pass.

---

## Development Workflow

```bash
# 1. Pull latest dev
git checkout dev && git pull origin dev

# 2. Work on your script, then commit
git add group13_ws/src/focus_robot/scripts/your_script.py
git commit -m "feat(M3): implement voice command parsing"

# 3. Push and open a PR into dev
git push origin dev
```
