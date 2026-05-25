cmake_minimum_required(VERSION 3.0.2)
project(emote_bot)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  opencv_apps
  message_generation
)

add_message_files(
  FILES
  UserState.msg
  HeadPosture.msg
)

generate_messages(
  DEPENDENCIES
  std_msgs
)

catkin_package(
  CATKIN_DEPENDS
    rospy
    std_msgs
    opencv_apps
    message_runtime
)

catkin_install_python(PROGRAMS
  scripts/user_state_monitor.py
  scripts/head_posture.py
  scripts/voice_command.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
