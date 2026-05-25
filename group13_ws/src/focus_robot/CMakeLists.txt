cmake_minimum_required(VERSION 3.0.2)
project(focus_robot)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  opencv_apps
  sensor_msgs
  cv_bridge
  message_generation
)

add_message_files(
  FILES
  UserState.msg
  HeadPosture.msg
  SessionCommand.msg
  SessionState.msg
)

generate_messages(
  DEPENDENCIES
  std_msgs
)

catkin_package(
  CATKIN_DEPENDS rospy std_msgs opencv_apps sensor_msgs cv_bridge message_runtime
)

catkin_install_python(PROGRAMS
  scripts/user_state_monitor.py
  scripts/head_posture.py
  scripts/head_posture_monitor.py
  scripts/fatigue_monitor.py
  scripts/constants.py
  scripts/voice_command.py
  scripts/session_manager.py
  scripts/test_integration.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
