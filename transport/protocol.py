import socket
import threading
import time
import random
from typing import Callable, Dict, Tuple
from .packet import (
    TransportHeader, serialize_packet, deserialize_packet, verify_checksum,
    FLAG_SYN, FLAG_ACK, FLAG_FIN
)
from .connection import Connection, ConnectionState

"""
Part 2 – Connection Management and API Stub
Implements the connection state machine, 3-way handshake (SYN/SYN-ACK/ACK),
and application-facing API functions (connect, send_msg, on_message, close).
This module bridges Part 1 (UDP + packets) with Parts 3 and 4 (receiver/sender).
"""

class TransportProtocol:
    # The main class implementing the Transport API. 
    # This class owns the UDP socket, manages all connections, and routes incoming packets.
    def __init__(self, local_port: int):
        self.local_port = local_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running = False
        self.listen_thread = None
        
        # Maps (ip, port) -> Connection object
        self.connections: Dict[Tuple[str, int], Connection] = {}
        
        # Server-side: Callback for when a new client connects
        self.on_new_connection: Callable[[Connection], None] = None

    def start(self):
        # Binds the socket and starts the listener thread
        try:
            self.sock.bind(('', self.local_port))
            print(f"Socket bound to port {self.local_port}")
        except OSError as e:
            print(f"Failed to bind socket: {e}")
            return
            
        self.running = True
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        print("Protocol listener started.")

    def stop(self):
        # Stops the listener thread and closes the socket
        self.running = False
        self.sock.close()  # This will cause recvfrom to raise an exception
        if self.listen_thread:
            self.listen_thread.join()
        print("Protocol listener stopped.")

    def _listen_loop(self):
        # Main packet processing loop. Runs in its own thread
        while self.running:
            try:
                # 1. Read from the wire
                data, sender_addr = self.sock.recvfrom(2048)
                
                # 2. Deserialize (Part 1)
                header, payload = deserialize_packet(data)
                if not header:
                    print(f"Dropping malformed packet from {sender_addr}")
                    continue
                
                # 3. Checksum (Part 1)
                if not verify_checksum(data):
                    print(f"Dropping corrupt packet from {sender_addr}")
                    continue
                
                # 4. Route the packet based on state
                if sender_addr in self.connections:
                    conn = self.connections[sender_addr]
                    conn.update_activity()
                    
                    # Route to existing connection
                    if conn.state == ConnectionState.SYN_SENT and \
                       header.flags & (FLAG_SYN | FLAG_ACK):
                        # Client: This is the SYN-ACK
                        self._handle_syn_ack(conn, header)
                    elif conn.state == ConnectionState.SYN_RECV and \
                         header.flags & FLAG_ACK:
                        # Server: This is the final ACK of handshake
                        self._handle_handshake_ack(conn, header)
                    else:
                        # Established connection: route to sender/receiver
                        self._route_packet(conn, header, payload)
                        
                elif header.flags & FLAG_SYN:
                    # Server: This is a new connection request
                    self._handle_new_syn(header, sender_addr)
                    
                else:
                    print(f"Dropping packet from unknown source: {sender_addr}")

            except socket.error:
                # This happens when self.sock.close() is called
                if self.running:
                    print("Socket error in listener.")
                break
        print("Listen loop exiting.")

    def _route_packet(self, conn: Connection, header: TransportHeader, payload: bytes):
        # Routes a packet for an established connection
        
        # 1. Route to Sender (Part 4)
        if header.flags & FLAG_ACK:
            # Handle ACK for our FIN
            if conn.state == ConnectionState.FIN_WAIT:
                print(f"[Conn {conn.conn_id}] Received FIN-ACK. Closing.")
                conn.state = ConnectionState.CLOSED
                self._cleanup_connection(conn)
                return
            
            conn.sender.process_incoming_ack(header)

        # 2. Route to Receiver (Part 3)
        if payload:
            conn.receiver.process_data_packet(header, payload)
        
        # 3. Handle FIN from peer
        if header.flags & FLAG_FIN:
            self._handle_fin(conn, header)

    # Handshake Logic

    def _handle_new_syn(self, header: TransportHeader, sender_addr: Tuple[str, int]):
        # Server-side: Handles a new SYN packet
        if not self.on_new_connection:
            print("Server not configured to accept new connections. Dropping SYN.")
            return

        print(f"New SYN received from {sender_addr}")
        conn_id = random.randint(1, 0xFFFFFFFF)
        conn = Connection(self, conn_id, sender_addr, ConnectionState.SYN_RECV)
        self.connections[sender_addr] = conn
        
        # Send SYN-ACK
        syn_ack_header = TransportHeader(
            flags=FLAG_SYN | FLAG_ACK,
            conn_id=conn_id,
            ack=header.seq + 1,  # Acknowledge the SYN
            rwnd=conn.receiver.rwnd
        )
        self._send_raw_packet(syn_ack_header, b"")
        print(f"[Conn {conn_id}] Sent SYN-ACK.")

    def _handle_syn_ack(self, conn: Connection, header: TransportHeader):
        # Client-side: Handles a SYN-ACK packet
        print(f"[Conn {conn.conn_id}] Received SYN-ACK. Connection ESTABLISHED.")
        conn.state = ConnectionState.ESTABLISHED
        conn.conn_id = header.conn_id # Set the official connection ID
        
        # Send final ACK of 3-way handshake
        ack_header = TransportHeader(
            flags=FLAG_ACK,
            conn_id=conn.conn_id,
            ack=header.seq + 1
        )
        self._send_raw_packet(ack_header, b"")

    def _handle_handshake_ack(self, conn: Connection, header: TransportHeader):
        # Server-side: Handles final ACK of 3-way handshake
        print(f"[Conn {conn.conn_id}] Received final ACK. Connection ESTABLISHED.")
        conn.state = ConnectionState.ESTABLISHED
        
        # Notify the server application
        if self.on_new_connection:
            self.on_new_connection(conn)

    # Teardown Logic 

    def _handle_fin(self, conn: Connection, header: TransportHeader):
       # Handles a FIN packet from the peer
        print(f"[Conn {conn.conn_id}] Received FIN.")
        
        # Send FIN-ACK
        fin_ack_header = TransportHeader(
            flags=FLAG_ACK | FLAG_FIN,
            conn_id=conn.conn_id,
            ack=header.seq + 1
        )
        self._send_raw_packet(fin_ack_header, b"")
        conn.state = ConnectionState.CLOSED
        
        if conn.on_disconnect_callback:
            conn.on_disconnect_callback(conn)
        
        self._cleanup_connection(conn)

    def _cleanup_connection(self, conn: Connection):
        # Removes a connection from the active map
        if conn.peer_address in self.connections:
            del self.connections[conn.peer_address]
            print(f"[Conn {conn.conn_id}] Connection cleaned up.")

    # Internal Send Function
    
    def _send_raw_packet(self, header: TransportHeader, payload: bytes):
        # (Internal) Serializes and sends a packet 
        # This is called by the stubs (Parts 3 & 4)
        try:
            packet = serialize_packet(header, payload)
            self.sock.sendto(packet, header.conn_id.peer_address)
        except Exception as e:
            print(f"Error sending packet: {e}")

    # Public API 

    def connect(self, server_addr: Tuple[str, int], timeout=5.0) -> Connection:
        # API Connects to a server. This is a blocking call
        print(f"Attempting to connect to {server_addr}...")
        
        # 1. Create a local Connection object
        conn = Connection(self, 0, server_addr, ConnectionState.SYN_SENT)
        self.connections[server_addr] = conn
        
        # 2. Send SYN packet
        syn_header = TransportHeader(flags=FLAG_SYN)
        self._send_raw_packet(syn_header, b"")
        
        # 3. Wait for state to change to ESTABLISHED (or timeout)
        start_time = time.time()
        while time.time() - start_time < timeout:
            if conn.state == ConnectionState.ESTABLISHED:
                return conn
            time.sleep(0.01) # Poll
            
        # 4. If we get here, it timed out
        print("Connection timed out.")
        self._cleanup_connection(conn)
        raise TimeoutError("Connection timed out")

    def send_msg(self, conn: Connection, data: bytes):
        # API sends a message over a connection.
        if conn.state != ConnectionState.ESTABLISHED:
            raise Exception("Connection not established.")
        
        # Delegate to Part 4 (Sender)
        conn.sender.queue_data_for_sending(data)

    def on_message(self, conn: Connection, callback: Callable[[bytes], None]):
        # API registers a callback to run when a message is received
        conn.on_message_callback = callback

    def on_disconnect(self, conn: Connection, callback: Callable[[Connection], None]):
        # API registers a callback to run when a peer disconnects
        conn.on_disconnect_callback = callback

    def close(self, conn: Connection):
        # (API) Initiates a graceful shutdown of the connection 
        if conn.state == ConnectionState.CLOSED:
            return
        
        print(f"[Conn {conn.conn_id}] Sending FIN.")
        conn.state = ConnectionState.FIN_WAIT
        
        fin_header = TransportHeader(
            flags=FLAG_FIN,
            conn_id=conn.conn_id
        )
        self._send_raw_packet(fin_header, b"")
