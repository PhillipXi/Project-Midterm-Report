from .packet import TransportHeader, FLAG_ACK
import threading


class ReceiverLogic:
    """
    Part 3 – Receiver Logic (Reliability & Flow Control)
    ----------------------------------------------------
    • Handles incoming packets for an established connection
    • Buffers out-of-order packets (Selective-Repeat style)
    • Delivers only in-order data to the app callback
    • Sends ACKs with cumulative ack + advertised window (rwnd)
    """

    def __init__(self, conn):
        self.conn = conn                      # Reference to Connection object
        self.MAX_BUFFER_SIZE = 64 * 1024      # 64 KB receiver window
        self.buffer = {}                      # seq → payload
        self.next_expected_seq = 0            # Next in-order seq we expect
        self.advertised_window = self.MAX_BUFFER_SIZE
        self._lock = threading.Lock()         # Thread safety


    # Main entry point – called by protocol._route_packet()

    def process_data_packet(self, header: TransportHeader, payload: bytes):
        """Handle an incoming data packet and maintain in-order delivery."""
        with self._lock:
            seq = header.seq

            # 1. Old or duplicate → just ACK current state
            if seq < self.next_expected_seq:
                self._send_ack()
                return

            # 2. Accept if within our buffer window
            if not self._would_overflow(payload):
                self.buffer[seq] = payload
                # Try to deliver contiguous data
                self._deliver_in_order()
            else:
                print(f"[Conn {self.conn.conn_id}] Buffer full, cannot store seq={seq}")

            # 3. Always send an ACK (cumulative)
            self._send_ack()

 
    # In-order delivery

    def _deliver_in_order(self):
        """Deliver buffered data to the app in sequence order."""
        delivered = False

        while self.next_expected_seq in self.buffer:
            data = self.buffer.pop(self.next_expected_seq)
            self.next_expected_seq += len(data)
            delivered = True

            if self.conn.on_message_callback:
                try:
                    self.conn.on_message_callback(data)
                except Exception as e:
                    print(f"[Conn {self.conn.conn_id}] on_message_callback error: {e}")

        if delivered:
            self._update_advertised_window()


    # Flow control helpers

    def _would_overflow(self, incoming: bytes) -> bool:
        """Return True if adding this payload would exceed MAX_BUFFER_SIZE."""
        used = sum(len(p) for p in self.buffer.values())
        return (used + len(incoming)) > self.MAX_BUFFER_SIZE

    def _update_advertised_window(self):
        """Recalculate advertised window (rwnd) after deliveries."""
        used = sum(len(p) for p in self.buffer.values())
        self.advertised_window = max(0, self.MAX_BUFFER_SIZE - used)


    # ACK logic

    def _send_ack(self):
        """Send a pure ACK acknowledging received data."""
        self._update_advertised_window()
        ack_header = TransportHeader(
            flags=FLAG_ACK,
            conn_id=self.conn.conn_id,
            ack=self.next_expected_seq,
            rwnd=self.advertised_window
        )
        self.conn._internal_send(ack_header, b"")
