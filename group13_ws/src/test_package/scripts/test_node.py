#!/usr/bin/env python

import rospy

if __name__ == '__main__':
	rospy.init_node("myfirstnode")
	rospy.loginfo("the node has been started")
	rospy.sleep(1)
	rospy.loginfo("Exit noW")
