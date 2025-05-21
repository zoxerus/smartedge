import socket
import threading
import json
import netifaces
import time

# Configuration
PORT = 5000  # Port to listen on
GROUP_ID = "my_group"  # Group identifier
DISCOVERY_INTERVAL = 5  # Seconds between discovery messages


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
    def __init__(self, node_type, node_uuid, node_sebackbone_ip):
        self.node_name = socket.gethostname()
        self.node_type = node_type
        self.uuid = node_uuid
        self.node_sebackbone_ip = node_sebackbone_ip
        self.known_nodes = {self.node_name: self.get_ip()}  # Known nodes in the network
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', PORT))
        self.lock = threading.Lock()  # To protect shared resources
        
    def get_known_nodes(self):
        return self.known_nodes

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
