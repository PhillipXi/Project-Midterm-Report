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
We have chosen Selective Repeat ARQ for our chat room application for the following reasons:

Efficiency under loss: In a chat application, especially under bursty loss conditions (8-12%), Selective Repeat outperforms Go-Back-N by only retransmitting lost packets rather than the entire window. This significantly reduces bandwidth waste and improves goodput.
Lower latency: Chat messages are typically small and latency-sensitive. Selective Repeat minimizes head-of-line blocking by allowing out-of-order packets to be buffered and delivered once gaps are filled, rather than discarding them entirely as Go-Back-N would.
Better flow control: With independent acknowledgment of each packet, the sender receives more granular feedback about what the receiver has successfully received, enabling more precise flow control decisions.
Scalability: For a multi-client chat server, Selective Repeat's ability to maintain higher throughput under packet loss means the server can handle more concurrent connections without performance degradation.

The trade-off is increased implementation complexity (managing out-of-order buffers at both sender and receiver), but this is justified given our requirement to handle bursty loss profiles while maintaining low latency for real-time chat.

Our transport protocol header will be **20 bytes total**, structured as follows:

| **Field** | **Size (bytes)** | **Purpose** | **Details** |
|------------|------------------|--------------|--------------|
| `ver` | 1 | Protocol version | Version identifier (currently 0x01). Allows future protocol evolution. |
| `flags` | 1 | Control flags | Bit flags: SYN (0x01), ACK (0x02), FIN (0x04), RST (0x08). Controls connection lifecycle and packet type. |
| `conn_id` | 4 | Connection identifier | Unique 32-bit connection ID generated during handshake. Allows multiplexing multiple connections over same UDP port. |
| `seq` | 4 | Sequence number | 32-bit sequence number for reliable ordering. Wraps around at 2^32. Increments per packet (not per byte). |
| `ack` | 4 | Acknowledgment number | Cumulative ACK: highest in-order sequence received. Combined with SACK for Selective Repeat. |
| `window` | 2 | Receiver window size | Advertised receive window (0–65535 packets). Used for flow control to prevent receiver buffer overflow. |
| `len` | 2 | Payload length | Length of payload data in bytes (0–65535). Does not include header. |
| `checksum` | 2 | Header + payload checksum | 16-bit CRC or Internet checksum for error detection. Computed over entire packet (header + payload). |

**Total Header Size:** 20 bytes



Total Header Size: 20 bytes
Additional SACK Extension (optional field in payload):
•	When ACK flag is set, the payload may contain SACK (Selective Acknowledgment) blocks
•	Each SACK block: 8 bytes (4-byte start seq, 4-byte end seq)
•	Up to 4 SACK blocks per ACK packet to indicate non-contiguous received ranges




Reliability Logic
This transport protocol is implemented over UDP, which provides only best-effort, connectionless delivery. To add reliability and flow control, our design implements a Selective Repeat Automatic Repeat Request (ARQ) mechanism entirely in user space. Each data segment is sent as a single UDP datagram that includes our custom header and payload.
Every outgoing UDP datagram is assigned a sequence number and tracked in a send buffer. The receiver checks sequence numbers and verifies integrity using the custom checksum field. If a packet arrives intact, the receiver sends back an ACK (also a UDP datagram) containing the highest contiguous sequence received and optional Selective ACK (SACK) blocks for any additional packets that arrived out of order.
Each sent packet has its own timer. If an ACK or SACK is not received before the retransmission timeout (RTO) expires, the sender retransmits only that missing packet. The RTO is adjusted dynamically based on measured round-trip times (RTTs), and exponential backoff is used after repeated losses.
The receiver buffers out-of-order packets and reassembles them into the correct sequence before delivering them to the application layer. The receiver’s advertised window (in bytes or packets) limits how much data the sender may transmit before waiting for further acknowledgments.
All control (SYN, ACK, FIN) and data exchanges occur over UDP; our protocol implements its own reliability, ordering, and connection management on top of UDP.


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
When we test are programs it will be though the command prompt with at least 3 different command prompts open. One would be for the `chat_server.py` and the other two would be the `chat_client.py`. We would then make sure that all of our commands work as intended and that we are able to connect to the server.
to measure our performance we would have to add certain functions to calculate our metrics for the two programs. for our `chat_server.py` we would calculate the Goodput, and in our `chat_client.py` we would calculate the Throughput and retransmissions per KB. We would
calculate the Average Latency in ms and the 95th Percentile Latency in ms for both our programs.
### Calculations
this table shows how to calculate our Metrics

| Metric                        | Calculation                         |
|-------------------------------|-------------------------------------|
| `Goodput(KB/s)`               | bytes succesfilly received/duration |
| `Throughput(KB/s)`            | bytes sent/duration                 |
| `Avg Latency(ms)`             | Avg(receive time - send timestamps) |
| `95th Percentile Latency(ms)` | 95th percentile of latency list     |
| `Retransmission per KB`        | retransmit_count/(bytes sent/1024)  |


just testing our program on a `Clean Network test` we should be able to see that everything is working as intended. We would expect a 0% packet lost, low stable latency, and all messages being sent and delivered. With `Random Network lost` the goal is to see how our program handles unpredictable packet
loss. if our program is working as expected we should only see slight message lost with our chat staying operational. With `Bursty Network lost` the goal is to show how our program handles heavy loss to text message buffering, retransmission, or error handling in short periods.
The result would be several lost messages in a row, but our chat client should be able to recover, or at least maintain a stable connection.

---

### **6. Progress Summary (10/17 Status)**

* **What has been implemented so far:** The full project plan and system design are finished and documented in this README. The packet structure for the transport layer is defined, and the command grammar for the application layer is set. There are 2 very simple chat_client.py and chat_server.py files as placeholders.

* **What remains to be completed:** The main coding still needs to be done. The next steps are to build the reliability logic using a Sliding Window ARQ, add server-side concurrency so multiple clients can stay connected at once, and finish the application layer for handling commands and broadcasting messages.


* **Evidence of progress:** This README shows the work completed so far. It covers the design and planning phase in detail and lays out a clear roadmap for building and testing the rest of the project.









