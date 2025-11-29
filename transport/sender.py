# transport/sender.py
import threading
import time
from collections import deque
from packet import (
    TransportHeader,
    FLAG_ACK,
    FLAG_PSH,
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
        
        self.bytes_sent = 0
        self.retransmissions = 0
        self.rtt_samples = []

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

                self.connection._internal_send(header, payload)
                print(f"[Sender {self.connection.conn_id}] Sent packet seq={self.next_seq}")

                self.bytes_sent += len(payload)

                # Start retransmission timer
                self.start_rto_timer(payload, self.next_seq)
                self.next_seq += len(payload)

    # ----------------------------------------------------
    #  Retransmission timer handling
    # ----------------------------------------------------
    def start_rto_timer(self, header, payload: bytes, seq_num: int):
        timer = threading.Timer(RTO_VALUE, self.on_rto_expired, args=[payload, seq_num])
        timer.daemon = True
        timer.start()
        current_time = time.time()
        self.unacked_packets[seq_num] = (header, payload, timer, current_time)

    def on_rto_expired(self, header, payload: bytes, seq_num: int):
        """Called when an ACK hasn't arrived in time."""
        with self.lock:
            if seq_num in self.unacked_packets:
                print(f"[Sender {self.connection.conn_id}] Timeout → retransmitting seq={seq_num}")
                self.retransmissions += 1
                self.connection.internal_send(header, payload)
                # self.connection.protocol._send_raw_packet(None, payload, self.connection.peer_address)
                # restart timer
                self.start_rto_timer(header, payload, seq_num)

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
                header, payload, timer, send_time = self.unacked_packets.pop(seq)
                if isinstance(timer, threading.Timer):
                    timer.cancel()
                    
                rtt = time.time() - send_time
                self.rtt_samples.append(rtt)
                
                print(f"[Sender {self.connection.conn_id}] Packet seq={seq} ACKed. RTT={rtt:.4f}s")

            # Slide window forward
            self.base_seq = ack_num
            self.advertised_window = header.rwnd

            # Try to send more if window opened
            self.send_buffered_data()
