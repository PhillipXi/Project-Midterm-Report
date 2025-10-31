# transport/sender.py
import threading
import time
from collections import deque
from packet import (
    TransportHeader,
    FLAG_ACK,
    FLAG_PSH,
    serialize_packet
)

MAX_PAYLOAD_SIZE = 1400      # bytes per packet
RTO_VALUE = 1.0              # Retransmission timeout (seconds)


class SenderLogic:
    """Handles reliable data sending, timers, and ACK processing."""

    def __init__(self, connection):
        self.connection = connection
        self.next_seq = 0                      # Next sequence number to use
        self.base_seq = 0                      # Oldest un-ACKed packet
        self.send_buffer = deque()             # Queue of payloads waiting to send
        self.unacked_packets = {}              # seq -> (packet, timer)
        self.lock = threading.Lock()
        self.advertised_window = 4096          # Updated by receiver ACKs

    # ----------------------------------------------------
    #  Called by Part 2 send_msg()
    # ----------------------------------------------------
    def queue_data_for_sending(self, data: bytes):
        """Break large data into chunks and queue them for sending."""
        for i in range(0, len(data), MAX_PAYLOAD_SIZE):
            chunk = data[i:i + MAX_PAYLOAD_SIZE]
            self.send_buffer.append(chunk)
        print(f"[Sender {self.connection.conn_id}] Queued {len(data)} bytes for sending.")
        self.send_buffered_data()

    # ----------------------------------------------------
    #  Send packets while window allows
    # ----------------------------------------------------
    def send_buffered_data(self):
        with self.lock:
            while (self.next_seq - self.base_seq) < self.advertised_window and self.send_buffer:
                payload = self.send_buffer.popleft()
                header = TransportHeader(
                    ver=1,
                    flags=FLAG_PSH,
                    conn_id=self.connection.conn_id,
                    seq=self.next_seq,
                    ack=0,
                    rwnd=0,
                    length=len(payload)
                )

                packet = serialize_packet(header, payload)
                self.connection.protocol._send_raw_packet(header, payload, self.connection.peer_address)
                print(f"[Sender {self.connection.conn_id}] Sent packet seq={self.next_seq}")

                # Start retransmission timer
                self.start_rto_timer(packet, self.next_seq)
                self.next_seq += len(payload)

    # ----------------------------------------------------
    #  Retransmission timer handling
    # ----------------------------------------------------
    def start_rto_timer(self, packet: bytes, seq_num: int):
        timer = threading.Timer(RTO_VALUE, self.on_rto_expired, args=[packet, seq_num])
        timer.daemon = True
        timer.start()
        self.unacked_packets[seq_num] = (packet, timer)

    def on_rto_expired(self, packet: bytes, seq_num: int):
        """Called when an ACK hasn't arrived in time."""
        with self.lock:
            if seq_num in self.unacked_packets:
                print(f"[Sender {self.connection.conn_id}] Timeout → retransmitting seq={seq_num}")
                self.connection.protocol._send_raw_packet(None, packet, self.connection.peer_address)
                # restart timer
                self.start_rto_timer(packet, seq_num)

    # ----------------------------------------------------
    #  ACK handling
    # ----------------------------------------------------
    def process_incoming_ack(self, header: TransportHeader):
        """Handle cumulative ACKs."""
        ack_num = header.ack
        print(f"[Sender {self.connection.conn_id}] Received ACK={ack_num}")
        with self.lock:
            # Remove all packets fully acknowledged
            to_remove = [seq for seq in self.unacked_packets if seq < ack_num]
            for seq in to_remove:
                packet, timer = self.unacked_packets.pop(seq)
                if isinstance(timer, threading.Timer):
                    timer.cancel()
                print(f"[Sender {self.connection.conn_id}] Packet seq={seq} ACKed and removed.")

            # Slide window forward
            self.base_seq = ack_num
            self.advertised_window = header.rwnd

            # Try to send more if window opened
            self.send_buffered_data()
