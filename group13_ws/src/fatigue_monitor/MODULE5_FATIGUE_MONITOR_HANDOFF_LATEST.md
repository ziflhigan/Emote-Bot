# Module 5 Handoff — Fatigue Monitor Data Publisher

## 1. Module Overview

Package:

```text
fatigue_monitor
```

Main script:

```text
group13_ws/src/fatigue_monitor/scripts/fatigue_node.py
```

ROS node name:

```text
/fatigue_monitor
```

Main purpose:

```text
Publish fatigue-related sensor signals continuously for the LLM module to consume.
```

This module is an **always-on fatigue signal publisher**. It computes visual fatigue indicators from the camera, enriches them with Member 2 user presence and Member 6 head posture data, and publishes one JSON summary topic for the LLM brain.

The LLM module owns session state and intervention decisions. This fatigue node does **not** manage sessions.

---

## 2. Latest Architecture

```text
usb_cam
  ↓
/usb_cam/image_raw
  ↓
fatigue_monitor
  ↓
/focus_robot/fatigue_summary
  ↓
LLM module
  ↓
/tts_request
  ↓
speech_output_module
```

Additional inputs:

```text
Member 2 user state      → /vision_and_presence_detection
Member 6 head posture    → /head_posture_state
Voice command dismiss    → /voice_command
```

The fatigue monitor publishes continuously, regardless of whether a focus session is active. The LLM is expected to know the current session state internally and decide whether to use or ignore the fatigue data.

---

## 3. Module Boundary

### This module does

- Subscribe to `/usb_cam/image_raw`
- Run MediaPipe FaceMesh on camera frames
- Compute:
  - Eye Aspect Ratio, also known as EAR
  - PERCLOS
  - face absence duration
  - face-mesh head pitch
  - fatigue score
  - fatigue level
- Subscribe to Member 2 user presence output
- Subscribe to Member 6 head posture output
- Subscribe to `/voice_command` only for `dismiss`
- Publish individual fatigue metrics
- Publish `/focus_robot/fatigue_summary` JSON for the LLM
- Publish to `/tts_request` only for:
  - `dismiss` acknowledgement
  - local fallback TTS mode

### This module does not

- Start a focus session
- End a focus session
- Subscribe to `/focus_robot/session_active`
- Publish `/focus_robot/session_active`
- Own session elapsed time
- Decide final LLM interventions
- Use `SoundClient` directly
- Start `soundplay_node`
- Replace Member 2 or Member 6 logic

---

## 4. Important Session-State Update

Session state has been removed from this module.

Removed from the latest implementation:

```text
SessionState dataclass
/focus_robot/session_active subscriber
_session_callback()
session_active JSON field
elapsed_secs JSON field
elapsed_mins JSON field
warmup_secs parameter
session_warmup_done flag
time multiplier based on elapsed session time
```

Current behavior:

```text
Fatigue monitor is always monitoring.
LLM module owns session state.
LLM decides when fatigue data matters.
```

The overlay now shows:

```text
STATUS
Always monitoring
LLM manages session
```

---

## 5. Subscribed Topics

### 5.1 Camera input

```text
/usb_cam/image_raw
sensor_msgs/Image
```

Used by the module’s own MediaPipe FaceMesh pipeline.

Required for:

```text
EAR
PERCLOS
head pitch
face absence
OpenCV overlay
```

---

### 5.2 Member 2 input

```text
/vision_and_presence_detection
vision_presence_module/UserState
```

Expected fields:

```text
bool user_present
int32 consecutive_eyes_missing
int32 consecutive_face_absent
time stamp
```

Used for:

```text
M2 overlay status
m2_available JSON field
m2_user_present JSON field
m2_consecutive_eyes_missing JSON field
m2_consecutive_face_absent JSON field
face absence confirmation boost
```

If `vision_presence_module` is not available, the node still runs. M2 status remains unavailable.

---

### 5.3 Member 6 input

```text
/head_posture_state
head_posture_module/HeadPosture
```

Expected fields used:

```text
bool pose_visible
bool calibrated
bool head_down
float32 posture_score
```

Used for:

```text
M6 overlay status
m6_available JSON field
m6_calibrated JSON field
m6_pose_visible JSON field
m6_head_down JSON field
m6_posture_score JSON field
fatigue head/posture score fusion
```

Configurable parameter:

```text
~head_posture_topic
Default: /head_posture_state
```

M6 is trusted only when:

```text
m6.received = True
m6.calibrated = True
m6.pose_visible = True
```

Otherwise, fatigue scoring falls back to this module’s own face-mesh pitch signal.

---

### 5.4 Voice command input

