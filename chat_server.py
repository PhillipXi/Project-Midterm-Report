import time
from transport.protocol import TransportProtocol
from transport.connection import Connection

# Server's local port
SERVER_PORT = 12345
clients = {}  # To store connection objects

# --- Application-level Callbacks ---

def handle_new_client(conn: Connection):
    """
    This is the application-level "on_connect" callback.
    It's triggered by the TransportProtocol when a handshake is complete.
    """
    print(f"[App] New client connected: {conn.peer_address} (ID: {conn.conn_id})")
    clients[conn.conn_id] = conn
    
    # --- Register other callbacks for this connection ---
    
    # 1. Register the "on_message" callback
    def handle_client_message(data: bytes):
        """This callback is run by Part 3 when a message is ready."""
        message = data.decode('utf-8')
        print(f"[App] Received from {conn.conn_id}: {message}")
        
        # Echo the message back
        response = f"Server echoes: {message}".encode('utf-8')
        protocol.send_msg(conn, response)
    
    protocol.on_message(conn, handle_client_message)
    
    # 2. Register the "on_disconnect" callback
    def handle_client_disconnect(conn: Connection):
        """This callback is run by Part 2 when a FIN is received."""
        print(f"[App] Client disconnected: {conn.conn_id}")
        if conn.conn_id in clients:
            del clients[conn.conn_id]

    protocol.on_disconnect(conn, handle_client_disconnect)


# --- Main Server Logic ---
if __name__ == "__main__":
    print("Starting server...")
    
    # 1. Initialize the protocol
    protocol = TransportProtocol(local_port=SERVER_PORT)
    
    # 2. Register the "new connection" handler
    protocol.on_new_connection = handle_new_client
    
    # 3. Start the protocol's listener
    protocol.start()
    
    try:
        while True:
            print(f"[App] Server running. {len(clients)} clients connected.")
            time.sleep(10)
    except KeyboardInterrupt:
        print("Shutting down server...")
        protocol.stop()