# This tells python to look for files in parent folders
import sys
# setting path
sys.path.append('.')
sys.path.append('..')
sys.path.append('../..')

import subprocess
import logging
import threading
import socket
import atexit
import time
import ipaddress
import lib.global_config as cfg
import psutil
import sys
import lib.database_comms as db
import lib.bmv2_thrift_lib as bmv2
import os
import asyncio
import lib.global_constants as cts
from lib.helper_functions import *
import json
import concurrent.futures

from argparse import ArgumentParser

STRs = cts.String_Constants


parser = ArgumentParser()
parser.add_argument("-l", "--log-level",type=int, default=50, help="logging level")
# parser.add_argument("-l", "--log-file",type=int, default=50, help="logging level")
args = parser.parse_args()


dir_path = os.path.dirname(os.path.realpath(__file__))

# this part handles logging to console and to a file for debugging purposes
# where to store program logs
PROGRAM_LOG_FILE_NAME = './logs/ap.log'
os.makedirs(os.path.dirname(PROGRAM_LOG_FILE_NAME), exist_ok=True)
logger = logging.getLogger('ap_logger')
client_monitor_log_formatter = logging.Formatter("\n\nLine:%(lineno)d at %(asctime)s [%(levelname)s] %(filename)s :\n\t %(message)s \n\n")

client_monitor_log_file_handler = logging.FileHandler(PROGRAM_LOG_FILE_NAME, mode='w')
client_monitor_log_file_handler.setLevel(args.log_level)
client_monitor_log_file_handler.setFormatter(client_monitor_log_formatter)

client_monitor_log_console_handler = logging.StreamHandler(sys.stdout)
client_monitor_log_console_handler.setLevel(args.log_level)
client_monitor_log_console_handler.setFormatter(client_monitor_log_formatter)

logger.setLevel(args.log_level)    
logger.addHandler(client_monitor_log_file_handler)
logger.addHandler(client_monitor_log_console_handler)
db.db_logger = logger
bmv2.bmv2_logger = logger
logger.debug(f'running in: {dir_path}')



# a global variable to set the communication protocol with the switch
P4CTRL = bmv2.P4_CONTROL_METHOD_THRIFT_CLI
# Set which database the program is going to use

INDEX_IW_EVENT_MAC_ADDRESS = 3
INDEX_IW_EVENT_ACTION = 1 

IW_TOOL_JOINED_STATION_EVENT = 'new'
IW_TOOL_LEFT_STATION_EVENT = 'del'

# read the swarm subnet from the config file
# TODO: make this configurable by coordinator
THIS_SWARM_SUBNET=ipaddress.ip_address( cfg.this_swarm_subnet )
DEFAULT_SUBNET=ipaddress.ip_address(cfg.default_subnet)


# a variable to track created host ids
# TODO: have a database table for this
# current_host_id = config.this_swarm_dhcp_start
created_vxlans = set([])


SWARM_P4_MC_NODE = 1100
SWARM_P4_MC_GROUP = 1000


# a list to keep track of connected stations to current AP
connected_stations = {}


CONNECTED_STATIONS_VMAC_INDEX = 0
CONNECTED_STATIONS_VIP_INDEX = 1
CONNECTED_STATION_VXLAN_INDEX = 2

DEFAULT_WLAN_DEVICE_NAME= cfg.default_wlan_device

loopback_if = 'lo:0'

db.DATABASE_IN_USE = db.STR_DATABASE_TYPE_CASSANDRA
database_session = db.connect_to_database(cfg.database_hostname, cfg.database_port)
db.DATABASE_SESSION = database_session


THIS_AP_UUID = None
for snic in psutil.net_if_addrs()[loopback_if]:
    if snic.family == socket.AF_INET:        
        temp_mac = int_to_mac(int(ipaddress.ip_address(snic.address) -1 ))
        THIS_AP_UUID = f'AP:{temp_mac[9:]}'
if THIS_AP_UUID == None:
    logger.error("Could not Assign UUID to Node")
    exit()
logger.debug(f"AP ID: {THIS_AP_UUID}" )

THIS_AP_ETH_MAC = None
for snic in psutil.net_if_addrs()[cfg.default_backbone_device]:
    if snic.family == psutil.AF_LINK:        
        THIS_AP_ETH_MAC = snic.address
if THIS_AP_ETH_MAC == None:
    logger.error("Could not Connect to backbone, check eth device name in the config file")
    exit()

