# This tells python to look for files in parent directory
import sys
import subprocess


# setting path
sys.path.append('..')
sys.path.append('.')

import importlib.util
def check_and_install(*args):
    for package_name in args:
        # Check if the package is installed
        if importlib.util.find_spec(package_name) is None:
            print(f"'{package_name}' is not installed. Installing...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
                print(f"'{package_name}' has been installed successfully.")
            except subprocess.CalledProcessError as e:
                print(f"Failed to install '{package_name}': {e}")
        else:
            print(f"'{package_name}' is already installed.")


check_and_install('aenum', 'cassandra-driver', 'psutil')

import lib.global_config as global_config
import ipaddress
import socket
import re
import os
import logging
import ipaddress

import threading
import lib.bmv2_thrift_lib as bmv2
import lib.database_comms as db_comms

from argparse import ArgumentParser






parser = ArgumentParser()
parser.add_argument("-l", "--log-level",type=int, default=10, help="logging level")
args = parser.parse_args()





dir_path = os.path.dirname(os.path.realpath(__file__))


# where to store program logs
PROGRAM_LOG_FILE_NAME = './logs/coordinator.log'
os.makedirs(os.path.dirname(PROGRAM_LOG_FILE_NAME), exist_ok=True)
logger = logging.getLogger('coordinator_logger')
# this part handles logging to console and to a file for debugging purposes
log_formatter = logging.Formatter("\n\nLine:%(lineno)d at %(asctime)s [%(levelname)s] %(filename)s :\n\t %(message)s \n\n")

# log_file_handler = logging.FileHandler(PROGRAM_LOG_FILE_NAME, mode='w')
# log_file_handler.setLevel(args.log_level)
# log_file_handler.setFormatter(log_formatter)

log_console_handler = logging.StreamHandler(sys.stdout)
log_console_handler.setLevel(args.log_level)
log_console_handler.setFormatter(log_formatter)
logger.setLevel(args.log_level)    
# logger.addHandler(log_file_handler)
logger.addHandler(log_console_handler)

logger.debug(f'running in: {dir_path}')

db_comms.db_logger = logger
bmv2.bmv2_logger = logger



def int_to_mac(macint):
    if type(macint) != int:
        raise ValueError('invalid integer')
    return ':'.join(['{}{}'.format(a, b)
                     for a, b
                     in zip(*[iter('{:012x}'.format(macint ))]*2)])  # + 2199023255552

# TCP related
COORDINATOR_MAX_TCP_CONNNECTIONS = 5

# TODO: delete this
SWARM_NODE_TCP_SERVER = ('', 29997) 


DEFAULT_THRIFT_PORT = bmv2.DEFAULT_THRIFT_PORT

THIS_SWARM_SUBNET=ipaddress.ip_address( global_config.this_swarm_subnet )

db_comms.DATABASE_IN_USE = db_comms.STR_DATABASE_TYPE_CASSANDRA

database_session = db_comms.init_database('0.0.0.0', global_config.database_port)
db_comms.DATABASE_SESSION = database_session

# a function to parse a string and extract integers
# needed for interactiosn with bmv2

def extract_numbers(lst):
    """
    Extracts numbers from a list of strings using regular expressions.
    """
    # Compile a regular expression pattern to match digits
    pattern = re.compile(r'\d+')
     
    # Use the pattern to extract all digits from each string in the list
    extracted_numbers = [pattern.findall(s) for s in lst]
     
    # Convert the extracted numbers from strings to integers
    return [int(x) for sublist in extracted_numbers for x in sublist]



# this updates the list of broadcast ports in bmv2
def add_bmv2_swarm_broadcast_port_to_ap(ap_ip,thrift_port, switch_port ):
        res = bmv2.send_cli_command_to_bmv2(cli_command='mc_dump', thrift_ip=ap_ip, thrift_port=thrift_port)
        res_lines = res.splitlines()
        i = 0
        
        for line in res_lines:
            if 'mgrp(' in line:
                port_list = set(extract_numbers([ res_lines[i+1].split('ports=[')[1].split(']')[0] ]))
                port_list.add(switch_port)
                broadcast_ports =  ' '.join( str(port) for port in port_list)
                bmv2.send_cli_command_to_bmv2(f"mc_node_update 0 {broadcast_ports} ", ap_ip, thrift_port )  
            i = i + 1


def get_ap_ip_from_ap_id(ap_id):
    try:
        return global_config.ap_list[ap_id][0]
    except:
        return None
    
    

class Swarm_Node_Handler:
    def __init__(self, message, node_socket: socket.socket):
        self.message_as_word_array = message.split()
        self.node_socket = node_socket
        
    def handle_message(self):
        match self.message_as_word_array[0]:
            case 'Join_Request':
                self.handle_new_station_message()
                
            case 'node_left_ap':
                pass
            case _:
                pass    
            
    def handle_new_station_message(self):

        print('\nNew Join Request from: ', end='')
        req_id = self.message_as_word_array[1]
        node_uuid = self.message_as_word_array[2]
        node_swarm_id = self.message_as_word_array[3]
        node_swarm_ip = self.message_as_word_array[4]
        node_swarm_mac = self.message_as_word_array[5]
        node_swarm_ap = self.message_as_word_array[6]
        print(node_uuid + ' on ' + node_swarm_ap)        
    
        ap_ip = get_ap_ip_from_ap_id(node_swarm_ap)
        if (ap_ip == None):
            logger.error(f'Error: could not find IP of access point {node_swarm_ap}')
            return
    
        db_comms.update_db_with_joined_node(node_uuid, node_swarm_id)
                    
        # add_bmv2_swarm_broadcast_port_to_ap(ap_ip= ap_ip, thrift_port=DEFAULT_THRIFT_PORT, switch_port= node_swarm_id)

        entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                                                    table_name='MyIngress.tb_ipv4_lpm',
            action_name='MyIngress.ac_ipv4_forward', match_keys=f'{node_swarm_ip}/32' , 
            action_params= f'{str(node_swarm_id)}', thrift_ip= ap_ip, thrift_port= DEFAULT_THRIFT_PORT )
    
        entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
                                                    table_name='MyIngress.tb_l2_forward', action_name= 'ac_l2_forward', 
                                                    match_keys= f'{node_swarm_mac}', action_params= str(node_swarm_id),
                                                    thrift_ip= ap_ip, thrift_port= DEFAULT_THRIFT_PORT)
        
        # bmv2_thrift.delete_forwarding_entry_from_bmv2(
        #     communication_protocol= bmv2_thrift.P4_CONTROL_METHOD_THRIFT_CLI, table_name='MyIngress.tb_swarm_control', key= f'{node_swarm_id} {global_config.coordinator_vip}',
        #     thrift_ip= ap_ip, thrift_port= DEFAULT_THRIFT_PORT)

        # bmv2_thrift.delete_forwarding_entry_from_bmv2(
        #     communication_protocol= bmv2_thrift.P4_CONTROL_METHOD_THRIFT_CLI, table_name= 'MyIngress.tb_swarm_control', 
        #     key= f'{global_config.swarm_backbone_switch_port} {node_swarm_ip}', thrift_ip= ap_ip, thrift_port=DEFAULT_THRIFT_PORT)
        
        
        # insert table entries in the rest of the APs
        for key in global_config.ap_list.keys():
            if key != node_swarm_ap:
                entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                                                    table_name='MyIngress.tb_ipv4_lpm',
                        action_name='MyIngress.ac_ipv4_forward_mac_from_dst_ip', match_keys=f'{node_swarm_ip}/32' , 
                        action_params= f'{global_config.swarm_backbone_switch_port}', thrift_ip= global_config.ap_list[key][0], thrift_port= DEFAULT_THRIFT_PORT )
                
                entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
                                        table_name='MyIngress.tb_l2_forward', action_name= 'ac_l2_forward', 
                                        match_keys= f'{node_swarm_mac}', action_params= str(global_config.swarm_backbone_switch_port),
                                        thrift_ip= global_config.ap_list[key][0], thrift_port= DEFAULT_THRIFT_PORT)
                    
                                
        self.node_socket.send( bytes( f'{req_id} accepted'.encode() ) )

