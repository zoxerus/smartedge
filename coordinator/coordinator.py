#!/usr/bin/python3
# This tells python to look for files in parent directory
import sys
import subprocess
import queue


# setting path
sys.path.append('..')
sys.path.append('.')

import lib.global_config as cfg
import ipaddress
import socket
import re
import os
import logging
import ipaddress
import json
import threading
import lib.bmv2_thrift_lib as bmv2
import lib.database_comms as db
import lib.global_constants as cts
from lib.helper_functions import *
from argparse import ArgumentParser

STRs = cts.String_Constants

parser = ArgumentParser()
parser.add_argument("-l", "--log-level",type=int, default=50, help="set logging level [10, 20, 30, 40, 50]")
parser.add_argument("-n", "--num-id",type=int, default=50, help="sequential uniq numeric id for node identification")
args = parser.parse_args()





dir_path = os.path.dirname(os.path.realpath(__file__))


# where to store program logs
PROGRAM_LOG_FILE_NAME = './logs/coordinator.log'
os.makedirs(os.path.dirname(PROGRAM_LOG_FILE_NAME), exist_ok=True)
logger = logging.getLogger('coordinator_logger')
# this part handles logging to console and to a file for debugging purposes
log_formatter = logging.Formatter("Line:%(lineno)d at %(asctime)s [%(levelname)s] Thread: %(threadName)s File: %(filename)s :\n%(message)s\n")

# log_file_handler = logging.FileHandler(PROGRAM_LOG_FILE_NAME, mode='w')
# log_file_handler.setLevel(args.log_level)
# log_file_handler.setFormatter(log_formatter)

log_console_handler = logging.StreamHandler(sys.stdout)
log_console_handler.setLevel(args.log_level)
log_console_handler.setFormatter(log_formatter)
logger.setLevel(args.log_level)    
# logger.addHandler(log_file_handler)
logger.addHandler(log_console_handler)

logger.debug(f'Running in: {dir_path}')

db.db_logger = logger
bmv2.bmv2_logger = logger

thread_q = queue.Queue()

# TCP related
COORDINATOR_MAX_TCP_CONNNECTIONS = 5

# TODO: delete this
SWARM_NODE_TCP_SERVER = ('', 29997) 


DEFAULT_THRIFT_PORT = bmv2.DEFAULT_THRIFT_PORT

THIS_SWARM_SUBNET=ipaddress.ip_address( cfg.this_swarm_subnet )

db.DATABASE_IN_USE = db.STR_DATABASE_TYPE_CASSANDRA

database_session = db.init_database('0.0.0.0', cfg.database_port)
db.DATABASE_SESSION = database_session

# a function to parse a string and extract integers
# needed for interactiosn with bmv2


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
        return cfg.ap_list[ap_id][0]
    except:
        return None
    
    

