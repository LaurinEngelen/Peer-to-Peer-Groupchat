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
Nickname = args.nickname or "TestClient"
IP = args.ip or "127.0.0.1"
Port_udp = args.port_udp or 50001

Server_IP = '127.0.0.1'
Server_PORT = 50000

AktiveClients = []  # Liste der Clients, die mit dem Server verbunden sind
ConnectedClients = []  # Liste mit den Clientens, mit denen wir verbunden sind

is_running = True

server_tcp_sock = None  # Socket für die Verbindung zum Server
client_tcp_sock = None  # Socket für die Verbindung zu einem Peer
client_udp_sock = None  # Socket für die Verbindung zu einem Peer über UDP

# Server connection thread
def connect_to_tcp(server_ip, server_port):
    """Establishes a connection to the server and returns the socket object."""
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Initialize the socket here
    tcp_sock.settimeout(10)
    try:
        print(f"Connecting to server at {server_ip}:{server_port}")
        tcp_sock.connect((server_ip, server_port))
        print("Connected to server.")
        return tcp_sock  # Return the socket object
    except Exception as e:
        print("Error connecting to server:", e)
        tcp_sock.close()
        return None

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

def handle_tcp_response(tcp_sock):
    """Handles receiving and processing the server's response."""
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
        if is_running:  # Only print the error if the thread is not stopped intentionally
            print("Error receiving response from server:", e)


def disconnect_from_tcp(tcp_sock):
    """Closes the connection to the server."""
    global is_running
    try:
        if tcp_sock:
            message_to_tcp(tcp_sock, unregisterCASP(Nickname, IP))
            time.sleep(1)
            is_running = False  # Stop the thread
            tcp_sock.close()
            print("Disconnected from server.")
    except Exception as e:
        print("Error disconnecting from server:", e)

def connect_to_udp(udp_sock, peer_ip, peer_port, nickname, own_ip, own_port):
    """Sets up the UDP socket and sends an initial message to the peer."""
    udp_sock.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind((own_ip, own_port))
    udp_sock.settimeout(10)

    message = connectCACP(nickname, own_ip, own_port)
    try:
        udp_sock.sendto(message.encode('utf-8'), (peer_ip, peer_port))
        print(f"Message sent to {peer_ip}:{peer_port}")
    except Exception as e:
        print(f"Error during UDP connection: {e}")

def handle_udp_response(udp_sock):
    """Handles receiving and processing the response from the peer."""
    try:
        data, addr = udp_sock.recvfrom(1024)
        messageHandler(data)
    except socket.timeout:
        print("Socket timed out while waiting for a response.")
    except Exception as e:
        print(f"Error receiving UDP response: {e}")

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

def addUserToList(user):
    try:
        AktiveClients.append(user)
    except Exception as e:
        print(f"Error adding user to list: {e}")
        return []

def removeUserFromList(body):
    try:
        # Check if `body` is already a dictionary
        if isinstance(body, str):
            payload = json.loads(body)
        elif isinstance(body, dict):
            payload = body
        else:
            raise ValueError("Unsupported body type")

        # Extract user details
        user = payload.get("user", {})
        nickname = user.get("nickname")
        ip = user.get("ip")
        udp_port = user.get("udp_port")

        # Validate user details
        if nickname is None or ip is None or udp_port is None:
            print(f"Invalid user data: {user}")
            return

        user_tuple = (nickname, ip, udp_port)

        # Check if the user exists in the list before removing
        if user_tuple in AktiveClients:
            AktiveClients.remove(user_tuple)
            print(f"User removed: {user_tuple}")
            return
        else:
            print(f"User not found in AktiveClients: {user_tuple}")
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error removing user from list: {e}")

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
        f"Host: {IP}\r\n"
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
        #print(f"Debug: Parsed payload: {payload}")

        message_type = payload.get("type", "")
        if message_type == "register_ack":
            print("Register Acknowledge received.")
            user_list = payload.get("users", [])
            AktiveClients.extend(user_list)
            print("Active clients:", AktiveClients)
        elif message_type == "unregister_ack":
            print("Unregister Acknowledge received.")
            AktiveClients.clear()
            print("Active clients:", AktiveClients)
        elif message_type == "connect_ack":
            print("Connect Acknowledge received.")
            user = payload.get("user", [])
            ConnectedClients.append(user)
            print("Connected clients:", ConnectedClients)
        elif message_type == "message":
            print("Message received:", payload["message"])
        elif message_type == "user_update":
            if payload.get("action") == "add":
                print("User added:", payload["user"])
                addUserToList(payload["user"])
            elif payload.get("action") == "remove":
                print("User removed:", payload["user"])
                removeUserFromList(payload["user"])
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
        print("5. Beenden")

        choice = input("Wähle eine Option: ").strip()

        if choice == "1":
            server_tcp_sock = connect_to_tcp(Server_IP, Server_PORT)
            if server_tcp_sock:
                message_to_tcp(server_tcp_sock, registerCASP(Nickname, IP, Port_udp))
                threading.Thread(target=handle_tcp_response, args=(server_tcp_sock,)).start()
        elif choice == "2":
            if not AktiveClients:
                print("Keine aktiven Clients verfügbar.")
            else:
                print("Aktive Clients:")
                for i, client in enumerate(AktiveClients):
                    print(f"{i + 1}. {client}")
                client_choice = input("Wähle einen Client (Nummer): ").strip()
                try:
                    client_index = int(client_choice) - 1
                    peer_ip, peer_port = AktiveClients[client_index][1], AktiveClients[client_index][2]
                    connect_to_udp(client_udp_sock, peer_ip, peer_port, Nickname, IP, Port_udp)
                    threading.Thread(target=handle_udp_response, args=(client_udp_sock,)).start()
                except (ValueError, IndexError):
                    print("Ungültige Auswahl.")
        elif choice == "3":
            if not ConnectedClients:
                print("Keine aktiven Clients verfügbar.")
            else:
                print("Aktive Clients:")
                for i, client in enumerate(ConnectedClients):
                    print(f"{i + 1}. {client}")
                client_choice = input("Wähle einen Client (Nummer): ").strip()
                message = input("Nachricht eingeben: ")
                try:
                    client_index = int(client_choice) - 1
                    peer_ip, peer_port = ConnectedClients[client_index][1], ConnectedClients[client_index][2]
                    message_to_tcp(client_tcp_sock, messageCACP(IP, Nickname, peer_ip, message))
                    threading.Thread(target=handle_tcp_response, args=(client_tcp_sock,)).start()
                except (ValueError, IndexError):
                    print("Ungültige Auswahl.")

        elif choice == "4":
            if server_tcp_sock:
                disconnect_from_tcp(server_tcp_sock)
                server_tcp_sock = None  # Reset the socket to None
                print("Vom Server getrennt.")
            else:
                print("Keine aktive Verbindung zum Server.")

        elif choice == "5":
            print("Programm wird beendet.")
            disconnect_from_tcp(server_tcp_sock)
            disconnect_from_tcp(client_tcp_sock)
            disconnect_from_udp(client_udp_sock)
            break
        else:
            print("Ungültige Eingabe. Bitte erneut versuchen.")

# Hauptprogramm starten
if __name__ == "__main__":
    main_menu()
