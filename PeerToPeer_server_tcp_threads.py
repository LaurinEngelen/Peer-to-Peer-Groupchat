import json
import socket
import threading
import time
import argparse


# Global variables
StopFlag = False
connected_sockets = []
client_data = {}  # Dictionary to store client information
clients_lock = threading.Lock()

server_ip = "127.0.0.1"
server_port = 50000

def add_client_info(conn, addr, nickname=None, udp_port=0):
    """Adds client information to the client_data dictionary."""
    with clients_lock:
        client_data[conn] = {
            "conn": conn,  # Store the connection object
            "addr": addr,
            "nickname": nickname,
            "udp_port": udp_port
        }
        #print(f"Client info added: {addr}, Nickname: {nickname}, UDP Port: {udp_port}")

def update_client_info(conn, nickname, udp_port):
    """Updates client information in the client_data dictionary."""
    with clients_lock:
        if conn in client_data:
            client_data[conn]["nickname"] = nickname
            client_data[conn]["udp_port"] = udp_port
            #print(f"Client info updated: {client_data[conn]}")

def remove_client_info(conn):
    """Removes client information from the client_data dictionary."""
    with clients_lock:
        if conn in client_data:
            #print(f"Removing client info: {client_data[conn]}")
            del client_data[conn]

def get_client_info(conn):
    """Retrieves client information by socket connection."""
    with clients_lock:
        return client_data.get(conn)

def tui():
    """Simple Text User Interface."""
    global StopFlag
    while not StopFlag:
        print("\n--- Server Menu ---")
        print("1. Start Server")
        print("2. View Connected Clients")
        print("3. Broadcast Message")
        print("4. Shutdown Server")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            server_ip = input("Enter server IP (default 127.0.0.1): ").strip() or "127.0.0.1"
            server_port = int(input("Enter server port (default 50000): ").strip() or 50000)
            start_server(server_ip, server_port)
        elif choice == "2":
            with clients_lock:
                if client_data:
                    print("Connected Clients:")
                    for client in client_data.values():
                        print(f" - {client['nickname']} (IP: {client['addr'][0]}, UDP Port: {client['udp_port']})")
                else:
                    print("No clients connected.")
        elif choice == "3":
            message = input("Enter message to broadcast: ").strip()
            broadcast(message)
        elif choice == "4":
            print("Shutting down server...")
            StopFlag = True
            break
        else:
            print("Invalid choice. Please try again.")

def start_server(server_ip, server_port):
    """Starts the TCP server."""
    global StopFlag
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((server_ip, server_port))
    server_sock.listen(5)
    server_sock.settimeout(1)
    print(f"Server started on {server_ip}:{server_port}")
    threading.Thread(target=accept_connections, args=(server_sock,)).start()

def close_all_connections():
    """Closes all active client connections."""
    with clients_lock:
        for client in client_data.values():
            try:
                client["conn"].close()
                print(f"Closed connection to {client['addr']}")
            except Exception as e:
                print(f"Error closing connection to {client['addr']}: {e}")
        client_data.clear()

def shutdown_server(server_sock):
    """Shuts down the server."""
    global StopFlag
    StopFlag = True
    server_sock.close()  # Interrupt accept() in accept_connections
    print("Server shutting down...")


def find_nickname_by_addr(addr):
    """Finds a client's nickname by their address."""
    client = get_client_by_addr(addr)
    return client["nickname"] if client else None

def get_client_by_addr(addr):
    """Finds a client by their address."""
    with clients_lock:
        for client in client_data.values():
            if client["addr"] == addr:
                return client
    return None

def broadcast(message, exclude_conn=None):
    """Broadcasts a message to all connected clients except the excluded one."""
    with clients_lock:
        for client in list(client_data.values()):
            if client["conn"] == exclude_conn:
                print(f"Skipping client: {client['nickname']} at {client['addr']}")
                continue  # Skip the excluded connection
            try:
                print(f"Broadcasting to client: {client['nickname']} at {client['addr']}")
                client["conn"].send(message.encode('utf-8'))
            except Exception as e:
                print(f"Error broadcasting to {client['addr']}: {e}")
                client["conn"].close()
                remove_client_info(client["conn"])

def accept_connections(server_sock):
    """Accepts new connections and starts a thread for each client."""
    global StopFlag
    while not StopFlag:
        try:
            conn, addr = server_sock.accept()
            print(f"\nNew connection from {addr}")
            add_client_info(conn, addr, f"Client-{addr[1]}", 0)  # Add placeholder info to clients
            threading.Thread(target=handle_client, args=(conn, addr)).start()
        except socket.timeout:
            continue  # Allow periodic checks of StopFlag
        except OSError:
            # Socket closed during shutdown
            break
        except Exception as e:
            print(f"\nError accepting connections: {e}")

