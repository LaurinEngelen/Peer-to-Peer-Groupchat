"""
Client (Header-Based Protocol für P2P)

Protokollstruktur:                 |     Beispiel-Nachricht:
-----------------------------------|---------------------------------------------------
MESSAGE_TYPE PROTOCOL_VERSION      |     REGISTER 1.0\r\n               <- Pflicht
Header-Key: Header-Value           |     Host: 192.168.1.100\r\n
Header-Key: Header-Value           |     Content-Length: 67\r\n         <- Pflicht
...                                |     \r\n\r\n
[Leerzeile]                        |     {"nickname": "Laurin", "ip": "192.168.1.100", "udp_port": 12345}
[JSON-BODY]

MESSAGE_TYPE Client->Server: REGISTER, UNREGISTER, BROADCAST
MESSAGE_TYPE Server->Client: REGISTER_OK, USER_LIST, USER_JOINED, USER_LEFT, BROADCAST_MSG, BROADCAST_OK, ERROR
MESSAGE_TYPE Peer-to-Peer UDP: CHAT_REQUEST, CHAT_RESPONSE
MESSAGE_TYPE Peer-to-Peer TCP: CHAT_HELLO, CHAT_MSG, CHAT_CLOSE

HEADER-KEY: Host, From, To, Request-ID, Content-Length, Timestamp
"""

import socket
import threading
import json
import time
import random
from typing import Dict, List

