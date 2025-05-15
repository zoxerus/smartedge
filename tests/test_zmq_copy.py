import socket
import threading
import json
import time

# Configuration
PORT = 5000  # Port to listen on
GROUP_ID = "my_group"  # Group identifier
DISCOVERY_INTERVAL = 5  # Seconds between discovery messages

class Node:
    def __init__(self):
        self.node_name = socket.gethostname()
        self.known_nodes = {self.node_name: self.get_ip()}  # Known nodes in the network
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', PORT))
        self.lock = threading.Lock()  # To protect shared resources

    def get_ip(self):
        """Get the IP address of the current device."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't need to be reachable
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    def listen(self):
        """Listen for incoming messages."""
        while True:
            try:
                data, addr = self.sock.recvfrom(1024)
                message = json.loads(data.decode('utf-8'))
                if message['group_id'] == GROUP_ID:
                    node_name = message['node_name']
                    node_ip = message['node_ip']
                    with self.lock:
                        if node_name not in self.known_nodes:
                            self.known_nodes[node_name] = node_ip
                            print(f"Discovered node: {node_name} at {node_ip}")
            except Exception as e:
                print(f"Error receiving data: {e}")

    def announce(self):
        """Announce presence periodically."""
        while True:
            message = {
                'group_id': GROUP_ID,
                'node_name': self.node_name,
                'node_ip': self.get_ip()
            }
            message_json = json.dumps(message)
            try:
                # Broadcast to all devices on the network
                self.sock.sendto(message_json.encode('utf-8'), ('<broadcast>', PORT))
            except Exception as e:
                print(f"Error sending data: {e}")
            time.sleep(DISCOVERY_INTERVAL)

    def start(self):
        """Start the node."""
        # Enable broadcasting
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Start listening thread
        listen_thread = threading.Thread(target=self.listen, daemon=True)
        listen_thread.start()

        # Start announcing thread
        announce_thread = threading.Thread(target=self.announce, daemon=True)
        announce_thread.start()

        print("Node started. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)  # Keep the main thread alive
        except KeyboardInterrupt:
            print("Exiting.")

if __name__ == "__main__":
    node = Node()
    node.start()
