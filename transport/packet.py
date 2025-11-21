# transport/packet.py
import struct
import socket
from dataclasses import dataclass

# =======================
# ---- CONSTANTS ----
# =======================
FLAG_SYN = 0x01
FLAG_ACK = 0x02
FLAG_FIN = 0x04
FLAG_PSH = 0x08

# =======================
# ---- HEADER SETUP ----
# =======================
HEADER_FORMAT = "!HHLLLHHH"
HEADER_LEN = struct.calcsize(HEADER_FORMAT)

@dataclass
class TransportHeader:
    ver: int = 1
    flags: int = 0
    conn_id: int = 0
    seq: int = 0
    ack: int = 0
    rwnd: int = 0
    length: int = 0
    checksum: int = 0


# =======================
# ---- CHECKSUM ----
# =======================
def calculate_checksum(data: bytes) -> int:
    """Compute 16-bit Internet checksum."""
    if len(data) % 2:
        data += b'\x00'

    checksum = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        checksum += word
        checksum = (checksum & 0xFFFF) + (checksum >> 16)

    return ~checksum & 0xFFFF


def verify_checksum(packet_data: bytes) -> bool:
    """Verify that the checksum is valid."""
    return calculate_checksum(packet_data) == 0


# =======================
# ---- SERIALIZATION ----
# =======================
def serialize_packet(header: TransportHeader, payload: bytes) -> bytes:
    """Convert header + payload into bytes with a correct checksum."""
    # First pack with checksum = 0
    temp_header = struct.pack(
        HEADER_FORMAT,
        header.ver, header.flags, header.conn_id, header.seq,
        header.ack, header.rwnd, header.length, 0
    )
    packet = temp_header + payload

    # Compute checksum
    checksum = calculate_checksum(packet)

    # Repack header with correct checksum
    final_header = struct.pack(
        HEADER_FORMAT,
        header.ver, header.flags, header.conn_id, header.seq,
        header.ack, header.rwnd, header.length, checksum
    )
    return final_header + payload


def deserialize_packet(data: bytes) -> tuple[TransportHeader, bytes]:
    """Extract header and payload from raw bytes."""
    fields = struct.unpack(HEADER_FORMAT, data[:HEADER_LEN])
    header = TransportHeader(*fields)
    payload = data[HEADER_LEN:]
    return header, payload


# =======================
# ---- UDP I/O ----
# =======================
def init_socket(port: int) -> socket.socket:
    """Create and bind a UDP socket."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', port))
    return sock


def send_raw_packet(sock: socket.socket, data: bytes, dest_addr: tuple):
    """Send a UDP packet."""
    sock.sendto(data, dest_addr)


def receive_raw_packet(sock: socket.socket, bufsize: int = 4096) -> tuple[bytes, tuple]:
    """Receive a UDP packet."""
    data, addr = sock.recvfrom(bufsize)
    return data, addr
