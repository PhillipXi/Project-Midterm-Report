import time
import json
from transport.protocol import TransportProtocol
from transport.connection import Connection

SERVER_PORT = 12345

# Map conn_id -> Connection object
clients = {}

# Map "room_name" -> [conn_id, conn_id, ...]
# We initialize with a 'general' room
rooms = {"general": []}

# Map conn_id -> "Username" (Person 4 will manage this, but I need it for notifications)
usernames = {}

# Map "room_name" -> List of messages (Person 4 will manage this)
history = {"general": []}


# Helper functions

def get_username(conn_id):
    # Helper to get a name or default to 'Unknown'
    return usernames.get(conn_id, f"User{conn_id}")

def broadcast(room, json_obj, exclude_conn_id=None):
    # (Person 3's Job, but Person 1 needs it for notifications).
    # Sends a JSON message to everyone in a specific room.

    if room not in rooms:
        return

    payload = json.dumps(json_obj).encode('utf-8')
    
    # Loop through all connection IDs in the room
    for cid in rooms[room]:
        if cid == exclude_conn_id:
            continue
            
        if cid in clients:
            conn = clients[cid]
            try:
                # Use the transport protocol to send
                protocol.send_msg(conn, payload)
            except Exception as e:
                print(f"[Server] Broadcast error to {cid}: {e}")

# Message handlers 

def handle_login(conn, data):
    # STUB (Person 4, handle login packet) For now, just accept everyone
    name = data.get('name', f'User{conn.conn_id}')
    usernames[conn.conn_id] = name
    
    # Send welcome
    welcome = {"type": "INFO", "msg": f"Welcome {name}!"}
    protocol.send_msg(conn, json.dumps(welcome).encode('utf-8'))
    
    # Auto-join general
    handle_join(conn, {"room": "general"})

def handle_join(conn, data):
    # Handle JOIN packet.
    # 1. Remove user from current room (if any).
    # 2. Add conn.conn_id to rooms[data['room']].
    # 3. Broadcast {"type": "INFO", "msg": "User joined"} to that room.

    room_name = data.get('room')
    if not room_name:
        return

    # 1. Leave current room first (cleanup)
    # We iterate to find where they currently are
    for r_name, members in rooms.items():
        if conn.conn_id in members:
            # remove them from the old room
            members.remove(conn.conn_id)
            # Notify old room
            old_msg = {"type": "INFO", "msg": f"{get_username(conn.conn_id)} left."}
            broadcast(r_name, old_msg)
            break

    # 2. Create room if it doesn't exist
    if room_name not in rooms:
        rooms[room_name] = []

    # 3. Add to new room
    rooms[room_name].append(conn.conn_id)
    print(f"[Server] {conn.conn_id} joined room '{room_name}'")

    # 4. Notify new room
    join_msg = {"type": "INFO", "msg": f"{get_username(conn.conn_id)} joined {room_name}."}
    broadcast(room_name, join_msg)


def handle_leave(conn, data):
# Handle leave packet
    room_name = data.get('room')
    if room_name and room_name in rooms:
        if conn.conn_id in rooms[room_name]:
            rooms[room_name].remove(conn.conn_id)
            
            # Notify room
            msg = {"type": "INFO", "msg": f"{get_username(conn.conn_id)} left {room_name}."}
            broadcast(room_name, msg)


def handle_msg(conn, data):
    # STUB (Person 3) Basic echo to room for testing
    room = data.get('room')
    text = data.get('text')
    if room and text:
        out_msg = {
            "type": "CHAT", 
            "room": room, 
            "sender": get_username(conn.conn_id), 
            "text": text
        }
        broadcast(room, out_msg)

def handle_dm(conn, data):
    """(Person 3's Job): Handle DM packet."""
    pass # Person 3 will implement this

# Main dispatcher

def process_message(conn: Connection, raw_data: bytes):
    """Decodes raw bytes to JSON and calls the right handler."""
    try:
        payload = json.loads(raw_data.decode('utf-8'))
        msg_type = payload.get("type")
        
        # Dispatcher logic
        if msg_type == "LOGIN": handle_login(conn, payload)
        elif msg_type == "JOIN": handle_join(conn, payload)
        elif msg_type == "LEAVE": handle_leave(conn, payload)
        elif msg_type == "MSG": handle_msg(conn, payload)
        elif msg_type == "DM": handle_dm(conn, payload)
        else: print(f"Unknown message type: {msg_type}")

    except Exception as e:
        print(f"Error processing message from {conn.conn_id}: {e}")

# Connect events 

def on_new_client(conn: Connection):
    print(f"[App] New client connected: {conn.conn_id}")
    clients[conn.conn_id] = conn
    
    # Register the message handler
    protocol.on_message(conn, lambda d: process_message(conn, d))
    protocol.on_disconnect(conn, on_client_disconnect)

def on_client_disconnect(conn: Connection):
    # Clean up user from all lists
    # This prevents the server from crashing if it tries to send to a dead user
    
    print(f"[App] Client {conn.conn_id} disconnected.")
    cid = conn.conn_id
    
    # 1. Remove from clients list
    if cid in clients:
        del clients[cid]

    # 2. Remove from rooms and notify others
    for r_name, members in rooms.items():
        if cid in members:
            members.remove(cid)
            msg = {"type": "INFO", "msg": f"{get_username(cid)} disconnected."}
            broadcast(r_name, msg)

    # 3. Remove username
    if cid in usernames:
        del usernames[cid]

if __name__ == "__main__":
    protocol = TransportProtocol(local_port=SERVER_PORT)
    protocol.on_new_connection(on_new_client)
    protocol.start()

    print(f"Server started on port {SERVER_PORT}. Waiting for connections...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping server...")
        protocol.stop()
        