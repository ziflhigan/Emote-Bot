cmake_minimum_required(VERSION 3.0.2)
project(head_posture_module)

find_package(catkin REQUIRED COMPONENTS
  cv_bridge
  rospy
  sensor_msgs
  std_msgs
  message_generation
)

add_message_files(
  FILES
  HeadPosture.msg
)

generate_messages(
  DEPENDENCIES
  std_msgs
)

catkin_package(
  CATKIN_DEPENDS
    cv_bridge
    rospy
    sensor_msgs
    std_msgs
    message_runtime
)

catkin_install_python(PROGRAMS
  scripts/head_posture_monitor.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
