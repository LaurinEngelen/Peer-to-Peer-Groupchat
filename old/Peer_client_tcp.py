import json
import socket
import argparse
import threading
import time

# Argumente für Startparameter definieren
parser = argparse.ArgumentParser(description="TCP Client for mathematical operations.")
parser.add_argument("--nickname", type=str, help="Nickname of User")
parser.add_argument("--ip", type=str, help="IP of Client")
parser.add_argument("--port_udp", type=int, help="UDP Port of Client")


args = parser.parse_args()

# Startparameter auslesen
OWN_NICKNAME = args.nickname or "TestClient"
OWN_IP = args.ip or "127.0.0.1"
OWN_UDP_PORT = args.port_udp or 50001
OWN_TCP_PORT_CLIENTS = None
OWN_TCP_PORT_SERVER = None

server_tcp_sock = None  # Socket für die Verbindung zum Server
client_tcp_sock = None  # Socket für die Verbindung zu einem Peer
client_udp_sock = None  # Socket für die Verbindung zu einem Peer über UDP

Server_IP = '127.0.0.1'
Server_PORT = 50000

connected_sockets = {
    "server": None,  # Active socket for the server
    "clients": {}   # Dictionary to store client nicknames and their sockets
}

UserList = []  # List to store the clients returned by the server

is_running = True
clients_lock = threading.Lock()

# Server connection thread

def setup_tcp_socket_server(server_ip, server_port):
    """Sets up a TCP socket for communication with the server."""
    global OWN_TCP_PORT_SERVER
    global server_tcp_sock
    try:
        server_tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_tcp_sock.settimeout(10)  # Set a timeout for the connection
        server_tcp_sock.connect((server_ip, server_port))
        print(f"TCP socket created and connected to {server_ip}:{server_port}")
        OWN_TCP_PORT_SERVER = server_tcp_sock.getsockname()[1]

        # Send registration message to the server
        message_to_tcp(server_tcp_sock, registerCASP(OWN_NICKNAME, OWN_IP, OWN_UDP_PORT))
        threading.Thread(target=handle_tcp_response, args=(server_tcp_sock,), daemon=True).start()
    except Exception as e:
        print(f"Error setting up TCP socket: {e}")

def setup_tcp_socket_client():
    """Sets up a TCP socket for communication with a specific client."""
    global OWN_TCP_PORT_CLIENTS
    global client_tcp_sock
    try:
        client_tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_tcp_sock.settimeout(10)  # Set a timeout for the connection
        print(f"TCP socket created")
        OWN_TCP_PORT_CLIENTS = client_tcp_sock.getsockname()[1]

        # Start a thread to handle incoming client connections
        threading.Thread(target=accept_client_connections, daemon=True).start()
    except Exception as e:
        print(f"Error setting up TCP socket: {e}")


def accept_client_connections():
    """Thread to accept incoming TCP client connections."""
    global client_tcp_sock
    while is_running:
        try:
            client_sock, client_addr = client_tcp_sock.accept()
            print(f"New client connected: {client_addr}")
            # Add the new client socket to the connected_sockets dictionary and UserList
            with clients_lock:
                connected_sockets["clients"][client_addr[0]] = client_sock
                add_user_to_list((client_addr[0], client_addr[1], OWN_UDP_PORT), tcp_socket=client_sock, tcp_port=OWN_TCP_PORT_CLIENTS)

            # Start a new thread to handle the client
            threading.Thread(target=handle_tcp_response, args=(client_sock,), daemon=True).start()
        except Exception as e:
            if is_running:
                print(f"Error accepting new connection: {e}")

def message_to_tcp(tcp_sock, message):
    """Sends a message to the server."""
    try:
        if tcp_sock:
            tcp_sock.send(message.encode('utf-8'))
            #print("Message sent to server:" + message)
        else:
            print("No active connection to the server.")
    except Exception as e:
        print("Error communicating with server:", e)

def connect_to_client_tcp(client_ip, client_tcp_port):
    """Connects to a specific client over TCP."""
    global client_tcp_sock
    try:
        client_tcp_sock.connect((client_ip, client_tcp_port))
        print(f"Connected to client {client_ip}:{client_tcp_port}")

        # Send connect request to the server
        message_to_tcp(client_tcp_sock, connectCACP(OWN_NICKNAME, OWN_IP, OWN_UDP_PORT))
        return client_tcp_sock
    except Exception as e:
        print(f"Error connecting to client {client_ip}:{client_tcp_port} - {e}")
        return None

