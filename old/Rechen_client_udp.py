import socket
import time

ID = 1 # ID des Clients
RechenOP = "SUM" # SUM, PRO, MIN, MAX
NZahlen = 2 # Anzahl der Zahlen
Zahlen = [2, 3] # Zahlen

# Message Format: <ID><Rechenoperation><N><z1><z2>…<zN>
def MessageBuilder(ID, RechenOP, NZahlen, Zahlen):
    message = f"<{ID}><{RechenOP}><{NZahlen}>" + "".join([f"<{zahl}>" for zahl in Zahlen])
    return message

Server_IP = '127.0.0.1'
Server_PORT = 50000

MESSAGE = MessageBuilder(ID, RechenOP, NZahlen, Zahlen)
print('Sending message', MESSAGE, 'to UDP server with IP ', Server_IP, ' on Port=', Server_PORT)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
sock.settimeout(10)
sock.sendto(MESSAGE.encode('utf-8'), (Server_IP, Server_PORT))
try:
    data, addr = sock.recvfrom(1024)
    print('received message: '+data.decode('utf-8')+' from ', addr)
except socket.timeout:
    print('Socket timed out at',time.asctime())

sock.close()