# a function to configure the keep alive of the tcp connection
def set_keepalive_linux(sock, after_idle_sec=1, interval_sec=3, max_fails=5):
    """Set TCP keepalive on an open socket.

    It activates after 1 second (after_idle_sec) of idleness,
    then sends a keepalive ping once every 3 seconds (interval_sec),
    and closes the connection after 5 failed ping (max_fails), or 15 seconds
    """
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, after_idle_sec)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval_sec)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, max_fails)



def handle_swarm_node(node_socket, address):
    try:
        message = node_socket.recv(1024).decode()
        print(f'received: {message} from {address}')    
        
        message_handler = Swarm_Node_Handler(message= message, node_socket=node_socket)
        message_handler.handle_message()
    except Exception as e:
        print(e)


# receives TCP connections from swarm nodes
def swarm_coordinator():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serversocket:
        serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serversocket.bind(SWARM_NODE_TCP_SERVER)
        set_keepalive_linux(sock= serversocket, after_idle_sec=1, interval_sec=3, max_fails= 5)
        serversocket.listen(COORDINATOR_MAX_TCP_CONNNECTIONS)
        print('Coordinator Script is Running')
        while True:
            (node_socket, address) = serversocket.accept()
            print(f'received connection request from {address}')
            threading.Thread(target=handle_swarm_node, args=(node_socket, address, ), daemon= True ).start()

def set_arps():
    for host_id in range(global_config.this_swarm_dhcp_start, global_config.this_swarm_dhcp_end + 1):
        station_virtual_ip_address = str( THIS_SWARM_SUBNET + host_id )
        station_virtual_mac_address = int_to_mac(int( THIS_SWARM_SUBNET + host_id ))
        cli_command = f'arp -s {station_virtual_ip_address} {station_virtual_mac_address}'
        subprocess.run(cli_command.split(), text=True)

def main():
    # set_arps()
    logger.debug('Coordinator Starting')
    print('Starting Coordinator')
    swarm_coordinator()
    # threading.Thread(target=ap_server).start()
    # threading.Thread(target=swarm_coordinator, daemon= True).start()
    return 0 

if __name__ == "__main__":
    main()
