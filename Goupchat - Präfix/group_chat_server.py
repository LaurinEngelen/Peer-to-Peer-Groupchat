#!/usr/bin/env python3
"""
Server-basierter Peer-to-Peer Group Chat - Server
Prof. Dr. Dirk Staehle - HTWG Konstanz
"""

import socket
import threading
import json
import time
from typing import Dict, List, Set

class GroupChatServer:
    def __init__(self, host='localhost', port=8888):
        self.host = host
        self.port = port
        self.clients = {}  # {client_socket: client_info}
        self.client_list = {}  # {nickname: {ip, udp_port, socket}}
        self.server_socket = None
        self.running = False
        
    def start(self):
        """Server starten"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            print(f"Server gestartet auf {self.host}:{self.port}")
            print("Warte auf Client-Verbindungen...")
            
            while self.running:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    print(f"Neue Verbindung von {client_address}")
                    
                    # Neuen Thread für jeden Client starten
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.error as e:
                    if self.running:
                        print(f"Fehler beim Akzeptieren der Verbindung: {e}")
                        
        except Exception as e:
            print(f"Server-Fehler: {e}")
        finally:
            self.stop()
    
    def handle_client(self, client_socket, client_address):
        """Client-Kommunikation verwalten"""
        try:
            while self.running:
                # Nachricht empfangen
                data = self.receive_message(client_socket)
                if not data:
                    break
                
                try:
                    message = json.loads(data)
                    self.process_message(client_socket, message)
                except json.JSONDecodeError:
                    self.send_error(client_socket, "Invalid JSON format")
                except Exception as e:
                    print(f"Fehler bei Nachrichtenverarbeitung: {e}")
                    
        except Exception as e:
            print(f"Client-Handler Fehler: {e}")
        finally:
            self.disconnect_client(client_socket)
    
    def receive_message(self, client_socket):
        """Nachricht aus TCP-Stream empfangen (mit Längenpräfix)"""
        try:
            # Erst die Länge der Nachricht lesen (4 Bytes)
            length_data = b''
            while len(length_data) < 4:
                chunk = client_socket.recv(4 - len(length_data))
                if not chunk:
                    return None
                length_data += chunk
            
            message_length = int.from_bytes(length_data, byteorder='big')
            
            # Dann die eigentliche Nachricht lesen
            message_data = b''
            while len(message_data) < message_length:
                chunk = client_socket.recv(message_length - len(message_data))
                if not chunk:
                    return None
                message_data += chunk
            
            return message_data.decode('utf-8')
        except Exception:
            return None
    
    def send_message(self, client_socket, message):
        """Nachricht an Client senden (mit Längenpräfix)"""
        try:
            message_bytes = message.encode('utf-8')
            length_prefix = len(message_bytes).to_bytes(4, byteorder='big')
            client_socket.send(length_prefix + message_bytes)
            return True
        except Exception as e:
            print(f"Fehler beim Senden: {e}")
            return False
    
    def process_message(self, client_socket, message):
        """Empfangene Nachricht verarbeiten"""
        msg_type = message.get('type')
        
        if msg_type == 'REGISTER':
            self.handle_register(client_socket, message)
        elif msg_type == 'UNREGISTER':
            self.handle_unregister(client_socket)
        elif msg_type == 'BROADCAST':
            self.handle_broadcast(client_socket, message)
        elif msg_type == 'GET_USERS':
            self.handle_get_users(client_socket)
        else:
            self.send_error(client_socket, f"Unknown message type: {msg_type}")
    
    def handle_register(self, client_socket, message):
        """Client-Registrierung verarbeiten"""
        try:
            nickname = message.get('nickname')
            ip = message.get('ip')
            udp_port = message.get('udp_port')
            
            if not nickname or not ip or not udp_port:
                self.send_error(client_socket, "Missing required fields")
                return
            
            if nickname in self.client_list:
                self.send_error(client_socket, "Nickname already exists")
                return
            
            # Client registrieren
            client_info = {
                'nickname': nickname,
                'ip': ip,
                'udp_port': udp_port,
                'socket': client_socket
            }
            
            self.clients[client_socket] = client_info
            self.client_list[nickname] = client_info
            
            # Erfolgreiche Registrierung bestätigen
            response = {
                'type': 'REGISTER_OK',
                'message': f'Successfully registered as {nickname}'
            }
            self.send_message(client_socket, json.dumps(response))
            
            # Aktuelle Benutzerliste senden
            self.send_user_list(client_socket)
            
            # Andere Clients über neuen Benutzer informieren
            self.broadcast_user_update('USER_JOINED', nickname, ip, udp_port, exclude=client_socket)
            
            print(f"Client {nickname} registriert von {ip}:{udp_port}")
            
        except Exception as e:
            self.send_error(client_socket, f"Registration failed: {e}")
    
    def handle_unregister(self, client_socket):
        """Client-Abmeldung verarbeiten"""
        if client_socket in self.clients:
            client_info = self.clients[client_socket]
            nickname = client_info['nickname']
            
            response = {
                'type': 'UNREGISTER_OK',
                'message': f'Successfully unregistered {nickname}'
            }
            self.send_message(client_socket, json.dumps(response))
            
            # Client entfernen
            del self.clients[client_socket]
            del self.client_list[nickname]
            
            # Andere Clients informieren
            self.broadcast_user_update('USER_LEFT', nickname, '', 0, exclude=client_socket)
            
            print(f"Client {nickname} abgemeldet")
    
    def handle_broadcast(self, client_socket, message):
        """Broadcast-Nachricht verarbeiten"""
        if client_socket not in self.clients:
            self.send_error(client_socket, "Not registered")
            return
        
        sender = self.clients[client_socket]['nickname']
        broadcast_message = message.get('message', '')
        
        # Broadcast an alle anderen Clients
        broadcast_data = {
            'type': 'BROADCAST_MSG',
            'sender': sender,
            'message': broadcast_message,
            'timestamp': time.time()
        }
        
        for other_socket, other_info in self.clients.items():
            if other_socket != client_socket:
                self.send_message(other_socket, json.dumps(broadcast_data))
        
        # Bestätigung an Sender
        response = {
            'type': 'BROADCAST_OK',
            'message': 'Message broadcasted'
        }
        self.send_message(client_socket, json.dumps(response))
        
        print(f"Broadcast von {sender}: {broadcast_message}")
    
    def handle_get_users(self, client_socket):
        """Aktuelle Benutzerliste senden"""
        self.send_user_list(client_socket)
    
    def send_user_list(self, client_socket):
        """Benutzerliste an Client senden"""
        user_list = []
        for nickname, info in self.client_list.items():
            if info['socket'] != client_socket:  # Eigenen Client nicht in Liste
                user_list.append({
                    'nickname': nickname,
                    'ip': info['ip'],
                    'udp_port': info['udp_port']
                })
        
        response = {
            'type': 'USER_LIST',
            'users': user_list
        }
        self.send_message(client_socket, json.dumps(response))
    
    def broadcast_user_update(self, update_type, nickname, ip, udp_port, exclude=None):
        """Benutzer-Update an alle Clients senden"""
        update_data = {
            'type': update_type,
            'nickname': nickname,
            'ip': ip,
            'udp_port': udp_port,
            'timestamp': time.time()
        }
        
        for client_socket, client_info in self.clients.items():
            if client_socket != exclude:
                self.send_message(client_socket, json.dumps(update_data))
    
    def send_error(self, client_socket, error_message):
        """Fehlernachricht an Client senden"""
        error_data = {
            'type': 'ERROR',
            'message': error_message
        }
        self.send_message(client_socket, json.dumps(error_data))
    
    def disconnect_client(self, client_socket):
        """Client-Verbindung beenden"""
        if client_socket in self.clients:
            client_info = self.clients[client_socket]
            nickname = client_info['nickname']
            
            del self.clients[client_socket]
            del self.client_list[nickname]
            
            # Andere Clients informieren
            self.broadcast_user_update('USER_LEFT', nickname, '', 0, exclude=client_socket)
            
            print(f"Client {nickname} getrennt")
        
        try:
            client_socket.close()
        except:
            pass
    
    def stop(self):
        """Server beenden"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print("Server beendet")

def main():
    server = GroupChatServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nServer wird beendet...")
        server.stop()

if __name__ == "__main__":
    main()