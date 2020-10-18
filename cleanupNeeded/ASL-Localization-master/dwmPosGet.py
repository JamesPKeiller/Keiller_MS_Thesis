# dwmPosGet
# Being written September 2019 by James Keiller
# This script is being written to test approach to 
# reading TLV (type, length, value) data from an attached
# Decawave DWM 1001 module through the UART TLV interface.
# This script simply calls the dwm_pos_get TLV request
# repeatedly, parses the result, and prints the result.

# Used for DWM1001 devices with default firmware connected through USB UART
# Currently limited to Python 3.6+ on Windows machines

import serial
import time
import sys
import argparse

global myPort # The name of the serial port to use
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


global ser  # This will be the name of the handle to the serial port
ser = None	 #

def main():
	global myPort
	global ser
	print("dwmPosGet started.")
	myPort = myParser()
	# Establish serial port connection
	try:
		ser = serial.Serial(myPort, 115200, timeout=1)
		print(ser)
		print("Connection established.")
	except:
		print("Error in trying to connect to serial port " + myPort)
	stopLoop = False
	# Loop plan:
	# 1. Ask Decawave for position
	# 2. Receive response, parsing as I go
	# --First response is confirmation / error code
	# --Second response is position
	# 2.5 Error handling
	# 3. Output message
	# ----------
	while (stopLoop == False):
		# 1. Ask Decawave for Position
		# txBuffer = bytes.fromhex("0C 00") #This is what I eventually want to write code to request
		# For the moment, I will instead request just the position with "02 00".
		txBuffer = bytes.fromhex("02 00")
		
		try:
			ser.write(txBuffer)
		except:
			print("Error during transmission of request 0x02 0x00")
			stopLoop = True
			break
		# -------------
		# 2. Receive response.  Type 00 = not ready, 40 is response
		typeTLV = bytes.fromhex("00")
		while typeTLV == bytes.fromhex("00"):
			typeTLV = ser.read(1) # Read the first byte of the response
			print("Waiting for type to stop being 0x00.  Type code read is: " + typeTLV.hex())
		# Read the byte that describes the length of the value.  Expect 0x01
		# at this part of the sequence.		
		lengthTLV = ser.read(1)
		lengthTLV = int.from_bytes(lengthTLV, byteorder='little')
		print("length of TLV payload is (expect 1): {0}".format(lengthTLV))

		# Read the value [error code].  Expect 0x00 if all is well
		valueTLV = ser.read(lengthTLV)
		print("Error code is: {0}".format(valueTLV.hex()))

		# SECOND I check to see if the message was bad.
		if valueTLV != bytes.fromhex("00"):
			print("Received an error message.  Flushing input buffer.")
			print(valueTLV)
			ser.reset_input_buffer()
			continue
		# ---------Now, I read until I get the position
		print("Have confirmation.  Now getting position.") # Debug
		typeTLV = bytes.fromhex("00")
		while typeTLV == bytes.fromhex("00"):
# Read the first byte of the response
			# Expect to see 0x40 in the TLV message that delivers the
			# error code.  Then will see 0x41 for the TLV message type that
			# delivers the position.
			typeTLV = ser.read(1)
			print("Received: {0}".format(typeTLV.hex()))

		print("Now reading the length byte.  Expect 13.")
		lengthTLV = ser.read(1)
		lengthTLV = int.from_bytes(lengthTLV, byteorder='little')
		print(lengthTLV)
		valueTLV = ser.read(lengthTLV)
		if lengthTLV != len(valueTLV):
			print("Error: Length read doesn't match length expected!")
			print("Length expected: ")
			print(lengthTLV)
			print("Value received:")
			print(valueTLV)
		num_positions = lengthTLV // 13
		for i in range(num_positions):
			x = int.from_bytes(valueTLV[i*13:i*13+4], byteorder='little')
			y = int.from_bytes(valueTLV[i*13+4:i*13+8], byteorder='little')
			z = int.from_bytes(valueTLV[i*13+8:i*13+12], byteorder='little')
			q = int.from_bytes(valueTLV[i*13+12:i*13+13], byteorder='little')
			print("x: {}\t y: {}\t z: {}\t q: {}".format(x, y, z, q))
		print("TLV value is: {}".format(valueTLV))


# The following lines allow this script to run as a program if called directly.
if __name__ == "__main__":
	main()
	
