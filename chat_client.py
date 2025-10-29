import time
import sys
from transport.protocol import TransportProtocol

SERVER_IP = "127.0.0.1"
SERVER_PORT = 12345
CLIENT_PORT = 54321 # Use a different port than the server

def main():
    # 1. Initialize the protocol on the client's port
    protocol = TransportProtocol(local_port=CLIENT_PORT)
    protocol.start()

    try:
        # 2. Connect to the server (blocking)
        print("Connecting to server...")
        conn = protocol.connect((SERVER_IP, SERVER_PORT), timeout=5.0)
        
        print(f"Connection established! (ID: {conn.conn_id})")
        
        # 3. Register the on_message callback
        def handle_server_message(data: bytes):
            print(f"\n[App] Received from server: {data.decode('utf-8')}")
            print("> ", end="", flush=True) # Re-draw prompt

        protocol.on_message(conn, handle_server_message)
        
        # 4. Start send loop
        print("Enter messages to send (or 'quit' to exit):")
        while True:
            message = input("> ")
            if message.lower() == 'quit':
                break
            
            # 5. Send the message
            protocol.send_msg(conn, message.encode('utf-8'))
            
    except TimeoutError:
        print("[App] Connection timed out. Exiting.")
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[App] An error occurred: {e}")
    finally:
        # 6. Close the connection
        if 'conn' in locals():
            print("Closing connection...")
            protocol.close(conn)
        protocol.stop()
        print("Client shut down.")

if __name__ == "__main__":
    main()