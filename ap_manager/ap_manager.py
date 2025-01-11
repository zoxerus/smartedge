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

dir_path = os.path.dirname(os.path.realpath(__file__))

# this part handles logging to console and to a file for debugging purposes
# where to store program logs
PROGRAM_LOG_FILE_NAME = './logs/ap.log'
os.makedirs(os.path.dirname(PROGRAM_LOG_FILE_NAME), exist_ok=True)
logger = logging.getLogger('ap_logger')
client_monitor_log_formatter = logging.Formatter("\n\nLine:%(lineno)d at %(asctime)s [%(levelname)s]:\n\t %(message)s \n\n")
client_monitor_log_file_handler = logging.FileHandler(PROGRAM_LOG_FILE_NAME, mode='w')
client_monitor_log_file_handler.setLevel(logging.DEBUG)
client_monitor_log_file_handler.setFormatter(client_monitor_log_formatter)
client_monitor_log_console_handler = logging.StreamHandler(sys.stdout)
client_monitor_log_console_handler.setLevel(logging.DEBUG)
client_monitor_log_console_handler.setFormatter(client_monitor_log_formatter)
logger.setLevel(logging.DEBUG)    
logger.addHandler(client_monitor_log_file_handler)
logger.addHandler(client_monitor_log_console_handler)
db.db_logger = logger
bmv2.bmv2_logger = logger
logger.debug(f'running in: {dir_path}')



# a global variable to set the communication protocol with the switch
P4CTRL = bmv2.P4_CONTROL_METHOD_THRIFT_CLI
# Set which database the program is going to use

# string constants
STR_NODE_VIP = 'Node_vIP'
STR_AP_ID = 'AP_ID'
STR_NODE_VMAC = 'NODE_VMAC'
STR_CONTROL_UPDATE_ACTION = 'ACTION'
STR_CONTROL_UPDATE_ACTION_JOIN = 'JOIN'
STR_CONTROL_UPDATE_ACTION_LEAVE = 'LEAVE'

INDEX_IW_EVENT_MAC_ADDRESS = 3
INDEX_IW_EVENT_ACTION = 1 

IW_TOOL_JOINED_STATION_EVENT = 'new'
IW_TOOL_LEFT_STATION_EVENT = 'del'

# read the swarm subnet from the config file
# TODO: make this configurable by coordinator
THIS_SWARM_SUBNET=ipaddress.ip_address( cfg.this_swarm_subnet )


# a variable to track created host ids
# TODO: have a database table for this
# current_host_id = config.this_swarm_dhcp_start
created_host_ids = set([])


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
def int_to_mac(macint):
    if type(macint) != int:
        raise ValueError('invalid integer')
    return ':'.join(['{}{}'.format(a, b)
                     for a, b
                     in zip(*[iter('{:012x}'.format(macint ))]*2)])  # + 2199023255552

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
    # client_monitor_log_formatter = logging.Formatter("\n\nLine:%(lineno)d at %(asctime)s [%(levelname)s]:\n\t %(message)s \n\n")
    # client_monitor_log_file_handler = logging.FileHandler(PROGRAM_LOG_FILE_NAME, mode='w')
    # client_monitor_log_file_handler.setLevel(logging.INFO)
    # client_monitor_log_file_handler.setFormatter(client_monitor_log_formatter)
    # client_monitor_log_console_handler = logging.StreamHandler(sys.stdout)
    # client_monitor_log_console_handler.setLevel(logging.INFO)
    # client_monitor_log_console_handler.setFormatter(client_monitor_log_formatter)
    # logger.setLevel(logging.INFO)    
    # logger.addHandler(client_monitor_log_file_handler)
    # logger.addHandler(client_monitor_log_console_handler)

    # db.db_logger = logger
    # bmv2.bmv2_logger = logger
    # logger.debug(f'running in: {dir_path}')
    
    
    # remvoe all configureation from bmv2, start fresh
    bmv2.send_cli_command_to_bmv2(cli_command="reset_state")

    # attach the backbone interface to the bmv2
    bmv2.send_cli_command_to_bmv2(cli_command=f"port_remove {cfg.swarm_backbone_switch_port}")
    bmv2.send_cli_command_to_bmv2(cli_command=f"port_add {cfg.default_backbone_device} {cfg.swarm_backbone_switch_port}")
    logger.debug('Program Initialized')

