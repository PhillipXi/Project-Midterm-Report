# chat_server.py
# Simple TCP chat server
# Usage: python chat_server.py <listen_port> [--live]
# Example: python chat_server.py 5000 --live
#
# Modes:
# - Default (line-based): send only when you press Enter; remote lines print as "Client: <line>".
# - --live (per-keystroke): send each key as you type; local echo shows what you type immediately,
#   remote characters are shown with a prefix at the start of each received line ("[Client] ").
#
# This server:
# - Listens for a single TCP client connection on the given port
# - Spawns a thread to receive and print what the client sends
# - Reads server user's input lines and sends them to the client
# - Type "quit" to exit cleanly

import socket
import sys
import threading
import os

def handle_client(conn, addr, live=False):
    """Receive data from the client and print it to stdout."""
    print(f"[+] Connected by {addr}")
    at_line_start = True  # Track if next received character starts a new line (for prefixing)
    while True:
        try:
            # Receive up to 4096 bytes from TCP socket
            data = conn.recv(4096)
            if not data:
                break
            if live:
                # In live mode, print bytes immediately and add a prefix at the start of each line
                # so remote input is clearly distinguishable from local echo.
                text = data.decode('utf-8', errors='replace')
                for ch in text:
                    if at_line_start:
                        sys.stdout.write("\n[Client] ")
                        at_line_start = False
                    sys.stdout.write(ch)
                    if ch == '\n':
                        at_line_start = True
                sys.stdout.flush()
            else:
                # Print what the client sent
                print(f"Client: {data.decode('utf-8', errors='replace')}")
        except ConnectionResetError:
            break
    conn.close()
    print(f"[-] Disconnected {addr}")

def _read_chars_windows():
    import msvcrt
    while True:
        ch = msvcrt.getwch()
        if ch == '\r':
            ch = '\n'
        yield ch

def _read_chars_unix():
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == '\r':
                ch = '\n'
            yield ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python chat_server.py listen_port [--live]")
        sys.exit(1)

    port = int(sys.argv[1])
    live = len(sys.argv) == 3 and sys.argv[2] == "--live"

    # Create socket (IPv4, TCP)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Bind to all interfaces so remote clients can connect
    server_socket.bind(("0.0.0.0", port))  # listen on all interfaces
    server_socket.listen(1)
    print(f"[+] Server listening on port {port}")

    # Block until a client connects
    conn, addr = server_socket.accept()
    if live:
        # Reduce latency for small writes in live mode
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    # Start background thread to receive/print client data
    threading.Thread(target=handle_client, args=(conn, addr, live), daemon=True).start()

    if live:
        # Keystroke-by-keystroke sending with local echo and basic backspace handling.
        # Local echo lets you see what you type even before the client receives it.
        try:
            reader = _read_chars_windows if os.name == 'nt' else _read_chars_unix
            for ch in reader():
                # Local echo
                if ch in ('\b', '\x7f'):
                    # Handle backspace locally: erase one char visually
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
                else:
                    sys.stdout.write(ch)
                    sys.stdout.flush()
                try:
                    # Send each character immediately to the client
                    conn.sendall(ch.encode('utf-8', errors='replace'))
                except (BrokenPipeError, ConnectionResetError):
                    break
        except KeyboardInterrupt:
            pass
    else:
        # Line-based sending: send when user presses Enter
        while True:
            try:
                msg = input()
            except EOFError:
                break
            if msg.lower() == "quit":
                break
            try:
                # Send the entire message to the connected client
                conn.sendall(msg.encode())
            except (BrokenPipeError, ConnectionResetError):
                break

    # Close sockets to free resources
    conn.close()
    server_socket.close()

if __name__ == "__main__":
    main()
