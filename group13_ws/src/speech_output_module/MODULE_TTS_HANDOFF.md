# Speech Output Module Handoff

This document is for Member 1 (master launch / integration) and for the
members who will publish to this module's input topic (e.g. session
manager, fatigue monitor).

## 1. Module Boundary

Speech Output Module does:

- Subscribe to `/tts_request` (`std_msgs/String`)
- Forward the text into `sound_play.SoundClient.say(...)`
- Run alongside `soundplay_node`, started by the same launch file
- Suppress duplicate consecutive utterances within a 5 s window
  (configurable via `~dedupe_seconds`)

Speech Output Module does not:

- Decide what to say
- Manage sessions
- Detect fatigue
- Parse voice commands
- Listen to the microphone
- Translate or paraphrase the text

Whoever publishes the message owns the wording. This module just
speaks.

## 2. Input Contract

Topic name:

```text
/tts_request
```

Message type:

```text
std_msgs/String
```

Field:

```text
string data
```

Semantics of `data`:

- A complete sentence the robot should speak as-is
- UTF-8 string; English works best with the default sound_play voice
- Empty / whitespace-only payloads are silently dropped (logged via
  `rospy.logwarn`)
- Identical consecutive payloads received within `~dedupe_seconds`
  (default 5.0 s) are suppressed to prevent annoying repetition

Example:

```text
data : "Take a break, you have been working for an hour."
data : "Session started. Focus mode is on."
data : "You look tired. Please look at the screen."
```

## 3. Suggested Vocabulary

The module is content-agnostic, but to keep the team consistent, the
following utterances are suggested for the agreed scenarios:

| Trigger                            | Recommended `data`                      | Owner             |
|------------------------------------|-----------------------------------------|-------------------|
| Voice command "start session"      | `"Session started. Focus mode is on."`  | session_manager   |
| Voice command "pause"              | `"Session paused."`                     | session_manager   |
| Voice command "resume"             | `"Session resumed."`                    | session_manager   |
| Voice command "end session"        | `"Session ended. Good job."`            | session_manager   |
| Voice command "status"             | (current state, free-form)              | session_manager   |
| Unknown voice command              | `"Sorry, I did not understand."`        | session_manager   |
| Eyes missing >= N callbacks        | `"You look tired. Take a short break."` | fatigue_monitor   |
| User absent >= N callbacks         | `"User not detected."` *(optional)*     | fatigue_monitor   |
| Bad head posture detected          | `"Please sit upright."`                 | fatigue_monitor   |

Add new phrases by simply publishing them - no change to this module
is required.

## 4. ROS Params Exposed

| Param              | Type   | Default            | Purpose                                                    |
|--------------------|--------|--------------------|------------------------------------------------------------|
| `~tts_topic`       | string | `/tts_request`     | Input topic name                                           |
| `~dedupe_seconds`  | float  | `5.0`              | Suppress identical consecutive payloads within this window |
| `~connect_delay`   | float  | `1.0`              | Sleep after creating SoundClient before first call         |
| `~voice`           | string | `""` (sound_play default) | Voice name passed to SoundClient.say()             |
| `~volume`          | float  | `1.0`              | Volume passed to SoundClient.say() (0.0 - 1.0)             |

## 5. Required ROS Package Config

Already present in this package (`speech_output_module/`):

`package.xml` dependencies:

```xml
<buildtool_depend>catkin</buildtool_depend>

<build_depend>rospy</build_depend>
<build_depend>std_msgs</build_depend>
<build_depend>sound_play</build_depend>

<exec_depend>rospy</exec_depend>
<exec_depend>std_msgs</exec_depend>
<exec_depend>sound_play</exec_depend>
```

`CMakeLists.txt` install block:

```cmake
catkin_install_python(PROGRAMS
  scripts/speech_output.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
```

## 6. System-Level Requirements

- `sound_play` ROS package installed on the robot (apt). Already in use
  by the kids module's `say_hello_ans.py`, so this is satisfied.
- A working audio output device. Verify once with:

  ```bash
  rosrun sound_play say.py "Hello, this is the focus robot."
  ```

  If you hear the phrase, your TTS stack is fine.
- No internet required. `sound_play` uses the local Festival TTS
  engine on Ubuntu 20.04, fully offline.

## 7. Why IDE Import Warnings Are Expected

The script imports:

```python
from sound_play.libsoundplay import SoundClient
from std_msgs.msg import String
```

These are resolved only after:

```bash
catkin_make
source devel/setup.bash
```

So a local IDE warning such as `Cannot find module sound_play` is
expected before deployment and build.

## 8. Master Launch Integration

Member 1 should include this module from the master focus-session
launch file:

```xml
<include file="$(find speech_output_module)/launch/speech_output.launch">
  <arg name="tts_topic" value="/tts_request"/>
</include>
```

Important:

- Do NOT also start a separate `soundplay_node` in the master launch.
  This module's launch already starts one. Two `soundplay_node`s would
  collide on the audio device.
- If the kids module's `say_hello_ans.launch` is also being included,
  drop the `soundplay_node` line from one of them.

Standalone launch order for development:

```text
roscore
roslaunch speech_output_module speech_output.launch
rostopic pub -1 /tts_request std_msgs/String "data: 'hello'"
```

## 9. How Upstream Modules Should Use It

### Session Manager (primary publisher)

```python
import rospy
from std_msgs.msg import String

class SessionManager:
    def __init__(self):
        rospy.init_node("session_manager")
        self.tts_pub = rospy.Publisher("/tts_request", String, queue_size=10)

    def announce(self, text):
        rospy.loginfo("Asking TTS to say: %r", text)
        self.tts_pub.publish(text)

    def start_session(self):
        # ... internal state changes ...
        self.announce("Session started. Focus mode is on.")
```

### Fatigue Monitor (secondary publisher)

```python
def on_user_state(self, msg):
    if msg.consecutive_eyes_missing >= self.threshold and not self.alerted:
        self.tts_pub.publish("You look tired. Take a short break.")
        self.alerted = True
```

### Voice Command Module (acknowledgement only, optional)

```python
# In your existing voice_command.py, you could OPTIONALLY publish an
# acknowledgement when an unknown command is heard:
self.tts_pub.publish("Sorry, I did not understand.")
```

This stays optional - voice_command works fine without ever speaking.

## 10. Faking the Topic for Development

Anyone can make the robot speak without writing a publisher:

```bash
roscore                                                   # T1
roslaunch speech_output_module speech_output.launch       # T2

# T3 - any of these will trigger speech:
rostopic pub -1 /tts_request std_msgs/String "data: 'Take a break.'"
rostopic pub -1 /tts_request std_msgs/String "data: 'Session started.'"
rostopic pub -1 /tts_request std_msgs/String "data: 'Hello world.'"
```

This is how integration testing is done. Teammates building publishers
do not need to coordinate with this module beyond the topic name.

## 11. Relationship to voice_command (sister module)

| Property           | voice_command                    | speech_output                    |
|--------------------|----------------------------------|----------------------------------|
| Direction          | mic -> ROS                       | ROS -> speakers                  |
| Topic              | `/voice_command` (publishes)     | `/tts_request` (subscribes)      |
| Message type       | `std_msgs/String`                | `std_msgs/String`                |
| External backend   | `recognize_google()`             | `sound_play.SoundClient`         |
| Server process     | none                             | `soundplay_node` (in launch)     |
| Wake-word required | yes                              | no                               |
| Internet required  | yes                              | no                               |

The two modules are independent. They do not depend on each other and
can be launched separately.