# a handler to clean exit the programs
def exit_handler():
    logger.debug('Handling exit')
    logger.debug(f'Created vxlan ids: {created_host_ids}') 
               
    # delete any created vxlans during the program lifetime
    for vxlan_id in created_host_ids:
        try:
            delete_vxlan_shell_command = "ip link del vxlan%s" % vxlan_id
            result = subprocess.run(delete_vxlan_shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
            db.delete_node_from_swarm_database(database_type=db.STR_DATABASE_TYPE_CASSANDRA, session=database_session,
                                    node_swarm_id= vxlan_id)
            logger.debug(f'deleted vxlan{vxlan_id},\n\t feedback: \n {result.stdout.strip() }')
        except Exception as e:
            logger.error(repr(e))

# a function for sending the configuration to the swarm node
# this connects to the TCP server running in the swarm node and sends the configuration as a string
def send_swarmNode_config(config_messge, node_socket_server_address):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as node_socket_client:
        node_socket_client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        node_socket_client.settimeout(5)
        try:
            node_socket_client.connect(node_socket_server_address)
            node_socket_client.sendall( bytes( config_messge.encode() ))
        except Exception as e:
            logger.error(f'Error sending config to {node_socket_server_address}: {e}')
    logger.debug(f'AP has sent this config to the Smart Node:\n\t {config_messge}')

def create_vxlan_by_host_id(vxlan_id, remote, port=4789): 
    logger.debug(f'Adding vxlan{vxlan_id}')
    
    add_vxlan_shell_command = "ip link add vxlan%s type vxlan id %s dev %s remote %s dstport %s" % (
        vxlan_id, vxlan_id, DEFAULT_WLAN_DEVICE_NAME, remote, port)

    result = subprocess.run(add_vxlan_shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if (result.stderr):
        logger.error(f'\nCould not create vxlan{vxlan_id}:\n\t {result.stderr}')
        return -1
    logger.debug(f'\nCreate vxlan{vxlan_id}:\n\t {result.stdout}')
    created_host_ids.add(vxlan_id)
    logger.debug(f'\nCreated host IDs:\n\t {created_host_ids}')            
    activate_interface_shell_command = "ip link set vxlan%s up" % vxlan_id
    result = subprocess.run(activate_interface_shell_command.split(), text=True , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if (result.stderr):
        logger.error(f'\nCould not activate interface vxlan{vxlan_id}:\n\t {result.stderr}')
        return -1
    logger.debug(f'\nActivated interface vxlan{vxlan_id}:\n\t {result.stdout}')
    return vxlan_id
        

def delete_vxlan_by_host_id(host_id):
    logger.debug(f'\nDeleting vxlan{host_id}')
    delete_vxlan_shell_command = "ip link del vxlan%s" % (host_id)
    result = subprocess.run(delete_vxlan_shell_command.split(), text=True , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if (result.stderr):
        logger.error(f'\ncould not delete delete vxlan{host_id}:\n\t {result.stderr}')
        return
    created_host_ids.remove(host_id)
    logger.debug(f'\nCreated host IDs: {created_host_ids}')


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
    result = subprocess.run( shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if (result.stderr):
        logger.error(f'\nCould not run arp for {physical_mac}:\n\t {result.stderr}')
        return
    logger.debug(f'ARP result:\n {result.stdout}')
    for line in result.stdout.strip().splitlines():
        if physical_mac in line and DEFAULT_WLAN_DEVICE_NAME in line:
            return line.split()[0]
    logger.error(f'\nIP not found in ARP for {physical_mac}')


def assign_virtual_mac_and_ip_by_host_id(host_id):
    station_virtual_ip_address = str( THIS_SWARM_SUBNET + host_id )
    station_virtual_mac_address = int_to_mac(int( THIS_SWARM_SUBNET + host_id ))
    
    logger.debug( f'\nAssigned Station\'s Virtual IP: {station_virtual_ip_address}' )
    logger.debug( f'\nAssigned Station\'s Virtual MAC: {station_virtual_mac_address}')
    
    return station_virtual_mac_address, station_virtual_ip_address


def handle_new_connected_station(station_physical_mac_address):
    logger.debug(f"handling newly connected staion {station_physical_mac_address}")
    # First Step check if node is already in the Connected Nodes 
    # sometimes an already connected station is randomly detected as connecting again, 
    # this check skips the execution of the rest of the code, as the station is already connected and set up.
    if (station_physical_mac_address in connected_stations.keys() ):
        logger.warning(f'\nStation {station_physical_mac_address} Connected to {THIS_AP_UUID} but was found already in Connected Stations')
        return
    
    # get the IP of the node from its mac address from the ARP table
    station_physical_ip_address = get_ip_from_arp_by_physical_mac(station_physical_mac_address)
    # sometimes it takes more than one try to get the ip from the ARP, I don't know why
    if station_physical_ip_address == None:
        tries = 2
        while (tries > 0):
            station_physical_ip_address = get_ip_from_arp_by_physical_mac(station_physical_mac_address)
            if station_physical_ip_address != None:
                break
            time.sleep(0.05)
            tries = tries - 1
        if station_physical_ip_address == None:
            logger.error(f'Error: Could not get Node Physical IP from ARP table for MAC: {station_physical_mac_address}')
            return
        
    # # 2nd Step: Check if Node belong to a Swarm or Not
    # # to do so we first read the UUID (bottom three bytes of MAC address)
    # SN_UUID = 'SN:' + station_physical_mac_address[9:]
    
    # # Then we search the TDD to see if the node is present in there
    # result = db.get_node_info_from_tdd(session=database_session, node_uuid=SN_UUID)
    # # in case the node is not present in the TDD we add it to the TDD
    # if (result == None):
    #     db.insert_into_thing_directory_with_node_info(database_typ=db_in_use, session=database_session,
    #                                                   node_uuid=SN_UUID, current_ap=THIS_AP_UUID, swarm_id=0)
        
    #     # We then add two table entries to route traffic from the node to the coordinator and vice versa.    
    #     # THIS ENTRY ONLY ALLOWES TRAFFIC TO COORDINATOR TCP PORT FROM THE NEW JOINED NODE
    #     entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
    #                                 table_name = 'MyIngress.tb_swarm_control',
    #                                 action_name = 'MyIngress.ac_send_to_coordinator', 
    #                                 match_keys = f'{config.wlan_switch_port} {config.coordinator_physical_ip}',
    #                                 action_params = f'{config.swarm_coordinator_switch_port} {THIS_AP_ETH_MAC} {config.coordinator_physical_mac}' )
        
    #     # THIS ENTRY ONLY ALLOWES TRAFFIC TO COORDINATOR TCP PORT FROM THE NEW JOINED NODE
    #     entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
    #                                 table_name = 'MyIngress.tb_swarm_control',
    #                                 action_name = 'MyIngress.ac_send_to_coordinator', 
    #                                 match_keys = f'{config.ethernet_switch_port} {station_physical_ip_address}',
    #                                 action_params = f'{config.wlan_switch_port} {THIS_AP_WLAN_MAC} {station_physical_mac_address}' )
    # # if node is present in the TDD byt current swarm of the node is 0 meaning it is in the guest network (default swarm or also called swarm zero)
    # elif (result.node_current_swarm == 0):
    #     # then we just updated the TDD to indicate that the node has connected to the current AP
    #     db.update_tdd_with_new_node_status(database_type=db_in_use, session=database_session, 
    #                                        node_uuid=SN_UUID, node_current_ap=THIS_AP_UUID, node_current_swarm=0)
    


        
    logger.debug( f'\nHandling New Station: {station_physical_mac_address} {station_physical_ip_address} at {time.time()}')
    
    host_id = db.get_next_available_host_id_from_swarm_table(first_host_id=cfg.this_swarm_dhcp_start,
                max_host_id=cfg.this_swarm_dhcp_end)
    
    logger.debug(f"Assigning Host ID: {host_id}")
    
    result = assign_virtual_mac_and_ip_by_host_id(host_id)
    station_vmac= result[0]
    station_vip = result[1]

    logger.debug( f'\nStation {station_physical_mac_address}\t{station_physical_ip_address}\n\t' +  
                f'assigned vIP: {station_vip} and vMAC: {station_vmac}')
    
    vxlan_id = create_vxlan_by_host_id( vxlan_id= host_id, remote= station_physical_ip_address )
       
    dettach_vxlan_from_bmv2_command = "port_remove %s" % (vxlan_id)
    bmv2.send_cli_command_to_bmv2(cli_command=dettach_vxlan_from_bmv2_command)
    
    attach_vxlan_to_bmv2_command = "port_add vxlan%s %s" % (vxlan_id, vxlan_id)
    bmv2.send_cli_command_to_bmv2(cli_command=attach_vxlan_to_bmv2_command)
    
    # We then add two table entries to route traffic from the node to the coordinator and vice versa.
    # THIS ENTRY ONLY ALLOWES TRAFFIC TO COORDINATOR TCP PORT FROM THE NEW JOINED NODE
    entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
                                table_name = 'MyIngress.tb_swarm_control',
                                action_name = 'MyIngress.ac_send_to_coordinator', 
                                match_keys = f'{vxlan_id} {cfg.coordinator_vip}',
                                action_params = f'{cfg.swarm_backbone_switch_port}' )
    
    # THIS ENTRY ONLY ALLOWES TRAFFIC TO COORDINATOR TCP PORT FROM THE NEW JOINED NODE
    entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
                                table_name = 'MyIngress.tb_swarm_control',
                                action_name = 'MyIngress.ac_send_to_coordinator', 
                                match_keys = f'{cfg.swarm_backbone_switch_port} {station_vip}',
                                action_params = f'{vxlan_id}' )
       
    # Add the newly connected station to the list of connected stations
    connected_stations[station_physical_mac_address] = [ station_vmac ,station_vip, vxlan_id]
    logger.debug(f"Connected Stations List after Adding {station_physical_mac_address}: {connected_stations}")
    
    # Now we should insert the new connected station in the swarm database
    db.insert_node_into_swarm_database(this_ap_id= THIS_AP_UUID,
                                    host_id=host_id, node_vip=station_vip, node_vmac=station_vmac, node_phy_mac=station_physical_mac_address)
    
    logger.debug(f'station: {station_vmac} {station_vip} joined AP {THIS_AP_UUID} at {time.time()}')
    
    # connect to the swarm node manager and send the  required configuration for the communication with the coordinator
    swarmNode_config_message = f'setConfig {vxlan_id} {station_vip} {station_vmac} {cfg.coordinator_vip} {cfg.coordinator_tcp_port} {THIS_AP_UUID}'
    threading.Thread(target= send_swarmNode_config, args= (swarmNode_config_message,
                                                           (station_physical_ip_address, cfg.node_manager_tcp_port ), ) 
    ).start()


                    
def handle_disconnected_station(station_physical_mac_address):
    # sometimes when the program is started there are already connected nodes to the AP.
    # so if one of these nodes disconnectes for the AP whre a disconnection is detected but the 
    # node is not found in the list of connected nodes, this check skips the execution of the rest of the code.
    logger.debug(f'Handling disconnected Node: {station_physical_mac_address}')
    if (station_physical_mac_address not in connected_stations.keys()):
        logger.warning(f'\nStation {station_physical_mac_address} disconnected from AP but was not found in connected stations')
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
        
        bmv2.delete_forwarding_entry_from_bmv2(communication_protocol=bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
                                          table_name='MyIngress.tb_l2_forward', key=station_virtual_mac_address,
                                          thrift_ip=ap_ip, thrift_port=bmv2.DEFAULT_THRIFT_PORT)

    
    # delete the corresponding switch port
    delete_vxlan_from_bmv2_command = "port_remove %s" % station_vxlan_id
    bmv2.send_cli_command_to_bmv2(delete_vxlan_from_bmv2_command)
    
    
    # delete the node from the database
    db.delete_node_from_swarm_database(database_type=db.STR_DATABASE_TYPE_CASSANDRA, session=database_session,
                                    node_swarm_id= station_vxlan_id)

    
    logger.debug(f'station: {station_virtual_ip_address} left {THIS_AP_UUID}')
       
    delete_vxlan_by_host_id(station_vxlan_id)
    

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
            
            handle_new_connected_station(station_physical_mac_address=station_physical_mac_address)

        elif output_line_as_word_array[INDEX_IW_EVENT_ACTION] ==   IW_TOOL_LEFT_STATION_EVENT:
            station_physical_mac_address = output_line_as_word_array[INDEX_IW_EVENT_MAC_ADDRESS]
            logger.info( '\nDisconnected Station MAC: ' + station_physical_mac_address )
            try:
                handle_disconnected_station(station_physical_mac_address=station_physical_mac_address)
            except Exception as e:
                logger.error(f'Error handling disconnected station: {station_physical_mac_address}')
                logger.error(e)



def ap_id_to_vxlan_id(access_point_id):
    vxlan_id = cfg.vxlan_ids[access_point_id]
    return vxlan_id

        
               
def main():
    logger.debug("AP: Program Started")
    initialize_program()
    
    
    # thread for monitoring connected devices to the AP WiFi network
    monitor_stations_on_thread = threading.Thread(target=monitor_stations, args=()).start()
    

            
    
if __name__ == '__main__':
    atexit.register(exit_handler)
    main()
    