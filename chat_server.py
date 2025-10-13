import threading
import socket

host = '127.0.0.1'
port = 20001
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((host, port))
s.listen(5)

clients = []
names = []

def broadcast(message):
    for client in clients:
        client.send(message)

def handle_client(client):
    while True:
        try:
            message = client.recv(1024)
            broadcast(message)
        except:
            index = clients.index(client)
            clients.remove(client)
            client.close()
            name = names[index]
            broadcast(f'{name} has left the chat'.encode("utf-8"))
            names.remove(name)
            break

def receive_client():
    while True:
        client, address = s.accept()
        print(f'{str(address)} has connected.')

        client.send('name'.encode("utf-8"))
        name = client.recv(1024).decode("utf-8")
        names.append(name)
        clients.append(client)

        print(f'{name} is your name')
        broadcast(f'{name} has joined the chat'.encode("utf-8"))
        client.send('welcome!'.encode("utf-8"))

        thread = threading.Thread(target=handle_client, args=(client,))
        thread.start()





receive_client()