class GroupChatClient:
    PROTOCOL_VERSION = "1.0"
    
    def __init__(self):
        self.nickname = ""
        self.server_socket = None
        self.udp_socket = None
        self.tcp_chat_socket = None
        self.udp_port = 0
        self.tcp_port = 0
        self.peer_list = {}  # {nickname: {ip, udp_port}}
        self.active_chats = {}  # {nickname: socket}
        self.running = False
        self.my_ip = ""
        
    def start(self, server_host='localhost', server_port=8888):
        try:
            # Nickname eingeben
            self.nickname = input("Nickname eingeben: ").strip()
            if not self.nickname:
                print("Ungültiger Nickname")
                return
            
            # UDP Socket für Peer-Kommunikation erstellen
            self.setup_udp_socket()
            
            # TCP Socket für Chat-Sessions erstellen
            self.setup_tcp_chat_socket()
            
            # Mit Server verbinden
            self.connect_to_server(server_host, server_port)
            
            # Bei Server registrieren
            self.register_with_server()
            
            self.running = True
            
            # Server-Nachrichten in separatem Thread empfangen
            server_thread = threading.Thread(target=self.handle_server_messages)
            server_thread.daemon = True
            server_thread.start()
            
            # UDP-Nachrichten in separatem Thread empfangen
            udp_thread = threading.Thread(target=self.handle_udp_messages)
            udp_thread.daemon = True
            udp_thread.start()
            
            # TCP Chat Server in separatem Thread
            tcp_server_thread = threading.Thread(target=self.tcp_chat_server)
            tcp_server_thread.daemon = True
            tcp_server_thread.start()
            
            # Hauptschleife für Benutzereingaben
            self.main_loop()
            
        except Exception as e:
            print(f"Client-Fehler: {e}")
        finally:
            self.stop()
    
    def setup_udp_socket(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Port automatisch wählen
        self.udp_socket.bind(('', 0))
        self.udp_port = self.udp_socket.getsockname()[1]
        print(f"UDP Socket auf Port {self.udp_port}")
    
    def setup_tcp_chat_socket(self):
        self.tcp_chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_chat_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_chat_socket.bind(('', 0))
        self.tcp_port = self.tcp_chat_socket.getsockname()[1]
        self.tcp_chat_socket.listen(5)
        print(f"TCP Chat Socket auf Port {self.tcp_port}")
    
    def connect_to_server(self, host, port):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.connect((host, port))
        self.my_ip = self.server_socket.getsockname()[0]
        print(f"Mit Server verbunden: {host}:{port}")
    
    def register_with_server(self):
        register_data = {
            'nickname': self.nickname,
            'ip': self.my_ip,
            'udp_port': self.udp_port
        }
        
        self.send_to_server('REGISTER', register_data)
    
    def send_to_server(self, message_type, json_data=None, additional_headers=None):
        try:
            body = ""
            if json_data:
                body = json.dumps(json_data)

            headers = []
            headers.append(f"{message_type} {self.PROTOCOL_VERSION}")
            headers.append(f"Host: {self.my_ip}")
            headers.append(f"Content-Length: {len(body.encode('utf-8'))}")

            if additional_headers:
                for key, value in additional_headers.items():
                    headers.append(f"{key}: {value}")

            message = "\r\n".join(headers) + "\r\n\r\n" + body
            
            self.server_socket.send(message.encode('utf-8'))
            return True
        except Exception as e:
            print(f"Fehler beim Senden an Server: {e}")
            return False
    
    def receive_from_server(self):
        try:
            header_lines = []
            current_line = b''
            
            while True:
                char = self.server_socket.recv(1)
                if not char:
                    return None, None, None
                
                if char == b'\n': # Bytestring endet mit \n
                    line = current_line.decode('utf-8').rstrip('\r')
                    if not line:  # Leere Zeile = Ende der Header
                        break
                    header_lines.append(line)
                    current_line = b''
                else:
                    current_line += char
            
            if not header_lines:
                return None, None, None
            
            # Erste Zeile parsen: MESSAGE_TYPE PROTOCOL_VERSION
            first_line = header_lines[0].split()
            if len(first_line) != 2:
                return None, None, None
            
            message_type = first_line[0]
            protocol_version = first_line[1]
            
            # Header parsen
            headers = {}
            for line in header_lines[1:]:
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            # Body lesen falls Content-Length vorhanden
            body = ""
            if 'Content-Length' in headers:
                content_length = int(headers['Content-Length'])
                if content_length > 0:
                    body_data = b''
                    while len(body_data) < content_length:
                        chunk = self.server_socket.recv(content_length - len(body_data))
                        if not chunk:
                            return None, None, None
                        body_data += chunk
                    body = body_data.decode('utf-8')
            
            return message_type, headers, body
            
        except Exception:
            return None, None, None
    
    def send_udp_header_message(self, message_type, json_data, target_ip, target_port, additional_headers=None):
        try:
            body = json.dumps(json_data) if json_data else ""

            headers = []
            headers.append(f"{message_type} {self.PROTOCOL_VERSION}")
            headers.append(f"From: {self.nickname}")
            headers.append(f"Host: {self.my_ip}")
            headers.append(f"Content-Length: {len(body.encode('utf-8'))}")

            if additional_headers:
                for key, value in additional_headers.items():
                    headers.append(f"{key}: {value}")

            message = "\r\n".join(headers) + "\r\n\r\n" + body
            
            self.udp_socket.sendto(message.encode('utf-8'), (target_ip, target_port))
            return True
        except Exception as e:
            print(f"Fehler beim UDP-Senden: {e}")
            return False
    
    def parse_udp_header_message(self, data):
        try:
            message_str = data.decode('utf-8')

            if '\r\n\r\n' not in message_str:
                return None, None, None
            
            header_part, body = message_str.split('\r\n\r\n', 1)
            header_lines = header_part.split('\r\n')
            
            if not header_lines:
                return None, None, None

            first_line = header_lines[0].split()
            if len(first_line) != 2:
                return None, None, None
            
            message_type = first_line[0]
            protocol_version = first_line[1]

            headers = {}
            for line in header_lines[1:]:
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            return message_type, headers, body
            
        except Exception as e:
            print(f"Fehler beim UDP-Parsen: {e}")
            return None, None, None
    
    def send_tcp_header_message(self, socket_obj, message_type, json_data=None, additional_headers=None):
        try:
            body = json.dumps(json_data) if json_data else ""

            headers = []
            headers.append(f"{message_type} {self.PROTOCOL_VERSION}")
            headers.append(f"From: {self.nickname}")
            headers.append(f"Host: {self.my_ip}")
            headers.append(f"Content-Length: {len(body.encode('utf-8'))}")

            if additional_headers:
                for key, value in additional_headers.items():
                    headers.append(f"{key}: {value}")

            message = "\r\n".join(headers) + "\r\n\r\n" + body
            
            socket_obj.send(message.encode('utf-8'))
            return True
        except Exception as e:
            print(f"Fehler beim TCP-Senden: {e}")
            return False
    
    def receive_tcp_header_message(self, socket_obj):
        try:
            header_lines = []
            current_line = b''
            
            while True:
                char = socket_obj.recv(1)
                if not char:
                    return None, None, None
                
                if char == b'\n':
                    line = current_line.decode('utf-8').rstrip('\r')
                    if not line:  # Leere Zeile = Ende der Header
                        break
                    header_lines.append(line)
                    current_line = b''
                else:
                    current_line += char
            
            if not header_lines:
                return None, None, None

            first_line = header_lines[0].split()
            if len(first_line) != 2:
                return None, None, None
            
            message_type = first_line[0]
            protocol_version = first_line[1]

            headers = {}
            for line in header_lines[1:]:
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()

            body = ""
            if 'Content-Length' in headers:
                content_length = int(headers['Content-Length'])
                if content_length > 0:
                    body_data = b''
                    while len(body_data) < content_length:
                        chunk = socket_obj.recv(content_length - len(body_data))
                        if not chunk:
                            return None, None, None
                        body_data += chunk
                    body = body_data.decode('utf-8')
            
            return message_type, headers, body
            
        except Exception:
            return None, None, None
    
    def handle_server_messages(self):
        while self.running:
            try:
                message_type, headers, body = self.receive_from_server()
                if not message_type:
                    break

                json_data = json.loads(body) if body else {}
                
                if message_type == 'REGISTER_OK':
                    print(f"✓ {json_data.get('message')}")
                elif message_type == 'USER_LIST':
                    self.update_peer_list(json_data.get('users', []))
                elif message_type == 'USER_JOINED':
                    self.handle_user_joined(json_data)
                elif message_type == 'USER_LEFT':
                    self.handle_user_left(json_data)
                elif message_type == 'BROADCAST_MSG':
                    self.handle_broadcast_message(json_data)
                elif message_type == 'ERROR':
                    print(f"Server-Fehler: {json_data.get('message')}")
                elif message_type == 'BROADCAST_OK':
                    print("✓ Broadcast gesendet")
                    
            except Exception as e:
                if self.running:
                    print(f"Fehler bei Server-Kommunikation: {e}")
                break
    
    def update_peer_list(self, users):
        self.peer_list = {}
        for user in users:
            self.peer_list[user['nickname']] = {
                'ip': user['ip'],
                'udp_port': user['udp_port']
            }
        print(f"Aktuelle Benutzer: {list(self.peer_list.keys())}")
    
    def handle_user_joined(self, json_data):
        nickname = json_data.get('nickname')
        self.peer_list[nickname] = {
            'ip': json_data.get('ip'),
            'udp_port': json_data.get('udp_port')
        }
        print(f"→ {nickname} ist beigetreten")
    
    def handle_user_left(self, json_data):
        nickname = json_data.get('nickname')
        if nickname in self.peer_list:
            del self.peer_list[nickname]
        if nickname in self.active_chats:
            self.active_chats[nickname].close()
            del self.active_chats[nickname]
        print(f"← {nickname} hat den Chat verlassen")
    
    def handle_broadcast_message(self, json_data):
        sender = json_data.get('sender')
        msg = json_data.get('message')
        print(f"[BROADCAST] {sender}: {msg}")
    
    def handle_udp_messages(self):
        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(4096)  # Größerer Buffer für Header
                message_type, headers, body = self.parse_udp_header_message(data)
                
                if not message_type:
                    continue

                json_data = json.loads(body) if body else {}
                
                if message_type == 'CHAT_REQUEST':
                    self.handle_chat_request(headers, json_data, addr)
                elif message_type == 'CHAT_RESPONSE':
                    self.handle_chat_response(headers, json_data, addr)
                    
            except Exception as e:
                if self.running:
                    print(f"UDP-Fehler: {e}")
    
    def handle_chat_request(self, headers, json_data, addr):
        initiator = headers.get('From')
        tcp_port = json_data.get('tcp_port')
        
        print(f"Chat-Anfrage von {initiator} erhalten")
        
        # Antwort senden
        response_data = {
            'accepted': True,
            'tcp_port': self.tcp_port
        }
        
        additional_headers = {
            'To': initiator,
            'Request-ID': headers.get('Request-ID', 'unknown')
        }
        
        self.send_udp_header_message(
            'CHAT_RESPONSE',
            response_data,
            addr[0],
            addr[1],
            additional_headers
        )
        
        # TCP-Verbindung zum Initiator aufbauen
        try:
            chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            chat_socket.connect((addr[0], tcp_port))

            hello_data = {
                'nickname': self.nickname
            }
            
            self.send_tcp_header_message(chat_socket, 'CHAT_HELLO', hello_data)
            
            self.active_chats[initiator] = chat_socket

            chat_thread = threading.Thread(
                target=self.handle_peer_chat,
                args=(chat_socket, initiator)
            )
            chat_thread.daemon = True
            chat_thread.start()
            
            print(f"Chat mit {initiator} erfolgreich gestartet")
            
        except Exception as e:
            print(f"Fehler beim Verbinden mit {initiator}: {e}")
    
    def handle_chat_response(self, headers, json_data, addr):
        responder = headers.get('From')
        accepted = json_data.get('accepted', False)
        
        if accepted:
            print(f"Chat-Anfrage von {responder} akzeptiert")
        else:
            print(f"Chat-Anfrage von {responder} abgelehnt")
    
    def tcp_chat_server(self):
        while self.running:
            try:
                client_socket, client_addr = self.tcp_chat_socket.accept()
                
                # Warten auf Identifikation (Header-basiert)
                try:
                    message_type, headers, body = self.receive_tcp_header_message(client_socket)
                    
                    if message_type == 'CHAT_HELLO':
                        json_data = json.loads(body) if body else {}
                        peer_nickname = json_data.get('nickname')
                        
                        if not peer_nickname:
                            peer_nickname = headers.get('From', 'Unknown')
                        
                        self.active_chats[peer_nickname] = client_socket

                        chat_thread = threading.Thread(
                            target=self.handle_peer_chat,
                            args=(client_socket, peer_nickname)
                        )
                        chat_thread.daemon = True
                        chat_thread.start()
                        
                        print(f"Chat mit {peer_nickname} erfolgreich gestartet")
                        
                except Exception as e:
                    print(f"Fehler bei Chat-Identifikation: {e}")
                    client_socket.close()
                    
            except Exception as e:
                if self.running:
                    print(f"TCP Chat Server Fehler: {e}")
    
    def handle_peer_chat(self, chat_socket, peer_nickname):
        try:
            while self.running:
                message_type, headers, body = self.receive_tcp_header_message(chat_socket)
                if not message_type:
                    break
                
                if message_type == 'CHAT_MSG':
                    json_data = json.loads(body) if body else {}
                    msg_text = json_data.get('message')
                    timestamp = headers.get('Timestamp', '')
                    
                    if timestamp:
                        print(f"[{peer_nickname}] ({timestamp}): {msg_text}")
                    else:
                        print(f"[{peer_nickname}]: {msg_text}")
                elif message_type == 'CHAT_CLOSE':
                    print(f"Chat mit {peer_nickname} wurde von der Gegenseite beendet")
                    break
                    
        except Exception as e:
            print(f"Chat-Fehler mit {peer_nickname}: {e}")
        finally:
            if peer_nickname in self.active_chats:
                del self.active_chats[peer_nickname]
            chat_socket.close()
            print(f"Chat mit {peer_nickname} beendet")
    
    def start_chat_with_peer(self, peer_nickname):
        if peer_nickname not in self.peer_list:
            print(f"Benutzer {peer_nickname} nicht gefunden")
            return
        
        if peer_nickname in self.active_chats:
            print(f"Chat mit {peer_nickname} bereits aktiv")
            return
        
        peer_info = self.peer_list[peer_nickname]

        chat_request_data = {
            'tcp_port': self.tcp_port
        }

        request_id = f"{self.nickname}_{int(time.time())}_{random.randint(1000, 9999)}"
        
        additional_headers = {
            'To': peer_nickname,
            'Request-ID': request_id
        }
        
        try:
            self.send_udp_header_message(
                'CHAT_REQUEST',
                chat_request_data,
                peer_info['ip'],
                peer_info['udp_port'],
                additional_headers
            )
            print(f"Chat-Anfrage an {peer_nickname} gesendet - warte auf Verbindung...")
        except Exception as e:
            print(f"Fehler beim Senden der Chat-Anfrage: {e}")
    
    def send_chat_message(self, peer_nickname, message):
        if peer_nickname not in self.active_chats:
            print(f"Kein aktiver Chat mit {peer_nickname}")
            return
        
        chat_msg_data = {
            'message': message
        }
        
        # Timestamp hinzufügen
        additional_headers = {
            'To': peer_nickname,
            'Timestamp': time.strftime('%H:%M:%S')
        }
        
        try:
            self.send_tcp_header_message(
                self.active_chats[peer_nickname],
                'CHAT_MSG',
                chat_msg_data,
                additional_headers
            )
        except Exception as e:
            print(f"Fehler beim Senden an {peer_nickname}: {e}")
    
    def close_chat_with_peer(self, peer_nickname):
        if peer_nickname not in self.active_chats:
            print(f"Kein aktiver Chat mit {peer_nickname}")
            return
        
        try:
            # CHAT_CLOSE Nachricht senden
            additional_headers = {
                'To': peer_nickname
            }
            
            self.send_tcp_header_message(
                self.active_chats[peer_nickname],
                'CHAT_CLOSE',
                None,
                additional_headers
            )

            self.active_chats[peer_nickname].close()
            del self.active_chats[peer_nickname]
            
            print(f"Chat mit {peer_nickname} beendet")
            
        except Exception as e:
            print(f"Fehler beim Beenden des Chats mit {peer_nickname}: {e}")
    
    def broadcast_message(self, message):
        broadcast_data = {
            'message': message
        }
        self.send_to_server('BROADCAST', broadcast_data)
    
    def main_loop(self):
        print("\n=== Group Chat gestartet ===")
        print("Befehle:")
        print("  /users        - Benutzer auflisten")
        print("  /chat <nick>  - Chat mit Benutzer starten")
        print("  /msg <nick> <text> - Nachricht an Benutzer")
        print("  /close <nick> - Chat mit Benutzer beenden")
        print("  /chats        - Aktive Chats anzeigen")
        print("  /broadcast <text> - Broadcast-Nachricht")
        print("  /quit         - Beenden")
        print()
        
        while self.running:
            try:
                user_input = input().strip()
                if not user_input:
                    continue
                
                if user_input.startswith('/'):
                    self.handle_command(user_input)
                else:
                    print("Unbekannter Befehl. Verwende /quit zum Beenden")
                    
            except KeyboardInterrupt:
                break
            except EOFError:
                break
    
    def handle_command(self, command):
        parts = command.split(' ', 2)
        cmd = parts[0].lower()
        
        if cmd == '/quit':
            self.running = False
        elif cmd == '/users':
            print(f"Aktuelle Benutzer: {list(self.peer_list.keys())}")
        elif cmd == '/chats':
            if self.active_chats:
                print(f"Aktive Chats: {list(self.active_chats.keys())}")
            else:
                print("Keine aktiven Chats")
        elif cmd == '/chat' and len(parts) > 1:
            self.start_chat_with_peer(parts[1])
        elif cmd == '/msg' and len(parts) > 2:
            self.send_chat_message(parts[1], parts[2])
        elif cmd == '/close' and len(parts) > 1:
            self.close_chat_with_peer(parts[1])
        elif cmd == '/broadcast' and len(parts) > 1:
            self.broadcast_message(' '.join(parts[1:]))
        else:
            print("Unbekannter Befehl")
    
    def stop(self):
        self.running = False
        
        # Alle aktiven Chats beenden
        for peer_nickname in list(self.active_chats.keys()):
            try:
                self.close_chat_with_peer(peer_nickname)
            except:
                pass
        
        # Bei Server abmelden
        if self.server_socket:
            try:
                self.send_to_server('UNREGISTER')
                time.sleep(0.1)  # Kurz warten
            except:
                pass
        
        # Sockets schließen
        for socket_obj in [self.server_socket, self.udp_socket, self.tcp_chat_socket]:
            if socket_obj:
                try:
                    socket_obj.close()
                except:
                    pass
        
        print("Client beendet")

def main():
    client = GroupChatClient()
    
    # Server-Adresse abfragen
    server_host = input("Server-Host (Enter für localhost): ").strip()
    if not server_host:
        server_host = 'localhost'
    
    server_port = input("Server-Port (Enter für 8888): ").strip()
    if not server_port:
        server_port = 8888
    else:
        server_port = int(server_port)
    
    try:
        client.start(server_host, server_port)
    except KeyboardInterrupt:
        print("\nClient wird beendet...")
    finally:
        client.stop()

if __name__ == "__main__":
    main()