from pyre import Pyre
from pyre import zhelper
import zmq
import time


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

def node_task():
    # Create a Pyre node with a unique name
    node = Pyre("NODE_" + str(int(time.time())))
    node.start()
    node.join("TEST_GROUP")  # Join discovery group
    
    poller = zmq.Poller()
    poller.register(node.socket(), zmq.POLLIN)
    
    while True:
        items = dict(poller.poll(1000))
        if node.socket() in items:
            msg = node.recv()
            event = msg.pop(0).decode('utf-8')
            
            if event == "ENTER":
                print(f"Discovered peer: {msg[1].decode('utf-8')}")
                # Send welcome message to new peer
                node.whisper(msg[1], b"Welcome to the network!")
                
            elif event == "WHISPER":
                print(f"Received message: {msg[-1].decode('utf-8')}")
                
            elif event == "EXIT":
                print(f"Peer left: {msg[1].decode('utf-8')}")

if __name__ == "__main__":
    node_task()