def handle_client(conn, addr):
    """Handles communication with a single client."""
    try:
        conn.settimeout(1)
        add_client_info(conn, addr)  # Add client with placeholder info
        while not StopFlag:
            try:
                data = conn.recv(1024).decode('utf-8')
                if not data:
                    print(f"\nClient {get_client_info(conn)['nickname']} {addr} disconnected.")
                    break

                # Decode and process the message
                status_line, headers, body = decodeResponse(data)
                if body:
                    payload = json.loads(body)
                    if payload.get("type") == "register":
                        nickname = payload.get("nickname")
                        udp_port = payload.get("udp_port")
                        update_client_info(conn, nickname, udp_port)
                        print(f"Client registered: {nickname}, UDP Port: {udp_port}")

                        # Send register_ackCASP to the newly registered client
                        user_list = [
                            (client["nickname"], client["addr"][0], client["udp_port"])
                            for client in client_data.values()
                        ]
                        register_ack_message = register_ackCASP(user_list)
                        message_to_tcp(conn, register_ack_message)

                        # Send update_addCASP to all other clients except the newly registered one
                        update_add_message = update_addCASP(nickname, addr[0], udp_port)
                        broadcast(update_add_message, exclude_conn=conn)
                    elif payload.get("type") == "unregister":
                        nickname = payload.get("nickname")
                        udp_port = payload.get("udp_port")

                        # Send unregister_ackCASP to the unregistering client
                        unregister_ack_message = unregister_ackCASP()
                        message_to_tcp(conn, unregister_ack_message)
                        remove_client_info(conn)

                        # Send update_removeCASP to all other clients
                        update_remove_message = update_removeCASP(nickname, addr[0], server_ip)
                        broadcast(update_remove_message, exclude_conn=conn)

                        print(f"Client unregistered: {nickname}, UDP Port: {udp_port}")
                        break
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error processing data from {addr}: {e}")
                break
    finally:
        remove_client_info(conn)
        conn.close()

def print_connected_clients():
    """Periodically prints the list of connected clients."""
    global StopFlag
    while not StopFlag:
        time.sleep(10)  # Wait for 10 seconds
        with clients_lock:
            print("\nConnected clients:")
            for client in client_data.values():
                print(f"Nickname: {client['nickname']}, IP: {client['addr'][0]}, UDP Port: {client['udp_port']}")

def message_to_tcp(tcp_sock, message):
    """Sends a message to the server."""
    try:
        if tcp_sock:
            tcp_sock.send(message.encode('utf-8'))
            #print("\nMessage sent to server:", message)
        else:
            print("\nNo active connection to the server.")
    except Exception as e:
        print("\nError communicating with server:", e)

def tcp_sock_from_ip_port(ip, port):
    """Finds the socket from the IP and port."""
    with clients_lock:
        for client in client_data.values():
            if client["addr"][0] == ip and client["addr"][1] == port:
                return client["conn"]
    return None

def disconnect_client(client_ip, udp_port):
    """Disconnects a client from the server."""
    with clients_lock:
        for client in client_data.values():
            if client["addr"][0] == client_ip and client["udp_port"] == udp_port:
                client["conn"].close()
                remove_client_info(client["conn"])
                print(f"Client {client['addr']} disconnected.")
                break

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
        return status_line, headers, body
    except Exception as e:
        print(f"Error decoding response: {e}")
        return None, None, None

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

def update_removeCASP(nickname, client_ip, server_ip):
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

def broadcastMessageCASP(client_ip, from_client, message):
    # JSON-Body erstellen
    body = {
        "type": "broadcast",
        "from": from_client,
        "to": "all",
        "message": message
    }
    json_body = json.dumps(body)
    content_length = len(json_body)

    # CASP-Nachricht aufbauen
    request = (
        f"BROADCAST CACP/1.0\r\n"
        f"Host: {client_ip}\r\n"
        f"Content-Length: {content_length}\r\n"
        f"\r\n"
        f"{json_body}"
    )

    return request

def messageHandler(body):
    try:
        payload = json.loads(body)
        message_type = payload.get("type", "")
        if message_type == "register":
            nickname = payload.get("nickname")
            client_ip = payload.get("ip")
            udp_port = payload.get("udp_port")
            if nickname and client_ip and udp_port:
                with clients_lock:
                    for client in client_data.values():
                        # Match the client using the address (IP and port)
                        if client["addr"][0] == client_ip and client["addr"][1] == 0:
                            client["nickname"] = nickname
                            client["udp_port"] = udp_port
                            print(f"Client {nickname} registered with IP {client_ip} and UDP port {udp_port}")
                            break
                responseClient = register_ackCASP(client_data.values())
                conn = tcp_sock_from_ip_port(client_ip, udp_port)
                message_to_tcp(conn, responseClient)
                responseOther = update_addCASP(nickname, client_ip, udp_port)
                broadcast(responseOther)
        elif message_type == "unregister":
            nickname = payload.get("nickname")
            client_ip = payload.get("ip")
            udp_port = payload.get("udp_port")
            if nickname and client_ip:
                remove_client_info((client_ip, udp_port))
                print(f"User {nickname} unregistered with IP {client_ip}")
                responseClient = unregister_ackCASP()
                conn = tcp_sock_from_ip_port(client_ip, udp_port)
                message_to_tcp(conn, responseClient)
                responseOther = update_removeCASP(nickname, client_ip, server_ip)
                broadcast(responseOther)
        elif message_type == "broadcast":
            message_content = payload.get("message")
            if message_content:
                print(f"Broadcast message: {message_content}")
                responseClient = broatcast_ackCASP()
                conn = tcp_sock_from_ip_port(payload.get("ip"), payload.get("udp_port"))
                message_to_tcp(conn, responseClient)
                responseOther = broadcastMessageCASP(payload.get("ip"), payload.get("nickname"), message_content)
                broadcast(responseOther)
        else:
            print(f"Unknown message type: {body}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")

if __name__ == "__main__":
    tui()