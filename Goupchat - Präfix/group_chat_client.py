#!/usr/bin/env python3
"""
Server-basierter Peer-to-Peer Group Chat - Client
Prof. Dr. Dirk Staehle - HTWG Konstanz
"""

import socket
import threading
import json
import time
import random
from typing import Dict, List

class GroupChatClient:
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
        
    def start(self, server_host='localhost', server_port=8888):
        """Client starten"""
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
        """UDP Socket für Peer-Kommunikation einrichten"""
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Port automatisch wählen
        self.udp_socket.bind(('', 0))
        self.udp_port = self.udp_socket.getsockname()[1]
        print(f"UDP Socket auf Port {self.udp_port}")
    
    def setup_tcp_chat_socket(self):
        """TCP Socket für Chat-Sessions einrichten"""
        self.tcp_chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_chat_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_chat_socket.bind(('', 0))
        self.tcp_port = self.tcp_chat_socket.getsockname()[1]
        self.tcp_chat_socket.listen(5)
        print(f"TCP Chat Socket auf Port {self.tcp_port}")
    
    def connect_to_server(self, host, port):
        """Mit Server verbinden"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.connect((host, port))
        print(f"Mit Server verbunden: {host}:{port}")
    
    def register_with_server(self):
        """Bei Server registrieren"""
        # Eigene IP-Adresse ermitteln
        my_ip = self.server_socket.getsockname()[0]
        
        register_msg = {
            'type': 'REGISTER',
            'nickname': self.nickname,
            'ip': my_ip,
            'udp_port': self.udp_port
        }
        
        self.send_to_server(register_msg)
    
    def send_to_server(self, message):
        """Nachricht an Server senden"""
        try:
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')
            length_prefix = len(message_bytes).to_bytes(4, byteorder='big')
            self.server_socket.send(length_prefix + message_bytes)
            return True
        except Exception as e:
            print(f"Fehler beim Senden an Server: {e}")
            return False
    
    def receive_from_server(self):
        """Nachricht vom Server empfangen"""
        try:
            # Länge lesen
            length_data = b''
            while len(length_data) < 4:
                chunk = self.server_socket.recv(4 - len(length_data))
                if not chunk:
                    return None
                length_data += chunk
            
            message_length = int.from_bytes(length_data, byteorder='big')
            
            # Nachricht lesen
            message_data = b''
            while len(message_data) < message_length:
                chunk = self.server_socket.recv(message_length - len(message_data))
                if not chunk:
                    return None
                message_data += chunk
            
            return json.loads(message_data.decode('utf-8'))
        except Exception:
            return None
    
    def handle_server_messages(self):
        """Server-Nachrichten verarbeiten"""
        while self.running:
            try:
                message = self.receive_from_server()
                if not message:
                    break
                
                msg_type = message.get('type')
                
                if msg_type == 'REGISTER_OK':
                    print(f"✓ {message.get('message')}")
                elif msg_type == 'USER_LIST':
                    self.update_peer_list(message.get('users', []))
                elif msg_type == 'USER_JOINED':
                    self.handle_user_joined(message)
                elif msg_type == 'USER_LEFT':
                    self.handle_user_left(message)
                elif msg_type == 'BROADCAST_MSG':
                    self.handle_broadcast_message(message)
                elif msg_type == 'ERROR':
                    print(f"Server-Fehler: {message.get('message')}")
                elif msg_type == 'BROADCAST_OK':
                    print("✓ Broadcast gesendet")
                    
            except Exception as e:
                if self.running:
                    print(f"Fehler bei Server-Kommunikation: {e}")
                break
    
    def update_peer_list(self, users):
        """Peer-Liste aktualisieren"""
        self.peer_list = {}
        for user in users:
            self.peer_list[user['nickname']] = {
                'ip': user['ip'],
                'udp_port': user['udp_port']
            }
        print(f"Aktuelle Benutzer: {list(self.peer_list.keys())}")
    
    def handle_user_joined(self, message):
        """Neuen Benutzer zur Liste hinzufügen"""
        nickname = message.get('nickname')
        self.peer_list[nickname] = {
            'ip': message.get('ip'),
            'udp_port': message.get('udp_port')
        }
        print(f"→ {nickname} ist beigetreten")
    
    def handle_user_left(self, message):
        """Benutzer aus Liste entfernen"""
        nickname = message.get('nickname')
        if nickname in self.peer_list:
            del self.peer_list[nickname]
        if nickname in self.active_chats:
            self.active_chats[nickname].close()
            del self.active_chats[nickname]
        print(f"← {nickname} hat den Chat verlassen")
    
    def handle_broadcast_message(self, message):
        """Broadcast-Nachricht anzeigen"""
        sender = message.get('sender')
        msg = message.get('message')
        print(f"[BROADCAST] {sender}: {msg}")
    
    def handle_udp_messages(self):
        """UDP-Nachrichten verarbeiten"""
        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(1024)
                message = json.loads(data.decode('utf-8'))
                
                if message.get('type') == 'CHAT_REQUEST':
                    self.handle_chat_request(message, addr)
                    
            except Exception as e:
                if self.running:
                    print(f"UDP-Fehler: {e}")
    
    def handle_chat_request(self, message, addr):
        """Chat-Anfrage verarbeiten"""
        initiator = message.get('initiator')
        tcp_port = message.get('tcp_port')
        
        print(f"Chat-Anfrage von {initiator} erhalten")
        
        # TCP-Verbindung zum Initiator aufbauen
        try:
            chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            chat_socket.connect((addr[0], tcp_port))
            
            # Identifikation senden
            hello_msg = {
                'type': 'CHAT_HELLO',
                'nickname': self.nickname
            }
            chat_socket.send(json.dumps(hello_msg).encode('utf-8'))
            
            self.active_chats[initiator] = chat_socket
            
            # Chat-Handler in separatem Thread starten
            chat_thread = threading.Thread(
                target=self.handle_peer_chat,
                args=(chat_socket, initiator)
            )
            chat_thread.daemon = True
            chat_thread.start()
            
            print(f"Chat mit {initiator} erfolgreich gestartet")
            
        except Exception as e:
            print(f"Fehler beim Verbinden mit {initiator}: {e}")
    
    def tcp_chat_server(self):
        """TCP Chat Server für eingehende Verbindungen"""
        while self.running:
            try:
                client_socket, client_addr = self.tcp_chat_socket.accept()
                
                # Warten auf Identifikation
                try:
                    data = client_socket.recv(1024)
                    message = json.loads(data.decode('utf-8'))
                    
                    if message.get('type') == 'CHAT_HELLO':
                        peer_nickname = message.get('nickname')
                        self.active_chats[peer_nickname] = client_socket
                        
                        # Chat-Handler starten
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
        """Peer-zu-Peer Chat verwalten"""
        try:
            while self.running:
                data = chat_socket.recv(1024)
                if not data:
                    break
                
                message = json.loads(data.decode('utf-8'))
                if message.get('type') == 'CHAT_MSG':
                    msg_text = message.get('message')
                    print(f"[{peer_nickname}]: {msg_text}")
                    
        except Exception as e:
            print(f"Chat-Fehler mit {peer_nickname}: {e}")
        finally:
            if peer_nickname in self.active_chats:
                del self.active_chats[peer_nickname]
            chat_socket.close()
            print(f"Chat mit {peer_nickname} beendet")
    
    def start_chat_with_peer(self, peer_nickname):
        """Chat mit Peer initiieren"""
        if peer_nickname not in self.peer_list:
            print(f"Benutzer {peer_nickname} nicht gefunden")
            return
        
        if peer_nickname in self.active_chats:
            print(f"Chat mit {peer_nickname} bereits aktiv")
            return
        
        peer_info = self.peer_list[peer_nickname]
        
        # UDP-Nachricht mit TCP-Port senden
        chat_request = {
            'type': 'CHAT_REQUEST',
            'initiator': self.nickname,
            'tcp_port': self.tcp_port
        }
        
        try:
            self.udp_socket.sendto(
                json.dumps(chat_request).encode('utf-8'),
                (peer_info['ip'], peer_info['udp_port'])
            )
            print(f"Chat-Anfrage an {peer_nickname} gesendet - warte auf Verbindung...")
        except Exception as e:
            print(f"Fehler beim Senden der Chat-Anfrage: {e}")
    
    def send_chat_message(self, peer_nickname, message):
        """Chat-Nachricht an Peer senden"""
        if peer_nickname not in self.active_chats:
            print(f"Kein aktiver Chat mit {peer_nickname}")
            return
        
        chat_msg = {
            'type': 'CHAT_MSG',
            'message': message
        }
        
        try:
            self.active_chats[peer_nickname].send(
                json.dumps(chat_msg).encode('utf-8')
            )
        except Exception as e:
            print(f"Fehler beim Senden an {peer_nickname}: {e}")
    
    def broadcast_message(self, message):
        """Broadcast-Nachricht über Server senden"""
        broadcast_msg = {
            'type': 'BROADCAST',
            'message': message
        }
        self.send_to_server(broadcast_msg)
    
    def main_loop(self):
        """Hauptschleife für Benutzereingaben"""
        print("\n=== Group Chat gestartet ===")
        print("Befehle:")
        print("  /users        - Benutzer auflisten")
        print("  /chat <nick>  - Chat mit Benutzer starten")
        print("  /msg <nick> <text> - Nachricht an Benutzer")
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
        """Befehl verarbeiten"""
        parts = command.split(' ', 2)
        cmd = parts[0].lower()
        
        if cmd == '/quit':
            self.running = False
        elif cmd == '/users':
            print(f"Aktuelle Benutzer: {list(self.peer_list.keys())}")
        elif cmd == '/chat' and len(parts) > 1:
            self.start_chat_with_peer(parts[1])
        elif cmd == '/msg' and len(parts) > 2:
            self.send_chat_message(parts[1], parts[2])
        elif cmd == '/broadcast' and len(parts) > 1:
            self.broadcast_message(' '.join(parts[1:]))
        else:
            print("Unbekannter Befehl")
    
    def stop(self):
        """Client beenden"""
        self.running = False
        
        # Bei Server abmelden
        if self.server_socket:
            try:
                unregister_msg = {'type': 'UNREGISTER'}
                self.send_to_server(unregister_msg)
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
        
        # Chat-Verbindungen schließen
        for chat_socket in self.active_chats.values():
            try:
                chat_socket.close()
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