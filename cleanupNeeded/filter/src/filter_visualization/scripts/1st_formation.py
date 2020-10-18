import sys
import rospy
from turtlesim.srv import *

def spawn_turtle_client(x, y, theta, name = None):
	rospy.wait_for_service('spawn')
	try:
		spawn_turtle = rospy.ServiceProxy('spawn', Spawn)
		if name == None:
			response = spawn_turtle(x,y,theta,'thing')
		else:
			response = spawn_turtle(x,y,theta,name)
		return response.name
	except rospy.ServiceException as e:
		print("Service call failed: %s"%e)


if __name__ == "__main__":
	response = spawn_turtle_client(1,2,0,"JoJo")
	print(response)
	response = spawn_turtle_client(5,5,0,"Grandpa")
	print(response)
	response = spawn_turtle_client(7,7,0)

