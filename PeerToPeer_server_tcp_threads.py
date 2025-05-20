import json
import socket
import threading
import time
import argparse

# Argumente für Startparameter definieren
parser = argparse.ArgumentParser(description="TCP Client for mathematical operations.")
parser.add_argument("--ip", type=str, default='127.0.0.1', help="IP of Server")
parser.add_argument("--port", type=int, default=50000, help="Port of Server")

args = parser.parse_args()

# Global stop flag to terminate threads gracefully
StopFlag = False
connected_clients = []  # List to store connected clients
Users = []  # List to store user information "nickname": "Max", "ip": "192.168.0.6", "udp_port": 5001
clients_lock = threading.Lock()  # Lock for thread-safe access to the list

# Server IP and Port
server_ip = args.ip
server_port = args.port

def shutdown_server():
    """Shuts down the server when no clients are connected for 30 seconds."""
    global StopFlag
    print("No clients connected for 30 seconds. Shutting down server...")
    StopFlag = True

def check_clients():
    """Periodically checks if there are no connected clients."""
    global StopFlag
    while not StopFlag:
        time.sleep(30)  # Wait for 30 seconds
        with clients_lock:
            if not connected_clients:  # If no clients are connected
                shutdown_server()
                break

def UserRegistration(message):
    values = message.split(';')
    if len(values) != 3:
        return "Invalid registration message format"
    username = values[0]
    ip = values[1]
    udp_port = int(values[2])

    userInfo = [username, ip, udp_port]
    Users.add(userInfo)
    print("User registered:", userInfo)
    return f"User {userInfo[1]} registration successful"

def find_nickname_by_addr(addr):
    ip, port = addr
    for user in Users:
        if user[1] == ip and user[2] == port:
            return user[0]  # Return the username
    return None

def broadcast(message):
    with clients_lock:
        for client_addr in connected_clients:
            try:
                conn, addr = client_addr
                conn.send(message.encode('utf-8'))
            except Exception as e:
                print(f"Error broadcasting to {addr}: {e}")

def receive(conn, addr):
    global StopFlag
    while not StopFlag:
        try:
            data = conn.recv(1024)
            if not data:  # Connection closed by the client
                print(f"Connection closed by client: {addr}")
                break
            print("Received message:", data.decode('utf-8'))
            response = UserRegistration(data.decode('utf-8'))
            conn.send(response.encode('utf-8'))
        except socket.timeout:
            continue  # Continue listening for data
        except Exception as e:
            print("Error in receive thread:", e)
            break
    with clients_lock:
        connected_clients.remove(addr)  # Remove client from the list
        response = f"Client {find_nickname_by_addr(addr)} disconnected"
        broadcast(response)
    conn.close()

def listen(sock):
    global StopFlag
    while not StopFlag:
        try:
            conn, addr = sock.accept()
            print("New connection accepted from:", addr)
            conn.settimeout(10)  # Set timeout for the connected socket
            with clients_lock:
                connected_clients.append(addr)  # Add client to the list
            threading.Thread(target=receive, args=(conn, addr)).start()
        except socket.timeout:
            continue  # Continue listening for new connections
        except Exception as e:
            print("Error in listen thread:", e)
            break

def print_connected_clients():
    """Periodically prints the list of connected clients."""
    global StopFlag
    while not StopFlag:
        time.sleep(10)  # Wait for 5 seconds
        with clients_lock:
            print("Connected clients:")
            for client in Users:
                print(client)



def register_ackCASP(user_list):
    # JSON-Body erstellen
    body = {
        "type": "register_ack",
        "status": "ok",
        "users": [
            {
                "nickname": user[0],
                "ip": user[1],
                "udp_port": user[2]
            }
            for user in user_list
        ]
    }
    json_body = json.dumps(body)
    content_length = len(json_body)

    # CASP-Nachricht aufbauen
    request = (
        f"OK CASP/1.0\r\n"
        f"Content-Length: {content_length}\r\n"
        f"\r\n"
        f"{json_body}"
    )

    return request

def unregister_ackCASP():
    body = {
        "type": "unregister_ack",
        "status": "ok"
    }
    json_body = json.dumps(body)
    content_length = len(json_body)

    # CASP-Nachricht aufbauen
    request = (
        f"OK CASP/1.0\r\n"
        f"Content-Length: {content_length}\r\n"
        f"\r\n"
        f"{json_body}"
    )

    return request

def broatcast_ackCASP():
    body = {
        "type": "broatcast_ack",
        "status": "ok"
    }
    json_body = json.dumps(body)
    content_length = len(json_body)

    # CASP-Nachricht aufbauen
    request = (
        f"OK CASP/1.0\r\n"
        f"Content-Length: {content_length}\r\n"
        f"\r\n"
        f"{json_body}"
    )

    return request

def update_addCASP(nickname, client_ip,udp_port):
    body = {
        "type": "user_update",
        "action": "add",
        "user": {
        "nickname": nickname,
        "ip": client_ip,
        "udp_port": udp_port
        }
    }
    json_body = json.dumps(body)
    content_length = len(json_body)

    # CASP-Nachricht aufbauen
    request = (
        f"UPDATE CASP/1.0\r\n"
        f"Host: {server_ip}\r\n"
        f"Content-Length: {content_length}\r\n"
        f"\r\n"
        f"{json_body}"
    )

    return request

def update_removeCASP(nickname, client_ip):
    body = {
        "type": "user_update",
        "action": "remove",
        "user": {
            "nickname": nickname,
            "ip": client_ip
        }
    }
    json_body = json.dumps(body)
    content_length = len(json_body)

    # CASP-Nachricht aufbauen
    request = (
        f"UPDATE CASP/1.0\r\n"
        f"Host: {server_ip}\r\n"
        f"Content-Length: {content_length}\r\n"
        f"\r\n"
        f"{json_body}"
    )

    return request

# Main server setup
My_IP = args.ip
My_PORT = args.port

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind((My_IP, My_PORT))
sock.listen(5)  # Allow up to 5 pending connections
sock.settimeout(10)  # Set timeout for the listening socket

print("Server is listening on", My_PORT)

# Start the thread to print connected clients
threading.Thread(target=print_connected_clients, daemon=True).start()

# Start the thread to check for no connected clients
threading.Thread(target=check_clients, daemon=True).start()

try:
    listen(sock)
except KeyboardInterrupt:
    print("Shutting down server...")
    StopFlag = True
finally:
    sock.close()