# dwmDistances
# Being written September 2019 by James Keiller
# Intended for use with DWM 1001 module through UART TLV interface
# This script calls the dwm_loc_get API call as specified in the
# DWM1001 Firmware API Guide 5.3.10.
# It parses the information received to send over
# the ROS network.
# In the future, this script will be expanded to allow
# position updates to be written to anchor nodes
# Currently limited to Python 3.6+.  Use command line arguments
# to specify the name of the port (See myParser() function)

import serial # use "pip install pyserial" if you have not already done so
import time
import sys
import argparse

defaultPortName = '/dev/ttyACM0'
# On linux, you should use /dev/ttyACM0
# ON Windows, the port name may be 'COM9' or similar
def myParser():
	# This function handles command lets the user specify the
	# name of the port to use with a command line argument.
	# --port=[name or number]
	parser = argparse.ArgumentParser(description = 'get position info')  # Script descript.
	parser.add_argument(
		'--port',
		default=defaultPortName,
		help='specify the name of the port to use (default: ' + defaultPortName + ' )'
		)
	args = parser.parse_args()
	print("Using port:", args.port)
	return args.port


ser = None	 # This will be the name of the handle to the serial port
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
# API Error codes
ERR_CODE_OK = bytes.fromhex("00")
# 1: unknown command or broken TLV frame
# 2: internal error
# 3: invalid parameter
# 4: busy
# 5: operation not permitted
# API Commands [Type, length]
DWM_POS_SET = bytes.fromhex("01 0d")  # Used to set position.  Follow with position as 13 bytes
DWM_POS_GET = bytes.fromhex("02 00")  # Used to ask for position.
DWM_LOC_GET = bytes.fromhex("0c 00")  # Request for position + distances to anchors/tags
# Response codes
TLV_TYPE_DUMMY = bytes.fromhex("00")  # Reserved for SPI dummy byte
TLV_TYPE_POS_XYZ = bytes.fromhex("41")  # Response position coordinates x,y,z with q
TLV_TYPE_RNG_AN_DIST = bytes.fromhex("48")  # Response: Ranging anchor distances
TLV_TYPE_RNG_AN_POS_DIST = bytes.fromhex("49")  # Response: Ranging anchor distances and positions


def main():
	global ser
	print("dwmPosGet started.")
	myPort = myParser()
	# Establish serial port connection
	try:
		ser = serial.Serial(myPort, baudrate=115200, timeout=None)
		print(ser)
		print("Connection established.")
	except:
		print("Error in trying to connect to serial port {}".format(myPort))
	stopLoop = False
	# Loop plan:
	# 1. Ask Decawave for position
	# 2. Receive response, parsing as I go
	# --First response is confirmation / error code
	# --Second response is position
	# 2.5 Error handling
	# 3. Output message
	# ----------
	while stopLoop is False:
		getLocations()


def sendTLV(request):
	global ser
	txBuffer = request
	try:
		ser.reset_input_buffer() # Get rid of anything in the buffer that could confuse this script.
		ser.write(txBuffer)
	except:
		print(f"Error during transmission of request {txBuffer.hex()}")
		stopLoop = True
		return EXIT_FAILURE
	return EXIT_SUCCESS


def receiveTLV():
	# Listen for TLV response from Decawave DWM1001 module
	# Returns a list of [Type, Length, Value]
	# If it receives TLV_TYPE_DUMMY, it keeps listening for next message
	global ser  # The handle for the serial port connection
	typeTLV = TLV_TYPE_DUMMY
	while (typeTLV == TLV_TYPE_DUMMY):
		typeTLV = ser.read(1)  # Read the "type" byte of the response
	lengthTLV = ser.read(1) # Read the "length" byte of the response
	lengthTLV = int.from_bytes(lengthTLV, byteorder='little')
	valueTLV = ser.read(lengthTLV) # Read the value [error code].
	return [typeTLV, lengthTLV, valueTLV]


def parsePOSvalue(value):
	# This helper function takes a 13-byte position code and returns the
	# x, y, z, and q values
	x = int.from_bytes(value[0:4], byteorder='little')
	y = int.from_bytes(value[4:8], byteorder='little')
	z = int.from_bytes(value[8:12], byteorder='little')
	q = int.from_bytes(value[12:13], byteorder='little')
	return [x, y, z, q]


