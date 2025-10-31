# transport/receiver.py
from packet import (
    TransportHeader,
    FLAG_ACK,
    serialize_packet
)

class ReceiverLogic:
    """Handles incoming packets for a single connection."""
    
    def __init__(self, connection):
        self.connection = connection  # Reference to the Connection object
        self.expected_seq = 0          # Next expected sequence number
        self.buffer = {}               # Out-of-order packets
        self.rwnd = 4096               # Receiver window size (for flow control)

    def process_data_packet(self, header: TransportHeader, payload: bytes):
        """Called when data arrives from the network."""
        conn_id = self.connection.conn_id
        print(f"[Receiver {conn_id}] Got packet seq={header.seq}, expected={self.expected_seq}")

        # ✅ Drop if sequence number is less than expected (duplicate)
        if header.seq < self.expected_seq:
            print(f"[Receiver {conn_id}] Duplicate packet dropped (seq={header.seq})")
            self.send_ack()  # Re-ACK to confirm what we have
            return

        # ✅ If it’s the next in sequence, deliver to app
        if header.seq == self.expected_seq:
            print(f"[Receiver {conn_id}] Delivering in-order data.")
            self.connection.deliver_data_to_app(payload)
            self.expected_seq += len(payload)

            # Check if we can deliver any buffered packets in order
            while self.expected_seq in self.buffer:
                next_payload = self.buffer.pop(self.expected_seq)
                self.connection.deliver_data_to_app(next_payload)
                self.expected_seq += len(next_payload)
        else:
            # ✅ Out-of-order: buffer it
            print(f"[Receiver {conn_id}] Out-of-order packet buffered (seq={header.seq})")
            self.buffer[header.seq] = payload

        # Always send ACK
        self.send_ack()

    def send_ack(self):
        """Send ACK for all data received so far."""
        ack_header = TransportHeader(
            ver=1,
            flags=FLAG_ACK,
            conn_id=self.connection.conn_id,
            seq=0,                # No data in ACK-only packet
            ack=self.expected_seq, # Cumulative ACK
            rwnd=self.rwnd,
            length=0
        )

        # No payload, ACK-only packet
        packet = serialize_packet(ack_header, b'')
        self.connection.protocol._send_raw_packet(ack_header, b'', self.connection.peer_address)

        print(f"[Receiver {self.connection.conn_id}] Sent ACK for seq={self.expected_seq}, rwnd={self.rwnd}")