def handle_tcp_response(tcp_sock):
    global is_running
    try:
        while is_running:
            try:
                time.sleep(1)
                msg = tcp_sock.recv(1024).decode('utf-8')
                if not msg:
                    print("Server closed the connection.")
                    break
                messageHandler(decodeResponse(msg)[2])
            except socket.timeout:
                continue
    except Exception as e:
        if is_running:
            print("Error receiving response from server:", e)


def disconnect_from_tcp(tcp_sock):
    """Closes the connection to the server."""
    global is_running
    try:
        if tcp_sock:
            message_to_tcp(tcp_sock, unregisterCASP(OWN_NICKNAME, OWN_IP))
            time.sleep(1)
            is_running = False  # Stop the thread
            tcp_sock.close()
            print("Disconnected from server.")
    except Exception as e:
        print("Error disconnecting from server:", e)


def setup_udp_socket(own_ip, own_port):
    """Sets up a UDP socket for communication."""
    global client_udp_sock
    try:
        client_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_udp_sock.bind((own_ip, own_port))
        client_udp_sock.settimeout(10)  # Set a timeout for receiving data
        print(f"UDP socket created and listening on {OWN_IP}:{OWN_UDP_PORT}")

        # Start a thread to listen for incoming UDP messages
        threading.Thread(target=handle_udp_response, daemon=True).start()
    except Exception as e:
        print(f"Error setting up UDP socket: {e}")

def handle_udp_response():
    """Thread to listen for incoming UDP messages."""
    global client_udp_sock
    while is_running:
        try:
            data, addr = client_udp_sock.recvfrom(1024)
            if data:
                print(f"Received UDP message from {addr}: {data.decode('utf-8')}")
                messageHandler(decodeResponse(data.decode('utf-8'))[2])
        except socket.timeout:
            continue
        except Exception as e:
            print(f"Error receiving UDP message: {e}")
            break

def message_to_udp(udp_sock, message, client_ip, client_port):
    """Sends a message to a specific client over UDP."""
    try:
        if udp_sock:
            udp_sock.sendto(message.encode('utf-8'), (client_ip, client_port))
            print(f"UDP message sent to {client_ip}:{client_port}: {message}")
        else:
            print("No active UDP socket to send message.")
    except Exception as e:
        print(f"Error sending UDP message: {e}")

def disconnect_from_udp(udp_sock):
    """Closes the UDP socket."""
    try:
        if udp_sock:  # Check if the socket is not None
            udp_sock.close()
            print("UDP socket closed.")
        else:
            print("No UDP socket to close.")
    except Exception as e:
        print(f"Error closing UDP socket: {e}")

def decodeResponse(response):
    try:
        lines = response.split('\r\n')
        status_line = lines[0]
        headers = {}
        for line in lines[1:]:
            if line == '':
                break
            key, value = line.split(': ', 1)
            headers[key] = value
        body = '\n'.join(lines[len(headers) + 2:])
        body_dict = json.loads(body)  # Parse body into a dictionary
        return status_line, headers, body_dict
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON body: {e}")
        return None, None, None
    except Exception as e:
        print(f"Error decoding response: {e}")
        return None, None, None

def extractUserList(body):
    try:
        payload = json.loads(body)
        users = payload.get("users", [])
        return [(user["nickname"], user["ip"], user["udp_port"]) for user in users]
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return []

def add_user_to_list(user, tcp_socket=None, tcp_port=None):
    """Adds a user to the UserList with optional TCP socket and port."""
    user_entry = {
        "nickname": user[0],
        "ip": user[1],
        "udp_port": user[2],
        "tcp_socket": tcp_socket,
        "tcp_port": tcp_port
    }
    if user_entry not in UserList:
        UserList.append(user_entry)
        print(f"User added to UserList: {user_entry}")
    else:
        print(f"User already exists in UserList: {user_entry}")

def remove_user_from_list(nickname):
    """Removes a user from the UserList."""
    user = get_user_by_nickname(nickname)
    if user in UserList:
        UserList.remove(user)
        print(f"User removed from UserList: {user}")
    else:
        print(f"User not found in UserList: {user}")

def print_user_list():
    """Displays the current UserList."""
    if not UserList:
        print("Keine Benutzer in der Liste.")
    else:
        print("\nAktuelle Benutzerliste:")
        for user in UserList:
            print(f"Nickname: {user['nickname']}, IP: {user['ip']}, UDP-Port: {user['udp_port']}")

def get_user_by_nickname(nickname):
    """Retrieves a user from the UserList by their nickname."""
    for user in UserList:
        if user["nickname"] == nickname:
            return user
    return None


def send_casp_message(sock, casp_message):
    try:
        print("Sending CASP message:")
        print(casp_message)
        sock.sendall(casp_message.encode('utf-8'))

        # Receive the server's response
        response = sock.recv(1024).decode('utf-8')
        print("Received response from server:")
        print(response)
        return response
    except Exception as e:
        print(f"Error sending CASP message: {e}")
        return f"Error: {e}"