class Swarm_Node_Handler:
    def __init__(self, message, node_socket: socket.socket):
        logger.debug(f'\nNew Request: {message} ')
        self.node_request = json.loads(message)
        self.node_socket = node_socket

        
    def user_input_respond_to_node_request(self):
        while True:
            user_input = input("Enter 1 to Accept the request, 0 for Reject: ") 
            if (user_input == '1' or user_input == '0'):
                print('Accepting the node')
                return user_input
            else:
                print('Wrong Input')
                
        
    def handle_message(self):
        logger.debug(f"Handling Request with type {self.node_request[STRs.TYPE.name]}")
        match self.node_request[STRs.TYPE.name]:
            case STRs.JOIN_REQUEST.name:
                logger.debug(f"Handling Request with type {STRs.JOIN_REQUEST.name}")
                self.accept_join_request()
                    
            case 'Node_Left_AP':
                pass
            
            case STRs.LEAVE_REQUEST.name:
                ret_val = self.user_input_respond_to_node_request()
                if ret_val == 1:
                    pass
                    # self.node_socket.send( bytes( f'Accepted: {self.message}'.encode() ) )
                    # db.delete_node_from_swarm_database(self.node_swarm_id)
                else:
                    self.node_socket.send( bytes( f'Rejected: {self.message}'.encode() ) )
                    
            case _:
                logger.debug(f"Request Type Unkown {self.node_request[STRs.TYPE.name]}")
            
    def reject_join_request(self):
        pass
        #TODO
        # db.delete_node_from_swarm_database(self.node_swarm_id)
        # self.node_socket.send( bytes( f'Rejected: {self.req_id}'.encode() ) )
        # print(f'Rejected node {self.node_uuid} with request {self.req_id}')
        
        
        
    def accept_join_request(self):
        # TODO: make this automatic

        SN_UUID = self.node_request[STRs.NODE_UUID.name]
        
        logger.debug(f'Accecpted Node {SN_UUID} in Swarm')
        
        # first we get the ip of the access point from the ap list
        ap_ip = get_ap_ip_from_ap_id(self.node_request[STRs.AP_UUID.name] )
        if (ap_ip == None):
            logger.error(f'Error: could not find IP of access point {self.node_request[STRs.AP_UUID.name]}')
            return
        
        
        host_id = db.get_next_available_host_id_from_swarm_table(first_host_id=cfg.this_swarm_dhcp_start,
                    max_host_id=cfg.this_swarm_dhcp_end, uuid=SN_UUID)
        
        result = assign_virtual_mac_and_ip_by_host_id(subnet= THIS_SWARM_SUBNET, host_id=host_id)
        
        station_vmac= result[0]
        station_vip = result[1]
        
        logger.debug(f'assigning vIP: {station_vip} vMAC: {station_vmac} to {SN_UUID}')
        swarmNode_config = {
            STRs.TYPE.name: STRs.JOIN_REQUEST.name,
            STRs.VETH1_VIP.name: station_vip,
            STRs.VETH1_VMAC.name: station_vmac,
            STRs.VXLAN_ID.name: self.node_request[STRs.VXLAN_ID.name],
            STRs.SWARM_ID.name: 1,
            STRs.COORDINATOR_VIP.name: cfg.coordinator_vip,
            STRs.COORDINATOR_TCP_PORT.name: cfg.coordinator_tcp_port
        }
        config_message = json.dumps(swarmNode_config)
        
        logger.debug(f'Sending {config_message}')
        try:    
            self.node_socket.sendall( bytes( config_message.encode() ) )
            logger.debug(f'Accepted node {SN_UUID} with request {self.node_request[STRs.REQUIST_ID.name]}')
        except Exception as e:
            logger.error(f"Error Sending confing to Node {SN_UUID}: {repr(e)}")
            return 
        
        
        db.insert_node_into_swarm_database(host_id=host_id, this_ap_id=self.node_request[STRs.AP_UUID.name],
                                           node_vip= station_vip, node_vmac= station_vmac, node_phy_mac='',
                                           node_uuid=SN_UUID, status=db.db_defines.SWARM_STATUS.JOINED.value)
        
        db.update_art_with_node_info(uuid=SN_UUID,node_current_ap=self.node_request[STRs.AP_UUID.name],
                                     node_current_swarm=1,node_current_ip=station_vip)
                    
        add_bmv2_swarm_broadcast_port_to_ap(ap_ip= ap_ip, thrift_port=DEFAULT_THRIFT_PORT, switch_port= self.node_request[STRs.VXLAN_ID.name])

        entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                                                    table_name='MyIngress.tb_ipv4_lpm',
            action_name='MyIngress.ac_ipv4_forward_mac_from_dst_ip', match_keys=f'{station_vip}/32' , 
            action_params= str(host_id), thrift_ip= ap_ip, thrift_port= DEFAULT_THRIFT_PORT )
     
        # entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
        #                                             table_name='MyIngress.tb_l2_forward', action_name= 'ac_l2_forward', 
        #                                             match_keys= f'{node_swarm_mac}', action_params= str(node_swarm_id),
        #                                             thrift_ip= ap_ip, thrift_port= DEFAULT_THRIFT_PORT)
        
        # bmv2.delete_forwarding_entry_from_bmv2(
        #     communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, table_name='MyIngress.tb_swarm_control', key= f'{node_swarm_id} {cfg.coordinator_vip}',
        #     thrift_ip= ap_ip, thrift_port= DEFAULT_THRIFT_PORT)

        # bmv2.delete_forwarding_entry_from_bmv2(
        #     communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, table_name= 'MyIngress.tb_swarm_control', 
        #     key= f'{cfg.swarm_backbone_switch_port} {self.node_swarm_ip}', thrift_ip= ap_ip, thrift_port=DEFAULT_THRIFT_PORT)
        
        
        # insert table entries in the rest of the APs
        node_ap_ip = cfg.ap_list[self.node_request[STRs.AP_UUID.name]][0]
        for key in cfg.ap_list.keys():
            if key != self.node_request[STRs.AP_UUID.name]:
                ap_ip = cfg.ap_list[key][0]
                ap_mac = int_to_mac( int(ipaddress.ip_address(node_ap_ip)) )
                entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                                                    table_name='MyIngress.tb_ipv4_lpm',
                        action_name='MyIngress.ac_ipv4_forward_mac', match_keys=f'{station_vip}/32' , 
                        action_params= f'{cfg.swarm_backbone_switch_port} {ap_mac}', thrift_ip= ap_ip, thrift_port= DEFAULT_THRIFT_PORT )
                
                # entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
                #                         table_name='MyIngress.tb_l2_forward', action_name= 'ac_l2_forward', 
                #                         match_keys= f'{node_swarm_mac}', action_params= str(cfg.swarm_backbone_switch_port),
                #                         thrift_ip= cfg.ap_list[key][0], thrift_port= DEFAULT_THRIFT_PORT)
         





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
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print(f"Exception Type: {exc_type.__name__}")
        print(f"File: {exc_tb.tb_frame.f_code.co_filename}")
        print(f"Line Number: {exc_tb.tb_lineno}")
        logger.error(f'Error Handling swarm Node {address}: {e}')
        
 

# receives TCP connections from swarm nodes
def swarm_coordinator():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serversocket:
        serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serversocket.bind(SWARM_NODE_TCP_SERVER)
        set_keepalive_linux(sock= serversocket, after_idle_sec=1, interval_sec=3, max_fails= 5)
        serversocket.listen(COORDINATOR_MAX_TCP_CONNNECTIONS)
        print('Coordinator Script is Running')
        while True:
            logger.debug(f'Waiting for Requests ... ')
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
