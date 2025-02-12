#!/usr/bin/python3
# This tells python to look for files in parent directory
import sys
import subprocess
import queue


# setting path
sys.path.append('..')
sys.path.append('.')

import lib.global_config as global_config
import ipaddress
import socket
import re
import os
import logging
import ipaddress
import json
import threading
import lib.bmv2_thrift_lib as bmv2
import lib.database_comms as db_comms
import lib.global_constants as cts
from argparse import ArgumentParser

STRs = cts.String_Constants

def int_to_mac(macint):
    if type(macint) != int:
        raise ValueError('invalid integer')
    return ':'.join(['{}{}'.format(a, b)
                     for a, b
                     in zip(*[iter('{:012x}'.format(macint ))]*2)])  # + 2199023255552



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

thread_q = queue.Queue()

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
def add_bmv2_swarm_broadcast_port_to_ap(ap_ip, thrift_port, switch_port ):
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
        logger.debug(f'\nNew Request: {message} ')
        self.node_request = json.loads(message)
        self.node_socket = node_socket

        
    def user_input_respond_to_node_request(self):
        user_input = -1
        while True:
            try:
                user_input = int( input("Enter 1 to Accept the request, 0 for Reject: ") )
            except Exception as e:
                print("Input Error")
                print(e)
                continue
            if (user_input == 1 or user_input == 0):
                return user_input
            else:
                print('Wrong Input')
                
        
    def handle_message(self):
        logger.debug(f"Handling Request with type {self.node_request[STRs.TYPE]}")
        match self.node_request[STRs.TYPE]:
            case STRs.JOIN_REQUEST_00:
                logger.debug(f"Handling Request with type {STRs.JOIN_REQUEST_00.name}")
                ret_val = self.user_input_respond_to_node_request()
                if ret_val == 1:
                    self.accept_join_request()
                else:
                    self.reject_join_request()
                    
            case 'Node_Left_AP':
                pass
            
            case STRs.LEAVE_REQUEST:
                ret_val = self.user_input_respond_to_node_request()
                if ret_val == 1:
                    self.node_socket.send( bytes( f'Accepted: {self.message}'.encode() ) )
                    db_comms.delete_node_from_swarm_database(self.node_swarm_id)
                else:
                    self.node_socket.send( bytes( f'Rejected: {self.message}'.encode() ) )
                    
            case _:
                pass
            
    def reject_join_request(self):
        db_comms.delete_node_from_swarm_database(self.node_swarm_id)
        self.node_socket.send( bytes( f'Rejected: {self.req_id}'.encode() ) )
        print(f'Rejected node {self.node_uuid} with request {self.req_id}')
        
        
        
    def accept_join_request(self):
        # TODO: make this automatic
        # first we get the ip of the access point from the ap list
        ap_ip = get_ap_ip_from_ap_id(self.node_swarm_ap)
        if (ap_ip == None):
            logger.error(f'Error: could not find IP of access point {self.node_swarm_ap}')
            return
    
        db_comms.update_db_with_joined_node(self.node_uuid, self.node_swarm_id)
                    
        add_bmv2_swarm_broadcast_port_to_ap(ap_ip= ap_ip, thrift_port=DEFAULT_THRIFT_PORT, switch_port= self.node_swarm_id)

        entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                                                    table_name='MyIngress.tb_ipv4_lpm',
            action_name='MyIngress.ac_ipv4_forward_mac_from_dst_ip', match_keys=f'{self.node_swarm_ip}/32' , 
            action_params= f'{str(self.node_swarm_id)}', thrift_ip= ap_ip, thrift_port= DEFAULT_THRIFT_PORT )
     
        # entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
        #                                             table_name='MyIngress.tb_l2_forward', action_name= 'ac_l2_forward', 
        #                                             match_keys= f'{node_swarm_mac}', action_params= str(node_swarm_id),
        #                                             thrift_ip= ap_ip, thrift_port= DEFAULT_THRIFT_PORT)
        
        # bmv2.delete_forwarding_entry_from_bmv2(
        #     communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, table_name='MyIngress.tb_swarm_control', key= f'{node_swarm_id} {global_config.coordinator_vip}',
        #     thrift_ip= ap_ip, thrift_port= DEFAULT_THRIFT_PORT)

        # bmv2.delete_forwarding_entry_from_bmv2(
        #     communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, table_name= 'MyIngress.tb_swarm_control', 
        #     key= f'{global_config.swarm_backbone_switch_port} {self.node_swarm_ip}', thrift_ip= ap_ip, thrift_port=DEFAULT_THRIFT_PORT)
        
        
        # insert table entries in the rest of the APs
        node_ap_ip = global_config.ap_list[self.node_swarm_ap][0]
        for key in global_config.ap_list.keys():
            if key != self.node_swarm_ap:
                ap_ip = global_config.ap_list[key][0]
                ap_mac = int_to_mac( int(ipaddress.ip_address(node_ap_ip)) )
                entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                                                    table_name='MyIngress.tb_ipv4_lpm',
                        action_name='MyIngress.ac_ipv4_forward_mac', match_keys=f'{self.node_swarm_ip}/32' , 
                        action_params= f'{global_config.swarm_backbone_switch_port} {ap_mac}', thrift_ip= ap_ip, thrift_port= DEFAULT_THRIFT_PORT )
                
                # entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
                #                         table_name='MyIngress.tb_l2_forward', action_name= 'ac_l2_forward', 
                #                         match_keys= f'{node_swarm_mac}', action_params= str(global_config.swarm_backbone_switch_port),
                #                         thrift_ip= global_config.ap_list[key][0], thrift_port= DEFAULT_THRIFT_PORT)
                    
                                
        self.node_socket.send( bytes( f'Accepted: {self.req_id}'.encode() ) )
        print(f'Accepted node {self.node_uuid} with request {self.req_id}')
         


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
        logger.debug(f'received: {message} from {address}')    
        
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
            logger.debug(f'received connection request from {address}')
            handle_swarm_node(node_socket=node_socket, address=address)
            # threading.Thread(target=handle_swarm_node, args=(node_socket, address, ), daemon= True ).start()


def main():
    # set_arps()
    logger.debug('Coordinator Starting')
    print('Starting Coordinator')
    swarm_coordinator()

    return 0 

if __name__ == "__main__":
    main()
