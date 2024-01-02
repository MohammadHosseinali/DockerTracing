import socket
import sys
from time import sleep

# Create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect the socket to the port where the server is listening
server_address = (sys.argv[1], 10000)
print( 'connecting to %s port %s' % server_address)


sock.connect(server_address)


try:
    while(True):
	    # Send data
	    message = 'This is the message.  It will be repeated.'
	    print( 'sending "%s"' % message)
	    sock.sendall(message.encode())

	    # Look for the response
	    amount_received = 0
	    amount_expected = len(message)
	    
	    while amount_received < amount_expected:
                data = sock.recv(128)
                amount_received += len(data)
                print( 'received "%s"' % data.decode())

finally:
    print( 'closing socket')
    sock.close()
    #sleep(0.1)