def registerCASP(nickname, client_ip, udp_port):
    # JSON-Body erstellen
    body = {
        "type": "register",
        "nickname": nickname,
        "ip": client_ip,
        "udp_port": udp_port
    }
    json_body = json.dumps(body)
    content_length = len(json_body)

    # CASP-Nachricht aufbauen
    request = (
        f"REGISTER CASP/1.0\r\n"
        f"Host: {client_ip}\r\n"
        f"Content-Length: {content_length}\r\n"
        f"\r\n"
        f"{json_body}"
    )

    return request

def unregisterCASP(nickname, client_ip):
    # JSON-Body erstellen
    body = {
        "type": "unregister",
        "nickname": nickname,
        "ip": client_ip
    }
    json_body = json.dumps(body)
    content_length = len(json_body)

    # CASP-Nachricht aufbauen
    request = (
        f"UNREGISTER CASP/1.0\r\n"
        f"Host: {client_ip}\r\n"
        f"Content-Length: {content_length}\r\n"
        f"\r\n"
        f"{json_body}"
    )

    return request


def broadcastCASP(nickname, message):
    # JSON-Body erstellen
    body = {
        "type": "broadcast",
        "nickname": nickname,
        "message": message
    }
    json_body = json.dumps(body)
    content_length = len(json_body)

    # CASP-Nachricht aufbauen
    request = (
        f"BROADCAST CASP/1.0\r\n"
        f"Host: {OWN_IP}\r\n"
        f"Content-Length: {content_length}\r\n"
        f"\r\n"
        f"{json_body}"
    )

    return request