```text
/voice_command
std_msgs/String
```

This module only handles:

```text
dismiss
```

Example test:

```bash
rostopic pub /voice_command std_msgs/String "data: 'dismiss'" --once
```

Expected behavior:

```text
overlay message cleared
event written to log
"Noted." published to /tts_request
```

All other commands are ignored by this module and should be handled by the LLM module.

---

## 6. Published Topics

### 6.1 Fatigue level

```text
/focus_robot/fatigue_level
std_msgs/Int32
```

Values:

```text
0 = ALERT
1 = MILD
2 = MODERATE
3 = SEVERE
```

---

### 6.2 Fatigue score

```text
/focus_robot/fatigue_score
std_msgs/Float32
```

Range:

```text
0.0 to 1.0
```

---

### 6.3 Eye Aspect Ratio

```text
/focus_robot/ear
std_msgs/Float32
```

Lower values indicate more closed eyes.

---

### 6.4 PERCLOS

```text
/focus_robot/perclos
std_msgs/Float32
```

Range:

```text
0.0 to 1.0
```

Represents the proportion of recent frames where eyes are considered closed.

---

### 6.5 Head pitch

```text
/focus_robot/head_pitch_deg
std_msgs/Float32
```

Unit:

```text
degrees
```

Computed using MediaPipe FaceMesh landmarks and OpenCV solvePnP.

---

### 6.6 Face absence duration

```text
/focus_robot/face_absent_secs
std_msgs/Float32
```

Unit:

```text
seconds
```

---

### 6.7 LLM summary topic

```text
/focus_robot/fatigue_summary
std_msgs/String
```

This is the primary topic for the LLM module.

The message is a JSON string containing all fatigue, M2, M6, and TTS-mode information.

Example subscriber:

```python
import json
import rospy
from std_msgs.msg import String

rospy.Subscriber('/focus_robot/fatigue_summary', String, self._fatigue_cb)

def _fatigue_cb(self, msg):
    data = json.loads(msg.data)

    fatigue_level = data["fatigue_level"]
    fatigue_score = data["fatigue_score"]
    perclos = data["perclos"]
    m6_head_down = data["m6_head_down"]
```

---

### 6.8 TTS request

```text
/tts_request
std_msgs/String
```

This module publishes speech request text only. Actual audio is handled by the TTS module.

Used for:

```text
dismiss acknowledgement
local fallback intervention messages
```

---

## 7. JSON Summary Contract

Published on:

```text
/focus_robot/fatigue_summary
```

Type:

```text
std_msgs/String
```

Payload:

```text
JSON string
```

Fields:

```text
fatigue_level
fatigue_label
fatigue_score
time_multiplier

ear
perclos
head_pitch_deg
head_down_frames
face_absent_secs
face_present

m2_available
m2_user_present
m2_consecutive_eyes_missing
m2_consecutive_face_absent

m6_available
m6_calibrated
m6_pose_visible
m6_head_down
m6_posture_score

local_tts_enabled
tts_topic
```

Session fields are intentionally omitted:

```text
session_active
elapsed_secs
elapsed_mins
```

Reason:

```text
LLM owns session state and already knows these values.
```

---

## 8. TTS Integration

This module does not directly use:

```text
SoundClient
sound_play
soundplay_node
```

Speech flow:

```text
fatigue_monitor or LLM
  ↓
/tts_request
  ↓
speech_output_module
  ↓
robot speaker / system audio
```

Default mode:

```bash
rosrun fatigue_monitor fatigue_node.py
```

In default mode:

```text
local_tts_enabled = False
fatigue_monitor publishes data only
LLM decides if/when to speak
LLM publishes to /tts_request
```

Fallback mode:

```bash
rosrun fatigue_monitor fatigue_node.py _local_tts_enabled:=true
```

In fallback mode:

```text
fatigue_monitor publishes simple intervention text directly to /tts_request
LLM is not required for basic testing
fallback is always-on because session state belongs to LLM
```

Adjust fallback message gap:

```bash
rosrun fatigue_monitor fatigue_node.py   _local_tts_enabled:=true   _min_intv_gap_secs:=10
```

---

## 9. Local Fallback TTS Logic

Fallback TTS only checks:

```text
fatigue_level > 0
minimum intervention gap has passed
```

It does not check session state or warmup.

Reason:

```text
LLM owns session state and warmup logic.
```

Messages:

```text
Level 1:
Working hard. Remember to rest your eyes.

Level 2:
Losing focus. A short break might help.

Level 3:
You look quite tired. Consider taking a break.
```

Parameter:

```text
~local_tts_enabled
Default: false
```

Parameter:

```text
~min_intv_gap_secs
Default: 30.0
```

---

## 10. Fatigue Score Logic

Score range:

```text
0.0 to 1.0
```

Level thresholds:

```text
0.30 = MILD
0.55 = MODERATE
0.80 = SEVERE
```

Weighted components:

```text
PERCLOS      50%
Head signal  30%
Face absence 20%
```

Time multiplier:

```text
Always 1.0
```

Reason:

```text
Session duration is owned by LLM. No local time scaling is applied.
```

---

### 10.1 PERCLOS

PERCLOS is based on EAR:

```text
EAR < 0.20 means eyes are treated as closed.
```

PERCLOS is computed over a rolling 60-second window.

---

### 10.2 Head signal with M6 fusion

This module computes face-mesh pitch:

```text
face_pitch_n = head_down_frames / HEAD_PITCH_CONFIRM_N
```

M6 provides body posture:

```text
m6_posture_score = body droop severity from 0.0 to 1.0
m6_head_down = sustained droop confirmation
```

M6 is valid only when:

```text
m6_received = True
m6_calibrated = True
m6_pose_visible = True
```

When M6 is valid:

```text
if m6_head_down:
    m6_head_n = m6_posture_score
else:
    m6_head_n = m6_posture_score * 0.35
```

Final head signal:

```text
head_n = max(m6_head_n, face_pitch_n)
```

Reason:

```text
M6 measures body droop.
This module measures face/head rotation.
Either cue can indicate fatigue posture.
```

When M6 is not valid:

```text
head_n = face_pitch_n
```

---

### 10.3 Face absence

Base face absence:

```text
face_absent_secs / FACE_ABSENT_MODERATE_S
```

If M2 also confirms face absence for more than 10 consecutive frames:

```text
absence signal is boosted by 1.2x, capped at 1.0
```

---

## 11. Build Requirements

From workspace root:

```bash
cd ~/Emote-Bot/group13_ws
catkin_make
source devel/setup.bash
```

Recommended dependencies in `fatigue_monitor/package.xml`:

```xml
<depend>rospy</depend>
<depend>std_msgs</depend>
<depend>sensor_msgs</depend>
<depend>cv_bridge</depend>
<depend>vision_presence_module</depend>
<depend>head_posture_module</depend>
```

Recommended `CMakeLists.txt` components:

```cmake
find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  sensor_msgs
  cv_bridge
  vision_presence_module
  head_posture_module
)
```

The script has import fallback for M2 and M6 packages. It can run without them, but full integration requires those packages to be present and built.

---

## 12. Runtime Launch Order

### 12.1 Minimal fatigue monitor test

Terminal 1:

```bash
roscore
```

Terminal 2, camera:

```bash
roslaunch usb_cam usb_cam-test.launch
```

VM alternative:

```bash
rosrun usb_cam usb_cam_node   _video_device:=/dev/video0   _image_width:=640   _image_height:=480   _framerate:=15   _pixel_format:=mjpeg
```

Terminal 3, fatigue node:

```bash
source ~/Emote-Bot/group13_ws/devel/setup.bash
rosrun fatigue_monitor fatigue_node.py
```

Terminal 4, check summary:

```bash
rostopic echo /focus_robot/fatigue_summary
```

Expected:

```text
JSON messages publishing continuously
```

---

### 12.2 Local fallback TTS test

Terminal 1:

```bash
roscore
```

Terminal 2:

```bash
rostopic echo /tts_request
```

Terminal 3, fatigue node fallback mode:

```bash
source ~/Emote-Bot/group13_ws/devel/setup.bash
rosrun fatigue_monitor fatigue_node.py   _local_tts_enabled:=true   _min_intv_gap_secs:=10
```

Trigger a fatigue condition:

```text
close eyes
look down
move out of frame
cover camera
```

Expected:

```text
/tts_request receives one of the local fallback messages
```

---

### 12.3 With TTS module

If `speech_output_module` is available:

```bash
roslaunch speech_output_module speech_output.launch
```

Test direct TTS:

```bash
rostopic pub /tts_request std_msgs/String "data: 'Testing speech output'" --once
```

Expected:

```text
robot or VM speaks the message
```

Do not manually start `soundplay_node` if the TTS launch already starts it.

---

### 12.4 With Member 2

Start camera first.

Then:

```bash
roslaunch opencv_apps face_detection.launch image:=/usb_cam/image_raw
```

Then:

```bash
roslaunch vision_presence_module user_state_monitor.launch
```

Check:

```bash
rostopic echo /vision_and_presence_detection
```

Expected overlay:

```text
M2 USER STATE green dot
Present YES/NO
Eyes miss and Face abs counters update
```