THIS_AP_WLAN_MAC = None
for snic in psutil.net_if_addrs()[cfg.default_wlan_device]:
    if snic.family == psutil.AF_LINK:        
        THIS_AP_WLAN_MAC = snic.address
if THIS_AP_WLAN_MAC == None:
    logger.error("Could not Connect to backbone, check eth device name in the config file")
    exit()
                         
def initialize_program():    
    # remvoe all configureation from bmv2, start fresh
    bmv2.send_cli_command_to_bmv2(cli_command="reset_state")

    # attach the backbone interface to the bmv2
    bmv2.send_cli_command_to_bmv2(cli_command=f"port_remove {cfg.swarm_backbone_switch_port}")
    bmv2.send_cli_command_to_bmv2(cli_command=f"port_add {cfg.default_backbone_device} {cfg.swarm_backbone_switch_port}")
    
    entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                                            table_name='MyIngress.tb_ipv4_lpm',
    action_name='MyIngress.ac_ipv4_forward', match_keys=f'{cfg.coordinator_vip}/32' , 
    action_params= f'{cfg.swarm_backbone_switch_port}')
    
    # handle broadcast
    bmv2.send_cli_command_to_bmv2(cli_command=f"mc_mgrp_create {SWARM_P4_MC_GROUP}")
    bmv2.send_cli_command_to_bmv2(cli_command=f"mc_node_create {SWARM_P4_MC_NODE} {cfg.swarm_backbone_switch_port}")
    bmv2.send_cli_command_to_bmv2(cli_command=f"mc_node_associate {SWARM_P4_MC_GROUP} 0")
    bmv2.send_cli_command_to_bmv2(cli_command=f"table_add MyIngress.tb_l2_forward ac_l2_broadcast 01:00:00:00:00:00&&&0x010000000000 => {SWARM_P4_MC_GROUP} 100 ")
    
    logger.debug('Program Initialized')
    print('AP Started')

# a handler to clean exit the programs
def exit_handler():
    pass
    # logger.debug('Handling exit')
    # logger.debug(f'Created vxlan ids: {created_vxlans}') 
               
    # # delete any created vxlans during the program lifetime
    # for vxlan_id in created_vxlans:
    #     try:
    #         delete_vxlan_shell_command = "ip link del se_vxlan%s" % vxlan_id
    #         result = subprocess.run(delete_vxlan_shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
    #         db.delete_node_from_swarm_database(node_swarm_id= vxlan_id)
    #         logger.debug(f'deleted vxlan{vxlan_id},\n\t feedback: \n {result.stdout.strip() }')
    #     except Exception as e:
    #         logger.error(repr(e))








# a function for sending the configuration to the swarm node
# this connects to the TCP server running in the swarm node and sends the configuration as a string
def send_swarmNode_config(config_messge, node_socket_server_address):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as node_socket_client:
        try:
            node_socket_client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            node_socket_client.settimeout(10)
            node_socket_client.connect(node_socket_server_address)
            node_socket_client.sendall( bytes( config_messge.encode() ))
            response = node_socket_client.recv(1024).decode()
            if response == "OK!":
                return 1
            return -1 
        except Exception as e:
            logger.error(f'Error sending config to {node_socket_server_address}: {e}')
            return -1
    logger.debug(f'AP has sent this config to the Smart Node:\n\t {config_messge}')