def parseTLV(typeTLV, length, value):
	# TLV_TYPE_DUMMY = bytes.fromhex("00")  # Reserved for SPI dummy byte
	# TLV_TYPE_POS_XYZ = bytes.fromhex("41")  # Response position coordinates x,y,z with q
	# TLV_TYPE_RNG_AN_DIST = bytes.fromhex("48")  # Response: Ranging anchor distances
	# TLV_TYPE_RNG_AN_POS_DIST = bytes.fromhex("49")  # Response: Ranging anchor distances and positions
	if typeTLV == TLV_TYPE_POS_XYZ:
		[x, y, z, q] = parsePOSvalue(value)
		return [x, y, z, q]
	if typeTLV == TLV_TYPE_RNG_AN_DIST:
		# This code may be received from an anchor node
		num_distances = int.from_bytes(value[0:1])
		distances = []
		for i in range (num_distances):
			offset = i*13+1
			addr = value[offset:offset+8].hex()  # Note: Address size is 8 bytes here, not 2 bytes
			d = int.from_bytes(value[offset+8:offset+12], byteorder = 'little')
			dq = int.from_bytes(value[offset+12:offset+13], byteorder = 'little')
			distances.append([addr, d, dq])
		return [num_distances, distances]
	if typeTLV == TLV_TYPE_RNG_AN_POS_DIST:
		num_distances = int.from_bytes(value[0:1], byteorder = 'little')
		distances = []
		for i in range(num_distances):
			offset = i*13+1
			addr = value[offset:offset+2].hex()  # UWB address
			d = int.from_bytes(value[offset+2:offset+6], byteorder = 'little')  # distance
			dq = int.from_bytes(value[offset+6:offset+7], byteorder = 'little')  # distance quality
			[x,y,z,q] = parsePOSvalue(value[offset+7:offset+20])
			distances.append([addr, d, dq, x, y, z, q])
		return [num_distances, distances]
	# Default case:
	print("Error: attempted to parse TLV of type not yet supported.")
	return EXIT_FAILURE


def printTLV(typeTLV, length, value):
	if typeTLV == TLV_TYPE_POS_XYZ:
		print( "{:_<15} {:_<15} {:_<15} {:_<5}".format('x','y','z','q'))
		[x,y,z,q] = parseTLV(typeTLV, length, value)
		print("{:<15} {:<15} {:<15} {:<5}".format(x,y,z,q))
	if typeTLV == TLV_TYPE_RNG_AN_POS_DIST:
		print("{:=<5} {:=<15} {:=<5} {:=<15} {:=<15} {:=<15} {:=<5}".format('addr', 'd', 'dq', 'x', 'y', 'z', 'q'))
		[num_distances, distances] = parseTLV(typeTLV, length, value)
		for i in range(num_distances):
			[addr, d, dq, x, y, z, q] = distances[i]
			print("{:<5} {:<15} {:<5} {:<15} {:<15}  {:<15} {:<5}".format(addr, d, dq, x, y, z, q))
	if typeTLV == TLV_TYPE_RNG_AN_DIST:
		print("{:=<5} {:=<15} {:=<5}".format('addr','d','dq'))
		[num_distances, distances] = parseTLV(typeTLV, length, value)
		for i in range(num_distances):
			[addr, d, dq] = distances[i]
			print("{:<5} {:<15} {:<5}".format(addr, d, dq))


def getLocations():
	# 1. Ask Decawave for Position and distances
	temp = sendTLV(DWM_LOC_GET)
	if temp == EXIT_FAILURE:
		return EXIT_FAILURE
	# -------------
	# 2. Receive response.  May get dummy bytes before real response.
	[typeTLV, length, value]= receiveTLV()
	if value != ERR_CODE_OK:
		print("Received an error message.  Flushing input buffer.")
		print(value)
		ser.reset_input_buffer()
		return EXIT_FAILURE
	# ---------Now, I read until I get the position
	[typeTLV, length, value] = receiveTLV()  # Expect Position
	if length < 13:
		print("No position received.  Flushing buffer.")
		ser.reset_input_buffer()
		return EXIT_FAILURE
	else:
		printTLV(typeTLV, length, value)
	[typeTLV, length, value] = receiveTLV()  # Expect Distances
	if length < 13:
		print("No distances received")
	else:
		printTLV(typeTLV, length, value)



# The following lines allow this script to run as a program if called directly.
if __name__ == "__main__":
	main()
	
