### **1. Team Information**

* **Team Name:** Team 1
* **Team Members:**
  * Amber Parker
  * Hugo Juarez Gurrola 
  * Phillip Ximenez
  * Annmarie Kongglang
* **Selected Project:** Group Chat with Rooms + Presence

---

### **2. Project Overview**

This project is about building a reliable multi-client chat service that runs over a custom transport layer built on top of UDP. The goal is to design a protocol that acts like TCP, handling things like in order message delivery, retransmissions, and flow control. In the final demo, multiple clients will be able to connect to the same server, join different chat rooms, and message in real time. Performance and reliability will be tested under three network setups: a clean connection, one with random packet loss, and one with bursty loss to see how well the protocol holds up.

---

### **3. Transport Protocol Design Plan**

---

### **4. Application Logic Plan**

### Command Grammar 

The "Group Chat with Rooms + Presence" application uses a text-based message structure for client-server communication. Each command or message follows this format: 


#### Client → Server Commands

| Command | Example | Description |
|----------|----------|-------------|
| `JOIN <room>` | `JOIN main` | Client joins (or creates) a chat room. |
| `LEAVE <room>` | `LEAVE main` | Client leaves the specified room. |
| `MSG <room> <text>` | `MSG main Hello everyone!` | Sends a message to all users in that room. |
| `WHO <room>` | `WHO main` | Requests a list of users in the room. |
| `QUIT` | `QUIT` | Gracefully disconnects from the server. |

#### Server → Client Messages

| Message | Example | Description |
|----------|----------|-------------|
| `SYS <text>` | `SYS Welcome to the chat server!` | System or status message. |
| `MSG <room> <sender>: <text>` | `MSG main Ann: Hi there!` | Broadcast message sent to a room. |
| `JOINED <room> <user>` | `JOINED main Amber` | Notifies users when someone joins. |
| `LEFT <room> <user>` | `LEFT main Hugo` | Notifies users when someone leaves. |
| `USERS <room> <user1,user2,...>` | `USERS main Ann, Amber, Hugo, Philip` | Lists all users in the specified room. |

---

### Client–Server Interaction

The steps below describe how clients and the server communicate:

1. **Connection Established**  
   - The client connects to the server using the reliable transport layer.  
   - The server sends: `SYS Welcome`.

2. **Join a Room**  
   - The client sends: `JOIN <room>`.  
   - The server adds the client and broadcasts `JOINED <room> <username>` to others in that room.

3. **Chat Messaging**  
   - The client sends: `MSG <room> <text>`.  
   - The server relays it to everyone in the room as `MSG <room> <sender>: <text>`.

4. **Presence Updates**  
   - When users join or leave, `JOINED` or `LEFT` messages are broadcast to notify all connected clients.

5. **Disconnection**  
   - When a client sends `QUIT` or closes their connection, the server removes them and sends `LEFT` notifications.

---

### Concurrency Plan

The server is designed to support multiple clients using **multi-threading**:

- Each client connection is managed by a **separate thread**.  
- The server’s main thread accepts connections; worker threads handle I/O for each client.  
- Shared resources like message queues and room membership lists are synchronized with **locks** or **mutexes** to avoid conflicts.  
- This ensures smooth message delivery and real-time chat across multiple users.

---

### **5. Testing and Metrics Plan**

---

### **6. Progress Summary (10/17 Status)**

* **What has been implemented so far:** The full project plan and system design are finished and documented in this README. The packet structure for the transport layer is defined, and the command grammar for the application layer is set. There are 2 very simple chat_client.py and chat_server.py files as placeholders.

* **What remains to be completed:** The main coding still needs to be done. The next steps are to build the reliability logic using a Sliding Window ARQ, add server-side concurrency so multiple clients can stay connected at once, and finish the application layer for handling commands and broadcasting messages.


* **Evidence of progress:** TThis README shows the work completed so far. It covers the design and planning phase in detail and lays out a clear roadmap for building and testing the rest of the project.






