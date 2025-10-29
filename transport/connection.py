from enum import Enum, auto
from typing import Callable, Optional
import time
from .receiver import ReceiverLogic
from .sender import SenderLogic

class ConnectionState(Enum):
    # Manages the state of a single connection 
    LISTENING = auto()  # Server only, waiting for SYN
    SYN_SENT = auto()     # Client only, SYN sent, waiting for SYN-ACK
    SYN_RECV = auto()     # Server only, SYN received, SYN-ACK sent
    ESTABLISHED = auto()  # Client/Server, handshake complete
    FIN_WAIT = auto()     # Client/Server, FIN sent, waiting for FIN-ACK
    CLOSED = auto()       # Client/Server, connection closed

class Connection:
    # Holds all state for a single connection. This object is the "brain" for one client-server relationship.
    def __init__(self, protocol, conn_id: int, peer_address: tuple[str, int], 
                 initial_state: ConnectionState):
        # Use tuple[str, int] for modern Python type hints
        self.protocol = protocol  # Reference to the main TransportProtocol
        self.conn_id = conn_id
        self.peer_address = peer_address
        self.state = initial_state
        self.last_active_time = time.time()
        
        # Application callbacks
        self.on_message_callback: Optional[Callable[[bytes], None]] = None
        self.on_disconnect_callback: Optional[Callable[["Connection"], None]] = None

        # Reliability Logic (Parts 3 & 4)
        # This connection "owns" its sender and receiver logic
        # This is where the "contract" is enforced
        self.receiver = ReceiverLogic(self)
        self.sender = SenderLogic(self)

        print(f"[Conn {self.conn_id}] New connection to {peer_address}, state={self.state.name}")

    def update_activity(self):
        # Updates the last active time
        self.last_active_time = time.time()

    def deliver_data_to_app(self, data: bytes):
        # Called by Part 3 (ReceiverLogic) when contiguous data is ready. This triggers the application's registered callback.
        if self.on_message_callback:
            try:
                self.on_message_callback(data)
            except Exception as e:
                print(f"[Conn {self.conn_id}] Error in on_message_callback: {e}")
        else:
            print(f"[Conn {self.conn_id}] No on_message_callback registered. Dropping data.")

    def _internal_send(self, header, payload: bytes):
        # Provides a single, unified send function for Parts 3 & 4. This calls the main protocol's private send method.
        # Set the correct conn_id and peer_address for sending
        header.conn_id = self.conn_id
        self.protocol._send_raw_packet(header, payload, self.peer_address)
