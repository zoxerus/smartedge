import zmq
import time
import threading
import json
import os
import uuid

class Node:
    def __init__(self, group_id, interface='*', port=5000):
        self.node_id = str(uuid.uuid4())
        self.group_id = group_id
        self.interface = interface
        self.port = port
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)
        self.subscriber = self.context.socket(zmq.SUB)
        self.subscriber.setsockopt_string(zmq.SUBSCRIBE, self.group_id)
        self.address = f"tcp://{self.interface}:{self.port}"
        self.publisher.bind(self.address)
        self.peers = {}

    def start_listening(self):
        """
        Start listening for announcements from other nodes.
        """
        self.subscriber.connect(self.address)
        while True:
            try:
                topic, message = self.subscriber.recv_multipart()
                self.process_message(topic.decode('utf-8'), message.decode('utf-8'))
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    break  # Context terminated
                else:
                    raise

    def announce_presence(self):
        """
        Announce the presence of this node by broadcasting its node_id and group_id.
        """
        message = {'node_id': self.node_id, 'address': self.address}
        self.broadcast(self.group_id, json.dumps(message))

    def broadcast(self, topic, message):
        """
        Broadcast a message to all subscribers.
        """
        try:
            self.publisher.send_multipart([topic.encode('utf-8'), message.encode('utf-8')])
            print(f"Node {self.node_id} broadcast: {message} on topic {topic}")
        except zmq.ZMQError as e:
            if e.errno == zmq.ETERM:
                print("Broadcasting stopped due to context termination.")
            else:
                raise

    def process_message(self, topic, message):
        """
        Process incoming messages, updating the peer list.
        """
        if topic == self.group_id:
            try:
                data = json.loads(message)
                peer_node_id = data.get('node_id')
                peer_address = data.get('address')

                if peer_node_id and peer_node_id != self.node_id:
                    if peer_node_id not in self.peers:
                        self.peers[peer_node_id] = peer_address
                        print(f"Node {self.node_id} discovered new peer: {peer_node_id} at {peer_address}")
            except json.JSONDecodeError:
                print(f"Node {self.node_id} received invalid JSON: {message}")

    def start(self):
        """
        Start the node, launching the listener thread and announcing presence.
        """
        listener_thread = threading.Thread(target=self.start_listening, daemon=True)
        listener_thread.start()

        # Announce presence periodically
        while True:
            self.announce_presence()
            time.sleep(5)  # Announce every 5 seconds

    def stop(self):
        """
        Stop the node and clean up resources.
        """
        print(f"Node {self.node_id} is stopping...")
        self.context.term()

if __name__ == '__main__':
    group_id = "my_network"  # Define a group ID for your network
    node = Node(group_id)
    try:
        node.start()
    except KeyboardInterrupt:
        node.stop()
