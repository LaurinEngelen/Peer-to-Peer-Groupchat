import json
import socket
import argparse
import threading
import time

# Argumente für Startparameter definieren
parser = argparse.ArgumentParser(description="TCP Client for mathematical operations.")
parser.add_argument("--nickname", type=str, default=1, help="Nickname of User")
parser.add_argument("--ip", type=int, required=True, help="IP of Client")
parser.add_argument("--port_udp", type=int, required=True, help="UDP Port of Client")


args = parser.parse_args()

# Startparameter auslesen
Nickname = args.nickname
IP = args.ip
Port_udp = args.port

Server_IP = '127.0.0.1'
Server_PORT = 50000

AktiveClients = []  # Liste der Clients, die mit dem Server verbunden sind
ConnectedClients = []  # Liste mit den Clientens, mit denen wir verbunden sind

server_tcp_sock = None  # Socket für die Verbindung zum Server
client_tcp_sock = None  # Socket für die Verbindung zu einem Peer
client_udp_sock = None  # Socket für die Verbindung zu einem Peer über UDP

# Server connection thread
def connect_to_tcp(tcp_sock, server_ip, server_port):
    """Establishes a connection to the server and returns the socket object."""
    tcp_sock.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.settimeout(10)
    try:
        print(f"Connecting to server at {server_ip}:{server_port}")
        tcp_sock.connect((server_ip, server_port))
        print("Connected to server.")
    except Exception as e:
        print("Error connecting to server:", e)
        tcp_sock.close()
        return None

def message_to_tcp(tcp_sock, message):
    """Sends a message to the server."""
    try:
        if tcp_sock:
            tcp_sock.send(message.encode('utf-8'))
            print("Message sent to server:", message)
        else:
            print("No active connection to the server.")
    except Exception as e:
        print("Error communicating with server:", e)

def handle_tcp_response(tcp_sock):
    """Handles receiving and processing the server's response."""
    try:
        while True:
            try:
                time.sleep(3)
                msg = tcp_sock.recv(1024).decode('utf-8')
                if not msg:
                    print("Server closed the connection.")
                    break
                print("Response from server:", msg)
            except socket.timeout:
                continue
    except Exception as e:
        print("Error receiving response from server:", e)

def disconnect_from_tcp(tcp_sock):
    """Closes the connection to the server."""
    try:
        if tcp_sock:
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
        print(f"Received message: {data.decode('utf-8')} from {addr}")
    except socket.timeout:
        print("Socket timed out while waiting for a response.")
    except Exception as e:
        print(f"Error receiving UDP response: {e}")

def disconnect_from_udp(udp_sock):
    """Closes the UDP socket."""
    try:
        udp_sock.close()
        print("UDP socket closed.")
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
        body = lines[len(headers) + 2:]
        return status_line, headers, body
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

def addUserToList(body):
    try:
        payload = json.loads(body)
        user = payload.get("user", [])
        AktiveClients.append(user)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return []

def removeUserFromList(body):
    try:
        payload = json.loads(body)
        user = payload.get("user", [])
        AktiveClients.remove(user)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return []

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


def main_menu():
    while True:
        print("\n--- Hauptmenü ---")
        print("1. Mit Server verbinden")
        print("2. Mit einem Client verbinden")
        print("3. Nachrichten mit einem Client austauschen")
        print("4. Beenden")
        choice = input("Wähle eine Option: ").strip()

        if choice == "1":
            connect_to_tcp(server_tcp_sock, Server_IP, Server_PORT)
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
                    threading.Thread(target=handle_udp_response(), args=(client_udp_sock)).start()
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
                    threading.Thread(target=handle_tcp_response(), args=(client_tcp_sock)).start()
                except (ValueError, IndexError):
                    print("Ungültige Auswahl.")
        elif choice == "4":
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
