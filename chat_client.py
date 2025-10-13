import socket
import threading
name = input("Enter a name: ")

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(('127.0.0.1', 20001))

def receive():
    while True:
        try:
            data = client.recv(1024).decode('utf-8')
            if data == 'name':
                pass
            else:
                print(data)
        except:
            print("ERROR")
            client.close()
            break

def write():
    while True:
        message = f'{name}: {input("Enter a message: ")}'
        client.send(message.encode('utf-8'))

receive_thread = threading.Thread(target=receive)
receive_thread.start()

write_thread = threading.Thread(target=write)
write_thread.start()