def acknowledgeCASP():
    body = {
        "type": "update_ack",
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

def connectCACP(nickname, client_ip, udp_port):
    # JSON-Body erstellen
    body = {
        "type": "connect_request",
        "nickname": nickname,
        "ip": client_ip,
        "udp_port": udp_port
    }
    json_body = json.dumps(body)
    content_length = len(json_body)

    # CASP-Nachricht aufbauen
    request = (
        f"CONNECT CACP/1.0\r\n"
        f"Host: {client_ip}\r\n"
        f"Content-Length: {content_length}\r\n"
        f"\r\n"
        f"{json_body}"
    )

    return request

def connect_ackCACP(client_ip):
    # JSON-Body erstellen
    body = {
        "type": "connect_ack",
        "status": "ok"
        }
    json_body = json.dumps(body)
    content_length = len(json_body)

    # CASP-Nachricht aufbauen
    request = (
        f"OK CACP/1.0\r\n"
        f"Host: {client_ip}\r\n"
        f"Content-Length: {content_length}\r\n"
        f"\r\n"
        f"{json_body}"
    )

    return request

def messageCACP(client_ip, from_client, to_client, message):
    # JSON-Body erstellen
    body = {
        "type": "message",
        "from": from_client,
        "to": to_client,
        "message": message
    }
    json_body = json.dumps(body)
    content_length = len(json_body)

    # CASP-Nachricht aufbauen
    request = (
        f"MESSAGE CACP/1.0\r\n"
        f"Host: {client_ip}\r\n"
        f"Content-Length: {content_length}\r\n"
        f"\r\n"
        f"{json_body}"
    )

    return request

def message_ackCACP(client_ip):
    # JSON-Body erstellen
    body = {
        "type": "message_ack",
        "status": "ok"
    }
    json_body = json.dumps(body)
    content_length = len(json_body)

    # CASP-Nachricht aufbauen
    request = (
        f"OK CACP/1.0\r\n"
        f"Host: {client_ip}\r\n"
        f"Content-Length: {content_length}\r\n"
        f"\r\n"
        f"{json_body}"
    )

    return request

def messageHandler(payload):
    try:
        message_type = payload.get("type", "")
        if message_type == "register_ack":
            print("Register Acknowledge received.")
            user_list = payload.get("users", [])
            for user in user_list:
                add_user_to_list(user)
            print("Active clients:", print_user_list())
        elif message_type == "unregister_ack":
            print("Unregister Acknowledge received.")
            connected_sockets.clear()
            UserList.clear()
        elif message_type == "user_update":
            if payload.get("action") == "add":
                add_user_to_list(payload["user"])
                print("User added:", payload["user"])
            elif payload.get("action") == "remove":
                remove_user_from_list(payload["user"]["nickname"])
                print("User removed:", payload["user"])
        elif message_type == "message":
            print("Message received from", payload["from"], "to", payload["to"])
            print("Message content:", payload["message"])
            # Send acknowledgment back to the sender
            message_to_tcp(client_tcp_sock, message_ackCACP(OWN_IP))
        elif message_type == "connect_request":
            print("Connect request received from", payload.get("from"))
            try:
                # Validate payload
                client_ip = payload["ip"]
                client_tcp_port = payload["tcp_port"]
                client_nickname = payload["from"]

                # Open a new TCP connection to the client
                client_tcp_sock = connect_to_client_tcp(client_ip, client_tcp_port, client_nickname)

        elif message_type == "connect_ack":
            print("Connect acknowledgment received from", payload.get("from"))
            try:
                # Validate payload
                client_ip = payload["ip"]
                client_tcp_port = payload["tcp_port"]
                client_nickname = payload["from"]

                # Ensure the client is already connected
                if client_nickname not in connected_sockets["clients"]:
                    print(f"Client {client_nickname} not found in connected_sockets. Attempting to connect...")
                    tcp_sock = connect_to_client_tcp(client_ip, client_tcp_port, client_nickname)
                    if tcp_sock:
                        connected_sockets["clients"][client_nickname] = tcp_sock
                        print(f"Connected to {client_nickname} at {client_ip}:{client_tcp_port}")
                    else:
                        print(f"Failed to connect to {client_nickname} at {client_ip}:{client_tcp_port}")
                else:
                    print(f"Client {client_nickname} is already connected.")
            except KeyError as e:
                print(f"Invalid connect_ack payload: missing key {e}")
            except Exception as e:
                print(f"Error handling connect_ack: {e}")
        elif message_type == "broadcast":
            print("Broadcast message received from", payload["from"])
            print("Message content:", payload["message"])
        else:
            print(f"Unknown message type: {message_type}")
    except Exception as e:
        print(f"Error handling message: {e}")



def main_menu():
    global server_tcp_sock  # Ensure the global variable is used
    while True:
        print("\n--- Hauptmenü ---")
        print("1. Mit Server verbinden")
        print("2. Mit einem Client verbinden")
        print("3. Nachrichten mit einem Client austauschen")
        print("4. Vom Server trennen")
        print("5. User-Liste anzeigen")
        print("6. Beenden")

        choice = input("Wähle eine Option: ").strip()

        if choice == "1":
            server_tcp_sock = connect_to_tcp(Server_IP, Server_PORT)
            if server_tcp_sock:
                message_to_tcp(server_tcp_sock, registerCASP(OWN_NICKNAME, OWN_IP, OWN_UDP_PORT))
                threading.Thread(target=handle_tcp_response, args=(server_tcp_sock,)).start()
        elif choice == "2":
            nickname = input("Gib den Nickname des Clients ein: ").strip()
            client_ip = input("Gib die IP des Clients ein: ").strip()
            client_port_udp = int(input("Gib den Port des Clients ein: ").strip())
            # Create and start the thread for the TCP socket
            tcp_thread = threading.Thread(target=setup_tcp_socket, args=(client_ip, client_port_udp, nickname), daemon=True)
            tcp_thread.start()

        elif choice == "3":
            if not connected_sockets["clients"]:
                print("Keine aktiven Clients verfügbar.")
            else:
                print("Aktive Clients:")
                for i, nickname in enumerate(connected_sockets["clients"]):
                    print(f"{i + 1}. {nickname}")
                client_choice = input("Wähle einen Client (Nummer): ").strip()
                try:
                    client_index = int(client_choice) - 1
                    nickname = list(connected_sockets["clients"].keys())[client_index]
                    client_sock = connected_sockets["clients"][nickname]
                    message = input("Nachricht eingeben: ")
                    message_to_tcp(client_sock, messageCACP(OWN_IP, OWN_NICKNAME, nickname, message))
                    print(f"Nachricht an {nickname} gesendet.")
                except (ValueError, IndexError):
                    print("Ungültige Auswahl.")
        elif choice == "4":
            if server_tcp_sock:
                disconnect_from_tcp(server_tcp_sock)
                server_tcp_sock = None
                print("Vom Server getrennt.")
            else:
                print("Keine aktive Verbindung zum Server.")
        elif choice == "5":
            print_user_list()
        elif choice == "6":
            print("Programm wird beendet.")
            disconnect_from_tcp(server_tcp_sock)
            disconnect_from_tcp(client_tcp_sock)
            disconnect_from_udp(client_udp_sock)
            break
        else:
            print("Ungültige Eingabe. Bitte erneut versuchen.")

# Hauptprogramm starten
if __name__ == "__main__":
    setup_tcp_socket_server(Server_IP, Server_PORT)
    setup_tcp_socket_client()
    setup_udp_socket(OWN_IP, OWN_UDP_PORT)

    main_menu()
