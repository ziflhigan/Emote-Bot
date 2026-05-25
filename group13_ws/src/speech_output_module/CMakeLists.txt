cmake_minimum_required(VERSION 3.0.2)
project(speech_output_module)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  sound_play
)

catkin_package(
  CATKIN_DEPENDS
    rospy
    std_msgs
    sound_play
)

catkin_install_python(PROGRAMS
  scripts/speech_output.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