def create_vxlan_by_host_id(vxlan_id, remote, port=4789): 
    logger.debug(f'Adding se_vxlan{vxlan_id}')
    
    add_vxlan_shell_command = "ip link add se_vxlan%s type vxlan id %s dev %s remote %s dstport %s" % (
        vxlan_id, vxlan_id, DEFAULT_WLAN_DEVICE_NAME, remote, port)

    result = subprocess.run(add_vxlan_shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if (result.stderr):
        logger.error(f'\nCould not create se_vxlan{vxlan_id}:\n\t {result.stderr}')
        return -1
    
    logger.debug(f'\nCreated se_vxlan{vxlan_id}')
    created_vxlans.add(vxlan_id)
    
    logger.debug(f'\ncreated_vxlans:\n\t {created_vxlans}')            
    activate_interface_shell_command = "ip link set se_vxlan%s up" % vxlan_id
    result = subprocess.run(activate_interface_shell_command.split(), text=True , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if (result.stderr):
        logger.error(f'\nCould not activate interface se_vxlan{vxlan_id}:\n\t {result.stderr}')
        return -1
    logger.debug(f'\nActivated interface se_vxlan{vxlan_id}')
    return vxlan_id
        

def delete_vxlan_by_host_id(host_id):
    logger.debug(f'\nDeleting se_vxlan{host_id}')
    delete_vxlan_shell_command = "ip link del se_vxlan%s" % (host_id)
    result = subprocess.run(delete_vxlan_shell_command.split(), text=True , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if (result.stderr):
        logger.error(f'\ncould not delete se_vxlan{host_id}:\n\t {result.stderr}')
        return
    created_vxlans.remove(host_id)
    logger.debug(f'\nCreated host IDs: {created_vxlans}')


def get_mac_from_arp_by_physical_ip(ip):
    shell_command = "arp -en"
    result = subprocess.run( shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if (result.stderr):
        logger.error(f'\nCould run arp for {ip}:\n\t {result.stderr}')
        return

    for line in result.stdout.strip().splitlines():
        if ip in line:
            return line.split()[2]
    logger.error(f'\nMAC not found in ARP for {ip}')
    return None



def get_ip_from_arp_by_physical_mac(physical_mac):
    shell_command = "arp -en"
    t0 = time.time()
    while time.time() - t0 < 5:
        result = subprocess.run( shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if (result.stderr):
            logger.error(f'\nCould not run arp for {physical_mac}:\n\t {result.stderr}')
            return
        for line in result.stdout.strip().splitlines():
            if physical_mac in line and DEFAULT_WLAN_DEVICE_NAME in line:
                ip = line.split()[0]
                logger.debug(f'\nIP {ip} was found in ARP for {physical_mac} after {time.time() - t0} Seconds')                
                return ip
 

def get_next_available_vxlan_id():
    shell_command = "ip -d link show | awk '/vxlan id/ {print $3}' "
    process_ret = subprocess.run(shell_command, text=True, shell=True, stdout=subprocess.PIPE )
    id_list_str = process_ret.stdout
    id_list = list(map(int, id_list_str.split()))
    result = min(set(range(1, 500 )) - set(id_list)) 
    return result 


async def handle_new_connected_station(station_physical_mac_address):
    logger.debug(f"handling newly connected staion {station_physical_mac_address}")
    
    
    # First Step check if node is already in the Connected Nodes 
    # sometimes an already connected station is randomly detected as connecting again, 
    # this check skips the execution of the rest of the code, as the station is already connected and set up.
    if (station_physical_mac_address in connected_stations.keys() ):
        logger.warning(f'\nStation {station_physical_mac_address} Connected to {THIS_AP_UUID} but was found already in Connected Stations')
        return
    
    # get the IP of the node from its mac address from the ARP table
    station_physical_ip_address = get_ip_from_arp_by_physical_mac(station_physical_mac_address)
    if (station_physical_ip_address == None ):
        logger.error(f'\nIP not found in ARP for {station_physical_mac_address}. Aborting the handling of the node')
        return
    logger.debug( f'\nHandling New Station: {station_physical_mac_address} {station_physical_ip_address} at {time.ctime(time.time())}')
    
    # 2nd Step: Check if Node belong to a Swarm or Not
    # to do so we first read the UUID (bottom three bytes of MAC address)
    SN_UUID = 'SN:' + station_physical_mac_address[9:]
    
    # # Then we search the ART  to see if the node is present in there
    node_db_result = db.get_node_info_from_art(node_uuid=SN_UUID)
    node_info = node_db_result.one()
    
    # # in case the node is not present in the ART
    if (node_db_result == None or node_info.node_current_swarm == 0):
        logger.debug(f'node_db_result == None or node_info.node_current_swarm == 0 for {SN_UUID}')
        
        command = f"ip -d link show | awk '/remote {station_physical_ip_address}/ {{print $3}}' "
        proc_ret = subprocess.run(command, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        vxlan_id = -1
        if (proc_ret.stdout == '' ):
            next_vxlan_id = get_next_available_vxlan_id()
            vxlan_id = create_vxlan_by_host_id( vxlan_id= next_vxlan_id, remote= station_physical_ip_address )
        else:
            vxlan_id = int(proc_ret.stdout)
        if (vxlan_id == -1):
            logger.error(f"Something wrong with assigning vxlan to {SN_UUID} ")
            return
        
        dettach_vxlan_from_bmv2_command = "port_remove %s" % (vxlan_id)
        bmv2.send_cli_command_to_bmv2(cli_command=dettach_vxlan_from_bmv2_command)
        
        attach_vxlan_to_bmv2_command = "port_add se_vxlan%s %s" % (vxlan_id, vxlan_id)
        bmv2.send_cli_command_to_bmv2(cli_command=attach_vxlan_to_bmv2_command)
        
        node_s0_ip = str(DEFAULT_SUBNET).split('.')[:3]
        node_s0_ip.append(station_physical_ip_address.split('.')[3])
        node_s0_ip = '.'.join(node_s0_ip)      
        
        node_s0_mac = int_to_mac(int( ipaddress.ip_address(node_s0_ip) ))
        
        swarmNode_config = {
            STRs.TYPE: STRs.JOIN_REQUEST_00.value,
            STRs.VETH1_VIP: node_s0_ip,
            STRs.VETH1_VMAC: node_s0_mac,
            STRs.VXLAN_ID: vxlan_id,
            STRs.SWARM_ID: 0,
            STRs.COORDINATOR_VIP: cfg.coordinator_phyip,
            STRs.COORDINATOR_TCP_PORT: cfg.coordinator_tcp_port,
            STRs.THIS_NODE_APID: THIS_AP_UUID
        }
        
        swarmNode_config_message = json.dumps(swarmNode_config)   
        result = send_swarmNode_config(swarmNode_config_message, (station_physical_ip_address, cfg.node_manager_tcp_port) )
        if (result == -1): # Node faild to configure itself
            logger.error(f'Smart Node {station_physical_ip_address} could not handle config:\n{swarmNode_config_message}')
            return
        connected_stations[station_physical_mac_address] = [ station_physical_mac_address ,node_s0_ip, vxlan_id]
        logger.debug(f"Connected Stations List after Adding {station_physical_mac_address}: {connected_stations}")

        
        # with concurrent.futures.ThreadPoolExecutor() as executor:
        #     future = executor.submit(send_swarmNode_config, swarmNode_config_message )  # Run function in thread
        #     result = future.result()  # Get the return value
            
        #     if (result == -1): # Node faild to configure itself
        #         logger.error(f'Smart Node {station_physical_ip_address} could not handle config:\n{swarmNode_config_message}')
        #         return
            
            
        db.insert_into_art(node_uuid=SN_UUID, current_ap=THIS_AP_UUID, swarm_id=0, ap_port=vxlan_id, node_ip=node_s0_ip)
        
        # TODO: verify if bmv2 is updated correctly 
        entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                            table_name='MyIngress.tb_ipv4_lpm',
                            action_name='MyIngress.ac_ipv4_forward_mac_from_dst_ip', match_keys=f'{node_s0_ip}/32' , 
                            action_params= f'{str(vxlan_id)}')
     
        node_ap_ip = cfg.ap_list[THIS_AP_UUID][0]
        for key in cfg.ap_list.keys():
            if key != THIS_AP_UUID:
                ap_ip = cfg.ap_list[key][0]
                ap_mac = int_to_mac( int(ipaddress.ip_address(node_ap_ip)) )
                entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                        table_name='MyIngress.tb_ipv4_lpm',
                        action_name='MyIngress.ac_ipv4_forward_mac', match_keys=f'{node_s0_ip}/32' , 
                        action_params= f'{cfg.swarm_backbone_switch_port} {ap_mac}', thrift_ip= ap_ip, thrift_port= bmv2.DEFAULT_THRIFT_PORT )
            

        
    else :
        logger.debug(f'node {SN_UUID} is part of swarm {node_info.node_current_swarm}')
        command = f"ip -d link show | awk '/remote {station_physical_ip_address}/ {{print $5}}' "
        proc_ret = subprocess.run(command, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if (proc_ret.stdout == '' ):
            next_vxlan_id = get_next_available_vxlan_id()
            vxlan_id = create_vxlan_by_host_id( vxlan_id= next_vxlan_id, remote= station_physical_ip_address )
            if (vxlan_id == -1):
                return
            
        host_id = db.get_next_available_host_id_from_swarm_table(first_host_id=cfg.this_swarm_dhcp_start,
                    max_host_id=cfg.this_swarm_dhcp_end, uuid=SN_UUID)
        
        result = assign_virtual_mac_and_ip_by_host_id(subnet= THIS_SWARM_SUBNET, host_id=host_id)
        station_vmac= result[0]
        station_vip = result[1]
        
        logger.debug( f'\nAssigned Station\'s Virtual IP: {station_vip}' )
        logger.debug( f'\nAssigned Station\'s Virtual MAC: {station_vmac}')
        
        logger.debug( f'\nStation {station_physical_mac_address}\t{station_physical_ip_address}\n\t' +  
                    f'assigned vIP: {station_vip} and vMAC: {station_vmac}')
        
        
        
        swarmNode_config = {
            STRs.TYPE: STRs.JOIN_REQUEST_01,
            STRs.VETH1_VIP: station_vip,
            STRs.VETH1_VMAC: station_vmac,
            STRs.VXLAN_ID: vxlan_id,
            STRs.COORDINATOR_VIP: cfg.coordinator_vip,
            STRs.COORDINATOR_TCP_PORT: cfg.coordinator_tcp_port,
            STRs.AP_ID: THIS_AP_UUID
        }
        
        swarmNode_config_message = json.dumps(swarmNode_config)
        result = send_swarmNode_config(swarmNode_config_message, station_physical_ip_address )
        if (result == -1): # Node faild to configure itself
            logger.error(f'Smart Node {station_physical_ip_address} could not handle config:\n{swarmNode_config_message}')
            return
            
        # swarmNode_config_message = f'setConfig_01 {station_vip} {station_vmac} {vxlan_id} {cfg.coordinator_phyip} {cfg.coordinator_tcp_port} {THIS_AP_UUID}'
        # with concurrent.futures.ThreadPoolExecutor() as executor:
        #     future = executor.submit(send_swarmNode_config, swarmNode_config_message )  # Run function in thread
        #     result = future.result()  # Get the return value
            
        #     if (result == -1): # Node faild to configure itself
        #         logger.error(f'Smart Node {station_physical_ip_address} could not handle config:\n{swarmNode_config_message}')
        #         return
        # TODO: update the bmv2 
        db.insert_into_art(node_uuid=SN_UUID, current_ap=THIS_AP_UUID, swarm_id=0, ap_port=vxlan_id, node_ip=node_s0_ip)
        db.insert_node_into_swarm_database(this_ap_id= THIS_AP_UUID,
                                        host_id=host_id, node_vip=station_vip, node_vmac=station_vmac, 
                                        node_phy_mac=station_physical_mac_address)
        
        entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                            table_name='MyIngress.tb_ipv4_lpm',
                            action_name='MyIngress.ac_ipv4_forward_mac_from_dst_ip', match_keys=f'{station_vip}/32' , 
                            action_params= f'{str(vxlan_id)}', thrift_ip= ap_ip, thrift_port= bmv2.DEFAULT_THRIFT_PORT )
     
        node_ap_ip = cfg.ap_list[THIS_AP_UUID][0]
        for key in cfg.ap_list.keys():
            if key != THIS_AP_UUID:
                ap_ip = cfg.ap_list[key][0]
                ap_mac = int_to_mac( int(ipaddress.ip_address(node_ap_ip)) )
                entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                        table_name='MyIngress.tb_ipv4_lpm',
                        action_name='MyIngress.ac_ipv4_forward_mac', match_keys=f'{station_vip}/32' , 
                        action_params= f'{cfg.swarm_backbone_switch_port} {ap_mac}', thrift_ip= ap_ip, thrift_port= bmv2.DEFAULT_THRIFT_PORT )

                    
async def handle_disconnected_station(station_physical_mac_address):
    try: 
        # sometimes when the program is started there are already connected nodes to the AP.
        # so if one of these nodes disconnectes from the AP whre a disconnection is detected but the 
        # node is not found in the list of connected nodes, this check skips the execution of the rest of the code.
        logger.debug(f'Handling disconnected Node: {station_physical_mac_address}')
        if (station_physical_mac_address not in connected_stations.keys()):
            logger.warning(f'\nStation {station_physical_mac_address} disconnected from AP but was not found in connected stations')
            return
        
        # Wait for some time configured by the variable in cfg before considering that the node has actually disconnected
        t0 = time.time()
        while time.time() - t0 < cfg.ap_wait_time_for_disconnected_station_in_seconds:
            cli_command = "iw wlan0 station dump | grep Station | awk '{print $2}'"
            proc_res = subprocess.run(cli_command,shell=True, text=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if (proc_res.stderr):
                logger.error(f"Error running command: {cli_command}\nError Message: {proc_res.stderr}")
            if (station_physical_mac_address in proc_res.stdout):
                return
            time.sleep(1)
        
        
        SN_UUID = 'SN:' + station_physical_mac_address[9:]
        node_db_result = db.get_node_info_from_art(node_uuid=SN_UUID)
        if ( node_db_result == None or node_db_result.node_current_ap != THIS_AP_UUID):
            return
            
        logger.debug(f'Removing disconnected Node: {station_physical_mac_address}')    
        # station_physical_ip_address = get_ip_from_arp(station_physical_mac_address)
        station_virtual_ip_address = connected_stations[station_physical_mac_address][CONNECTED_STATIONS_VIP_INDEX]
        station_virtual_mac_address = connected_stations[station_physical_mac_address][CONNECTED_STATIONS_VMAC_INDEX]
        station_vxlan_id = connected_stations[station_physical_mac_address][CONNECTED_STATION_VXLAN_INDEX]

        # delete the station from the connected stations
        del connected_stations[station_physical_mac_address]
        logger.debug(f"Connected Stations List after removing {station_physical_mac_address}: {connected_stations}")
        
        
        # delete the forwarding entries that point to this station from the rest of the Access Points.
        # TODO: move this functionality to the coordinator.
        for key in cfg.ap_list.keys():
            ap_ip = cfg.ap_list[key][0]
            logger.debug(f'deleting entries from: {key} with IP {ap_ip}')
            bmv2.delete_forwarding_entry_from_bmv2(communication_protocol=bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
                                            table_name='MyIngress.tb_ipv4_lpm', key=f'{station_virtual_ip_address}/32',
                                            thrift_ip=ap_ip, thrift_port=bmv2.DEFAULT_THRIFT_PORT)
            
            # bmv2.delete_forwarding_entry_from_bmv2(communication_protocol=bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
            #                                   table_name='MyIngress.tb_l2_forward', key=station_virtual_mac_address,
            #                                   thrift_ip=ap_ip, thrift_port=bmv2.DEFAULT_THRIFT_PORT)

        
        # delete the corresponding switch port
        delete_vxlan_from_bmv2_command = "port_remove %s" % station_vxlan_id
        bmv2.send_cli_command_to_bmv2(delete_vxlan_from_bmv2_command)
        
        
        # delete the node from the database
        db.update_db_with_left_node(node_swarm_id=station_vxlan_id)

        
        logger.debug(f'station: {station_virtual_ip_address} left {THIS_AP_UUID}')
        
        delete_vxlan_by_host_id(station_vxlan_id)
    except Exception as e:
        logger.error(f"Error handling disconnected station {SN_UUID}: {repr(e)}")

def monitor_stations():
    # this command is run in the shell to monitor wireless events using the iw tool
    monitoring_command = 'iw event'

    # python runs the shell command and monitors the output in the terminal
    process = subprocess.Popen( monitoring_command.split() , stdout=subprocess.PIPE)
    previous_line = ''
    # we iterate over the output lines to read the event and react accordingly
    for output_line in iter(lambda: process.stdout.readline().decode("utf-8"), ""):
        if (output_line.strip() == previous_line.strip()):
            continue
        previous_line = output_line
        output_line_as_word_array = output_line.split()
        logger.debug( '\WiFi Event: ' + output_line )
        
        if output_line_as_word_array[INDEX_IW_EVENT_ACTION] == IW_TOOL_JOINED_STATION_EVENT:
            station_physical_mac_address = output_line_as_word_array[INDEX_IW_EVENT_MAC_ADDRESS]
            logger.debug( '\nNew Station MAC: ' + station_physical_mac_address )
            
            asyncio.run( handle_new_connected_station(station_physical_mac_address=station_physical_mac_address) )

        elif output_line_as_word_array[INDEX_IW_EVENT_ACTION] ==   IW_TOOL_LEFT_STATION_EVENT:
            station_physical_mac_address = output_line_as_word_array[INDEX_IW_EVENT_MAC_ADDRESS]
            logger.info( '\nDisconnected Station MAC: ' + station_physical_mac_address )
            asyncio.run(  handle_disconnected_station(station_physical_mac_address=station_physical_mac_address) )



def ap_id_to_vxlan_id(access_point_id):
    vxlan_id = cfg.vxlan_ids[access_point_id]
    return vxlan_id

        
               
def main():
    print("AP Starting")
    logger.debug("AP: Program Started")
    initialize_program()
    monitor_stations()
    
    # thread for monitoring connected devices to the AP WiFi network
    # monitor_stations_on_thread = threading.Thread(target=monitor_stations, args=()).start()
    

            
    
if __name__ == '__main__':
    atexit.register(exit_handler)
    main()
    