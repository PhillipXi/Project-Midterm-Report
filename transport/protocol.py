import socket
import threading
import time
import random
from typing import Callable, Dict, Tuple

from .packet import (
    TransportHeader,
    serialize_packet,
    deserialize_packet,
    verify_checksum,
    FLAG_SYN,
    FLAG_ACK,
    FLAG_FIN,
    FLAG_PSH,
)
from .connection import Connection, ConnectionState

class TransportProtocol:
    # The main class implementing the Transport API.
    # This class owns the UDP socket, manages all connections, and routes incoming packets.
    # It orchestrates the handshake, data transfer, and teardown processes.

    def __init__(self, local_port: int):
        self.local_port = local_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running = False
        self.listen_thread = None

        # Maps peer address (ip, port) to the corresponding Connection object
        self.connections: Dict[Tuple[str, int], Connection] = {}

        # Server-side: Callback for when a new client connection is established
        self.on_new_connection: Callable[[Connection], None] = None

    def start(self):
        """Binds the socket and starts the main listener thread."""
        try:
            self.sock.bind(("", self.local_port))
            print(f"Socket bound to port {self.local_port}")
        except OSError as e:
            print(f"Failed to bind socket: {e}")
            return

        self.running = True
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        print("Protocol listener started.")

    def stop(self):
        # Stops the listener thread and closes the socket.
        self.running = False
        # Closing the socket will cause recvfrom to raise an exception, breaking the loop
        self.sock.close()
        if self.listen_thread:
            self.listen_thread.join()
        print("Protocol listener stopped.")

    def _listen_loop(self):
        # Main packet processing loop. Runs in its own thread.
        # This method acts as the central packet router.
        while self.running:
            try:
                # 1. Read from the wire
                raw_data, sender_addr = self.sock.recvfrom(2048)

                # 2. Verify checksum before doing anything else
                if not verify_checksum(raw_data):
                    print(f"Dropping corrupt packet from {sender_addr}")
                    continue

                # 3. Deserialize the packet
                header, payload = deserialize_packet(raw_data)
                if not header:
                    print(f"Dropping malformed packet from {sender_addr}")
                    continue

                # 4. Route the packet based on sender and flags
                conn = self.connections.get(sender_addr)

                if conn:
                    # Existing Connection
                    if conn.state == ConnectionState.SYN_SENT and header.flags == (FLAG_SYN | FLAG_ACK):
                        self._handle_syn_ack(conn, header, sender_addr)
                    elif conn.state == ConnectionState.SYN_RECV and header.flags == FLAG_ACK:
                        self._handle_handshake_ack(conn, header)
                    elif conn.state == ConnectionState.ESTABLISHED:
                        if header.flags & FLAG_FIN:
                            self._handle_fin(conn, header)
                        if header.flags & FLAG_ACK:
                            conn.sender.process_incoming_ack(header)
                        if payload or (header.flags & FLAG_PSH):
                            conn.receiver.process_data_packet(header, payload)
                    # Other states (like FIN_WAIT) are handled implicitly by ACK/FIN checks
                elif header.flags == FLAG_SYN:
                    # New Connection Request 
                    self._handle_new_syn(header, sender_addr)
                else:
                    print(f"Dropping packet from unknown source: {sender_addr}")

            except socket.error:
                # This is expected when self.sock.close() is called in stop()
                if not self.running:
                    break  # Graceful exit
                else:
                    print("Socket error in listener.")
                    break
        print("Listen loop exiting.")

    def _send_raw_packet(self, header: TransportHeader, payload: bytes, dest_addr: Tuple[str, int]):
        # (Internal) Serializes and sends a single packet to a given destination.
        # This is the ONLY place in the class where serialize_packet and sock.sendto are called.
        try:
            packet = serialize_packet(header, payload)
            self.sock.sendto(packet, dest_addr)
        except Exception as e:
            print(f"Error sending packet to {dest_addr}: {e}")

    # Handshake and Teardown Logic 

    def _handle_new_syn(self, header: TransportHeader, sender_addr: Tuple[str, int]):
        # Server-side: Handles a new SYN packet to establish a connection.
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
            seq=conn.sender.seq_num,
            ack=header.seq + 1,
            rwnd=conn.receiver.get_window_size(),
        )
        self._send_raw_packet(syn_ack_header, b"", sender_addr)
        print(f"[Conn {conn_id}] Sent SYN-ACK to {sender_addr}.")

    def _handle_syn_ack(self, conn: Connection, header: TransportHeader, sender_addr: Tuple[str, int]):
        # Client-side: Handles a SYN-ACK packet from the server.
        print(f"[Conn {conn.conn_id}] Received SYN-ACK. Connection ESTABLISHED.")
        conn.state = ConnectionState.ESTABLISHED
        conn.conn_id = header.conn_id  # Set the official connection ID from the server

        # Send the final ACK of the 3-way handshake
        ack_header = TransportHeader(
            flags=FLAG_ACK,
            conn_id=conn.conn_id,
            seq=conn.sender.seq_num,
            ack=header.seq + 1,
            rwnd=conn.receiver.get_window_size(),
        )
        self._send_raw_packet(ack_header, b"", sender_addr)

    def _handle_handshake_ack(self, conn: Connection, header: TransportHeader):
        # Server-side: Handles the final ACK of the 3-way handshake.
        print(f"[Conn {conn.conn_id}] Received final ACK. Connection ESTABLISHED.")
        conn.state = ConnectionState.ESTABLISHED

        # Notify the server application layer that a new client is ready
        if self.on_new_connection:
            self.on_new_connection(conn)

    def _handle_fin(self, conn: Connection, header: TransportHeader):
        # Handles a FIN packet from the peer to initiate teardown.
        print(f"[Conn {conn.conn_id}] Received FIN.")

        # Acknowledge the FIN
        ack_header = TransportHeader(
            flags=FLAG_ACK,
            conn_id=conn.conn_id,
            ack=header.seq + 1,
            rwnd=conn.receiver.get_window_size(),
        )
        self._send_raw_packet(ack_header, b"", conn.peer_address)

        # Notify application and clean up
        if conn.on_disconnect_callback:
            conn.on_disconnect_callback(conn)
        
        self._cleanup_connection(conn)

    def _cleanup_connection(self, conn: Connection):
        # Removes a connection from the active map and marks it as closed.
        conn.state = ConnectionState.CLOSED
        if conn.peer_address in self.connections:
            del self.connections[conn.peer_address]
            print(f"[Conn {conn.conn_id}] Connection cleaned up.")

    # Public API

    def connect(self, server_addr: Tuple[str, int], timeout=5.0) -> Connection:
        # Client-side, blocking. Establishes a connection to a server.
        print(f"Attempting to connect to {server_addr}...")

        # 1. Create a local Connection object in SYN_SENT state
        conn = Connection(self, 0, server_addr, ConnectionState.SYN_SENT)
        self.connections[server_addr] = conn

        # 2. Send SYN packet
        syn_header = TransportHeader(
            flags=FLAG_SYN,
            conn_id=0, # No conn_id yet
            seq=conn.sender.seq_num,
            rwnd=conn.receiver.get_window_size()
        )
        self._send_raw_packet(syn_header, b"", server_addr)

        # 3. Wait for the state to change to ESTABLISHED (or timeout)
        start_time = time.time()
        while time.time() - start_time < timeout:
            if conn.state == ConnectionState.ESTABLISHED:
                return conn
            time.sleep(0.01)  # Poll

        # 4. If we get here, it timed out
        print("Connection timed out.")
        self._cleanup_connection(conn)
        raise TimeoutError("Connection timed out")

    def send_msg(self, conn: Connection, data: bytes):
        # API Queues data to be sent over an established connection.
        if conn.state != ConnectionState.ESTABLISHED:
            raise ConnectionError("Connection not established.")
        conn.sender.queue_data_for_sending(data)

    def on_message(self, conn: Connection, callback: Callable[[Connection, bytes], None]):
        # API Registers a callback to run when a message is fully reassembled.
        conn.on_message_callback = callback

    def on_new_connection(self, callback: Callable[[Connection], None]):
        # Server-side API Registers a callback for newly established connections.
        self.on_new_connection = callback

    def close(self, conn: Connection):
        # API Initiates a graceful shutdown of the connection.
        if conn.state in [ConnectionState.FIN_WAIT, ConnectionState.CLOSED]:
            return

        print(f"[Conn {conn.conn_id}] Sending FIN.")
        conn.state = ConnectionState.FIN_WAIT

        fin_header = TransportHeader(
            flags=FLAG_FIN,
            conn_id=conn.conn_id,
            seq=conn.sender.seq_num,
            rwnd=conn.receiver.get_window_size()
        )
        self._send_raw_packet(fin_header, b"", conn.peer_address)
        # The connection will be fully closed and cleaned up when the FIN-ACK is received.
