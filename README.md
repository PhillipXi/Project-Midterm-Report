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

---

### **5. Testing and Metrics Plan**

---

### **6. Progress Summary (10/17 Status)**

* **What has been implemented so far:** The full project plan and system design are finished and documented in this README. The packet structure for the transport layer is defined, and the command grammar for the application layer is set. There are 2 very simple chat_client.py and chat_server.py files as placeholders.

* **What remains to be completed:** The main coding still needs to be done. The next steps are to build the reliability logic using a Sliding Window ARQ, add server-side concurrency so multiple clients can stay connected at once, and finish the application layer for handling commands and broadcasting messages.


* **Evidence of progress:** TThis README shows the work completed so far. It covers the design and planning phase in detail and lays out a clear roadmap for building and testing the rest of the project.



