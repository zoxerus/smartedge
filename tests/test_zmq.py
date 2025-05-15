import zmq
import time
import threading
import json
import os
import uuid
import netifaces

def get_default_iface_name_linux():
    route = "/proc/net/route"
    with open(route) as f:
        for line in f.readlines():
            try:
                iface, dest, _, flags, _, _, _, _, _, _, _, = line.strip().split()
                if dest != '00000000' or not int(flags, 16) & 2:
                    continue
                return iface  # This is the default interface name (e.g., 'eth0', 'enp3s0')
            except:
                continue

iface = get_default_iface_name_linux()
print(f"Default interface: {iface}")



def get_interface_ip(interface_name):
    """
    Gets the IPv4 address of a specified network interface.

    Args:
        interface_name (str): The name of the network interface (e.g., 'eth0', 'en0', 'Wi-Fi').

    Returns:
        str: The IPv4 address of the interface, or None if not found.
    """
    try:
        # Get all addresses for the specified interface
        addresses = netifaces.ifaddresses(interface_name)
        # Check if AF_INET (IPv4) addresses exist for this interface
        if netifaces.AF_INET in addresses:
            # Return the first IPv4 address found
            # addresses[netifaces.AF_INET] is a list of dicts, each dict has an 'addr' key
            return addresses[netifaces.AF_INET][0]['addr']
        else:
            print(f"No IPv4 address found for interface {interface_name}.")
            return None
    except ValueError:
        print(f"Interface {interface_name} not found or is invalid.")
        return None
    except KeyError:
        print(f"No 'addr' key found for IPv4 address on interface {interface_name}.")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


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
    interface = get_default_iface_name_linux()
    ip = get_interface_ip(interface)
    node = Node(group_id)
    try:
        node.start()
    except KeyboardInterrupt:
        node.stop()
