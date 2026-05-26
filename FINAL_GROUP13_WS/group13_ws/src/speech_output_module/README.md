# Speech Output Module

Text-to-speech output module for the focus robot. Subscribes to a string topic and asks `sound_play` to speak the text. Symmetric counterpart of the voice command module.

## ROS Contract

Input:

```text
/tts_request
std_msgs/String
```

Output: none on the ROS side. The module produces audio on the robot's speakers via the `sound_play` server (`soundplay_node`).

This module only speaks. It does not decide what to say, manage sessions, parse voice commands, detect fatigue, or analyse images.

## Build

From the workspace root:

```bash
cd ~/Emote-Bot/group13_ws
catkin_make
source devel/setup.bash
```

## Run

The launch file brings up both `soundplay_node` and the client:

```bash
roslaunch speech_output_module speech_output.launch
```

## Test And Screenshots

Use these commands for online testing and report screenshots:

```bash
rostopic info /tts_request
rosnode info /speech_output
rosnode info /soundplay_node

# Make the robot say something:
rostopic pub -1 /tts_request std_msgs/String "data: 'Take a break.'"
rostopic pub -1 /tts_request std_msgs/String "data: 'Session started.'"
rostopic pub -1 /tts_request std_msgs/String "data: 'You look tired.'"
```

For teammate handoff, see `MODULE_TTS_HANDOFF.md`.