Expected summary:

```text
m2_available = true
```

---

### 12.5 With Member 6

Start camera first.

Then:

```bash
roslaunch head_posture_module head_posture_monitor.launch
```

Check:

```bash
rostopic echo /head_posture_state
```

Expected fields:

```text
pose_visible
calibrated
head_down
posture_score
```

Expected overlay:

```text
M6 HEAD POSTURE green dot
Calibrating...
then Calibrated
Down YES/NO
Score changes
```

Expected summary:

```text
m6_available = true
m6_calibrated = true after calibration
m6_pose_visible = true when body pose is visible
m6_posture_score changes with posture
```

---

## 13. Debug Commands

Check all topics:

```bash
rostopic list
```

Check camera rate:

```bash
rostopic hz /usb_cam/image_raw
```

Check fatigue summary:

```bash
rostopic echo /focus_robot/fatigue_summary
```

Check TTS request:

```bash
rostopic echo /tts_request
```

Check M2:

```bash
rostopic echo /vision_and_presence_detection
```

Check M6:

```bash
rostopic echo /head_posture_state
```

Check package discovery:

```bash
rospack find fatigue_monitor
rospack find vision_presence_module
rospack find head_posture_module
```

Test dismiss:

```bash
rostopic pub /voice_command std_msgs/String "data: 'dismiss'" --once
```

Expected:

```text
/tts_request publishes: Noted.
```

---

## 14. Success Criteria

The module is working if:

```text
1. fatigue_node.py starts without import errors
2. OpenCV Fatigue Monitor window appears
3. Overlay shows STATUS / Always monitoring / LLM manages session
4. /focus_robot/fatigue_summary publishes JSON continuously
5. /focus_robot/fatigue_level publishes 0-3
6. /focus_robot/fatigue_score publishes 0.0-1.0
7. /voice_command dismiss causes /tts_request to publish Noted.
8. local fallback mode publishes /tts_request messages when fatigue_level > 0
9. M2 panel becomes connected when Member 2 runs
10. M6 panel becomes connected when Member 6 runs
11. fatigue_score increases when eyes close, face disappears, head pitch drops, or M6 posture_score/head_down increases
```

---

## 15. Common Failure Meanings

### No `/focus_robot/fatigue_summary`

Likely causes:

```text
fatigue_node.py is not running
camera frames are not arriving
workspace is not sourced
cv_bridge error
```

Check:

```bash
rostopic hz /usb_cam/image_raw
rosrun fatigue_monitor fatigue_node.py
```

---

### M2 says Not connected

Likely causes:

```text
vision_presence_module not built
user_state_monitor not running
/vision_and_presence_detection not publishing
```

Check:

```bash
rospack find vision_presence_module
rostopic echo /vision_and_presence_detection
```

---

### M6 says Not connected

Likely causes:

```text
head_posture_module not built
head_posture_monitor not running
/head_posture_state not publishing
```

Check:

```bash
rospack find head_posture_module
rostopic echo /head_posture_state
```

---

### M6 stays Calibrating

Likely causes:

```text
30-second baseline not finished
body pose not visible
camera cannot see shoulders
```

Check:

```bash
rostopic echo /head_posture_state
```

Look at:

```text
pose_visible
calibrated
posture_score
```

---

### `/tts_request` has messages but no sound

Fatigue node is working. Issue is in:

```text
speech_output_module
sound_play
audio device
speaker setup
```

Check:

```bash
rostopic echo /tts_request
roslaunch speech_output_module speech_output.launch
```

---

### Local fallback speaks too often

Increase:

```text
~min_intv_gap_secs
```

Example:

```bash
rosrun fatigue_monitor fatigue_node.py   _local_tts_enabled:=true   _min_intv_gap_secs:=60
```

---

## 16. Notes for Other Members

### For LLM Module

Subscribe to:

```text
/focus_robot/fatigue_summary
```

Type:

```text
std_msgs/String
```

Parse JSON.

Session state is not included because the LLM owns session state.

The LLM should publish speech/intervention text to:

```text
/tts_request
```

---

### For TTS Module

Subscribe to:

```text
/tts_request
```

Type:

```text
std_msgs/String
```

This module does not use `SoundClient` directly.

---

### For Member 2

Make sure this topic is available:

```text
/vision_and_presence_detection
```

Type:

```text
vision_presence_module/UserState
```

---

### For Member 6

Make sure this topic is available:

```text
/head_posture_state
```

Type:

```text
head_posture_module/HeadPosture
```

The fatigue node uses M6 only when:

```text
pose_visible = True
calibrated = True
```
