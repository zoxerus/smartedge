# This tells python to look for files in parent folders
import sys
# setting path
sys.path.append('..')
sys.path.append('../..')


import subprocess
import logging
import threading
import queue
import socket
import atexit
import time
import ipaddress
import config
import psutil
import sys
import lib.database_comms as db
import lib.bmv2_thrift_lib as bmv2
import os



# where to store program logs
PROGRAM_LOG_FILE_NAME = '../logs/client_monitor.log'
os.makedirs(os.path.dirname(PROGRAM_LOG_FILE_NAME), exist_ok=True)

# CONSTANTS TO POINT TO THE INDEX OF MAC ADDRESS AND EVENT TYPES IN "iw event" COMMAND
# example output "wlan0: new station 48:22:54:c7:27:04"
INDEX_IW_EVENT_MAC_ADDRESS = 3
INDEX_IW_EVENT_ACTION = 1 

# the physical interface that connects to the backbone network
# TODO: safely delete this
DEFAULT_EHTERNET_DEVICE_NAME = config.default_ethernet_device

# get primary wlan interface from the config file
DEFAULT_WLAN_DEVICE_NAME = config.default_wlan_interface
 
# This is the interface that connects to the coordinator
DEFAULT_COORDINATOR_INTERFACE_PEER = config.default_coordinator_device

# String constants to be used with the output of the iw tool
IW_TOOL_JOINED_STATION_EVENT = 'new'
IW_TOOL_LEFT_STATION_EVENT = 'del'

# TODO: move this to the config file, or use an automated implementation
SWARM_P4_MC_NODE = 1100
SWARM_P4_MC_GROUP = 1000


# a global variable to set the communication protocol with the switch
p4_control_method = bmv2.P4_CONTROL_METHOD_THRIFT_CLI

# Set which database the program is going to use
db_in_use = db.STR_DATABASE_TYPE_CASSANDRA

# string constants
# TODO: move to a global config file
STR_NODE_VIP = 'Node_vIP'
STR_AP_ID = 'AP_ID'
STR_NODE_VMAC = 'NODE_VMAC'
STR_CONTROL_UPDATE_ACTION = 'ACTION'
STR_CONTROL_UPDATE_ACTION_JOIN = 'JOIN'
STR_CONTROL_UPDATE_ACTION_LEAVE = 'LEAVE'


# read the swarm subnet from the config file
# TODO: make this configurable by coordinator
THIS_SWARM_SUBNET=ipaddress.ip_address( config.this_swarm_subnet )

# a variable to track created host ids
# TODO: have a database table for this
current_host_id = config.this_swarm_dhcp_start
created_host_ids = set([])
available_host_ids = set([])

# a list to keep track of connected stations to current AP
connected_stations = {}


CONNECTED_STATIONS_VMAC_INDEX = 0
CONNECTED_STATIONS_VIP_INDEX = 1
CONNECTED_STATION_VXLAN_INDEX = 2



logger = logging.getLogger('client_monitor_logger')

database_session = db.connect_to_database(db_in_use, config.database_hostname, config.database_port)
           
                         
def initialize_program():
    # this part handles logging to console and to a file for debugging purposes
    client_monitor_log_formatter = logging.Formatter("Line:%(lineno)d at %(asctime)s [%(levelname)s]: %(message)s \n")
    client_monitor_log_file_handler = logging.FileHandler(PROGRAM_LOG_FILE_NAME, mode='w')
    client_monitor_log_file_handler.setLevel(logging.DEBUG)
    client_monitor_log_file_handler.setFormatter(client_monitor_log_formatter)
    client_monitor_log_console_handler = logging.StreamHandler(sys.stdout)  # (sys.stdout)
    client_monitor_log_console_handler.setLevel(logging.INFO)
    client_monitor_log_console_handler.setFormatter(client_monitor_log_formatter)
    logger.setLevel(logging.DEBUG)    
    logger.addHandler(client_monitor_log_file_handler)
    logger.addHandler(client_monitor_log_console_handler)
    
    
    # remvoe all configureation from bmv2, start fresh
    bmv2.send_cli_command_to_bmv2(cli_command="reset_state")
    
    # attach the DEFAULT_COORDINATOR_INTERFACE_PEER interface to the bmv2
    bmv2.send_cli_command_to_bmv2(cli_command=f"port_remove {config.swarm_coordinator_switch_port}")
    bmv2.send_cli_command_to_bmv2(cli_command=f"port_add {DEFAULT_COORDINATOR_INTERFACE_PEER} {config.swarm_coordinator_switch_port}")
    
   
    # handle broadcast
    bmv2.send_cli_command_to_bmv2(cli_command=f"mc_mgrp_create {SWARM_P4_MC_GROUP}")
    bmv2.send_cli_command_to_bmv2(cli_command=f"mc_node_create {SWARM_P4_MC_NODE} {config.ap_communication_switch_port}")
    bmv2.send_cli_command_to_bmv2(cli_command=f"mc_node_associate {SWARM_P4_MC_GROUP} 0")
    bmv2.send_cli_command_to_bmv2(cli_command=f"table_add MyIngress.tb_l2_forward ac_l2_broadcast FF:FF:FF:FF:FF:FF => {SWARM_P4_MC_GROUP}")
    
    
    # this creates required vxlans for the communication to coordinator and other AP if they don't exits    
    if config.ap_communication_switch_port != config.swarm_coordinator_switch_port:
        try:
            add_vxlan_shell_command = ( f"ip link add vxlan{config.ap_communication_switch_port} "
                f"type vxlan id {config.ap_communication_switch_port} group 239.1.1.1 dstport 4789 dev {DEFAULT_EHTERNET_DEVICE_NAME} " )
            subprocess.run(add_vxlan_shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            activate_interface_shell_command = f"ip link set vxlan{config.ap_communication_switch_port} up" 
            subprocess.run(activate_interface_shell_command.split(), text=True , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            created_host_ids.add(config.ap_communication_switch_port)
            
            # attach the created vxlans to the bmv2 switch.
            bmv2.send_cli_command_to_bmv2(cli_command=f"port_remove {config.ap_communication_switch_port}")
            bmv2.send_cli_command_to_bmv2(cli_command=f"port_add vxlan{config.ap_communication_switch_port} {config.ap_communication_switch_port}")
    
        except Exception as e:
            logger.error(f'initialization error: {e}')
            exit() 
    logger.info('Program Initialized Successfully')

# a handler to clean exit the programs
def exit_handler():
    logger.info('Handling exit')
    logger.debug(f'Created vxlan ids: {created_host_ids}') 
               
    # delete any created vxlans during the program lifetime
    for vxlan_id in created_host_ids:
        try:
            delete_vxlan_shell_command = "ip link del vxlan%s" % vxlan_id
            result = subprocess.run(delete_vxlan_shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
            
            
            db.delete_node_from_swarm_database(database_type=db.STR_DATABASE_TYPE_CASSANDRA, session=database_session,
                                    node_swarm_id= vxlan_id)
            logger.debug(f'deleted vxlan{vxlan_id}, feedback {result.stdout.strip() }, errors: {result.stderr.strip() }')
        except Exception as e:
            logger.debug(repr(e))


# a function for sending the configuration to the swarm node
def send_swarmNode_config(config_messge, node_socket_server_address):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as node_socket_client:
        node_socket_client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        node_socket_client.settimeout(5)
        try:
            node_socket_client.connect(node_socket_server_address)
            node_socket_client.sendall( bytes( config_messge.encode() ))
        except Exception as e:
            print(f'Error sending config to {node_socket_server_address}: {e}')
    print(f'sent {config_messge}')
    


def create_vxlan_by_host_id(vxlan_id, remote, port=4789): 
    try:
        logger.debug(f'Adding vxlan{vxlan_id}')
        
        add_vxlan_shell_command = "ip link add vxlan%s type vxlan id %s dev %s remote %s dstport %s" % (
            vxlan_id, vxlan_id, DEFAULT_WLAN_DEVICE_NAME, remote, port)
        
        result = subprocess.run(add_vxlan_shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
        logger.debug(f'\nCreating vxlan {vxlan_id}: {result.stdout} {result.stderr}')
        created_host_ids.add(vxlan_id)
        logger.debug(f'\nCreated host IDs: {created_host_ids}')            
        activate_interface_shell_command = "ip link set vxlan%s up" % vxlan_id
        subprocess.run(activate_interface_shell_command.split(), text=True , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
    except Exception as e:
        logger.debug(f'\nError creating vxlan {vxlan_id}: {e}')
        logger.debug(f'\nError creating vxlan {vxlan_id}: {result.stderr}')
        return -1
    return vxlan_id
        

def delete_vxlan_by_host_id(host_id):
    vxlan_id = host_id
    logger.debug(f'\nDeleting vxlan ID: {vxlan_id}')
    delete_vxlan_shell_command = "ip link del vxlan%s" % (vxlan_id)
    subprocess.run(delete_vxlan_shell_command.split(), text=True , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    available_host_ids.add(host_id)
    created_host_ids.remove(host_id)
    logger.debug(f'\nCreated host IDs: {created_host_ids}')


def get_mac_from_arp_by_physical_ip(ip):
    shell_command = "arp -en"
    proc = subprocess.run( shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    for line in proc.stdout.strip().splitlines():
        if ip in line:
            return line.split()[2]
    return None


# TODO: safely delete this
def get_next_available_host_id():
    global current_host_id
    if (len(available_host_ids) == 0):
        host_id = current_host_id
        current_host_id = current_host_id + 1
        return host_id
    host_id =  min(available_host_ids)
    available_host_ids.remove(host_id)
    return host_id


def get_ip_from_arp_by_physical_mac(physical_mac):
    shell_command = "arp -en"
    t0 = time.time()
    while time.time() - t0 < 5:
        proc = subprocess.run( shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for line in proc.stdout.strip().splitlines():
            if physical_mac in line and DEFAULT_WLAN_DEVICE_NAME in line:
                return line.split()[0]


def assign_virtual_mac_and_ip_by_host_id(host_id):
    station_virtual_ip_address = str( THIS_SWARM_SUBNET + host_id )
    host_id_hex = f'{host_id:04x}'
    station_virtual_mac_address = f'00:00:00:00:{host_id_hex[:2]}:{host_id_hex[2:]}'
    
    logger.debug( f'\nStation\'s Virtual IP: {station_virtual_ip_address}' )
    logger.debug( f'\nStation\'s Virtual MAC: {station_virtual_mac_address}')
    
    return station_virtual_mac_address, station_virtual_ip_address



def handle_new_connected_station(station_physical_mac_address, control_queue):
    # sometimes an already connected station is randomly detected as connecting again, 
    # this check skips the execution of the rest of the code, as the station is already connected and set up.
    if (station_physical_mac_address in connected_stations.keys() ):
        return

    station_physical_ip_address = get_ip_from_arp_by_physical_mac(station_physical_mac_address)
    if station_physical_ip_address == None:
        logger.error(f'Error: Could not get Node Physical IP from ARP table for MAC: {station_physical_mac_address}')
        return
    
    logger.info( f'\nHandling New Station: {station_physical_mac_address} \t {station_physical_ip_address} at {time.time()}')
    

    host_id = db.get_next_available_host_id_from_swarm_table(database_typ=db_in_use,
                session=database_session, first_host_id=config.this_swarm_dhcp_start,
                max_host_id=config.this_swarm_dhcp_end)
    
    
    
    result = assign_virtual_mac_and_ip_by_host_id(host_id)
    station_vmac= result[0]
    station_vip = result[1]

    logger.info( f'\nStation {station_physical_mac_address}\t{station_physical_ip_address}\n\t' +  
                f'assigned vIP: {station_vip} and vMAC: {station_vmac}')
    
    vxlan_id = create_vxlan_by_host_id( vxlan_id= host_id, remote= station_physical_ip_address )
       
    dettach_vxlan_from_bmv2_command = "port_remove %s" % (vxlan_id)
    bmv2.send_cli_command_to_bmv2(cli_command=dettach_vxlan_from_bmv2_command)
    
    attach_vxlan_to_bmv2_command = "port_add vxlan%s %s" % (vxlan_id, vxlan_id)
    bmv2.send_cli_command_to_bmv2(cli_command=attach_vxlan_to_bmv2_command)
    
    # THIS ENTRY ONLY ALLOWES TRAFFIC TO COORDINATOR TCP PORT FROM THE NEW JOINED NODE
    entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
                                    table_name = 'MyIngress.tb_swarm_control',
                                    action_name = 'MyIngress.ac_send_to_coordinator', 
                                    match_keys = f'{vxlan_id} {config.coordinator_vip}',
                                    action_params = f'{config.swarm_coordinator_switch_port}' )
    
    # THIS ENTRY FORWARDS ONLY TCP TRAFFIC TO THE NEW JOINED NODE, ON COORDINATOR PORT NUMBER.
    entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
                                    table_name = 'MyIngress.tb_swarm_control',
                                    action_name = 'MyIngress.ac_send_to_coordinator', 
                                    match_keys = f'{config.swarm_coordinator_switch_port} {station_vip}',
                                    action_params = f'{vxlan_id}' ) 
       
    # Add the newly connected station to the list of connected stations
    connected_stations[station_physical_mac_address] = [ station_vmac ,station_vip, vxlan_id]
    
    # Now we should insert the new connected station in the swarm database
    db.insert_node_into_swarm_database(database_type=db_in_use, session= database_session, this_ap_id= config.this_ap_id,
                                    host_id=host_id, node_vip=station_vip, node_vmac=station_vmac, node_phy_mac=station_physical_mac_address)
    
    logger.info(f'station: {station_vmac} {station_vip} joined AP {config.this_ap_id} at {time.time()}')
    
    # connect to the swarm node manager and send the  required configuration for the communication with the coordinator
    swarmNode_config_message = f'setConfig {vxlan_id} {station_vip} {station_vmac} {config.coordinator_vip} {config.coordinator_mac} {config.coordinator_tcp_port} {config.this_ap_id}'
    threading.Thread(target= send_swarmNode_config, args= (swarmNode_config_message,
                                                           (station_physical_ip_address, config.node_manager_tcp_port ), ) 
    ).start()


                    
def handle_disconnected_station(station_physical_mac_address, control_queue):
    # sometimes when the program is started there are already connected nodes to the AP.
    # so if one of these nodes disconnectes for the AP whre a disconnection is detected but the 
    # node is not found in the list of connected nodes, this check skips the execution of the rest of the code.
    print(f'Handling disconnected Node: {station_physical_mac_address}')
    if (station_physical_mac_address not in connected_stations.keys()):
        logger.warning(f'\nStation {station_physical_mac_address} disconnected from AP but was not found in connected stations')
        return
    
    
    print(f'Removing disconnected Node: {station_physical_mac_address}')    
    # station_physical_ip_address = get_ip_from_arp(station_physical_mac_address)
    station_virtual_ip_address = connected_stations[station_physical_mac_address][CONNECTED_STATIONS_VIP_INDEX]
    station_virtual_mac_address = connected_stations[station_physical_mac_address][CONNECTED_STATIONS_VMAC_INDEX]
    station_vxlan_id = connected_stations[station_physical_mac_address][CONNECTED_STATION_VXLAN_INDEX]

    # delete the station from the connected stations
    del connected_stations[station_physical_mac_address]
       
       
    # delete the forwarding entries that point to this station from the rest of the Access Points.
    # TODO: move this functionality to the coordinator.
    for key in config.ap_list.keys():
        ap_ip = config.ap_list[key][1]
        print('deleting entries from: ' + ap_ip)
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

    
    logger.info(f'station: {station_virtual_ip_address} left AP {config.this_ap_id}')
       
    delete_vxlan_by_host_id(station_vxlan_id)
    



def monitor_stations(control_queue):
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
        logger.debug( '\noutput_line: ' + output_line )
        
        if output_line_as_word_array[INDEX_IW_EVENT_ACTION] == IW_TOOL_JOINED_STATION_EVENT:
            station_physical_mac_address = output_line_as_word_array[INDEX_IW_EVENT_MAC_ADDRESS]
            logger.info( '\nNew Station MAC: ' + station_physical_mac_address )
            
            handle_new_connected_station(
                station_physical_mac_address=station_physical_mac_address,
                control_queue=control_queue)

        elif output_line_as_word_array[INDEX_IW_EVENT_ACTION] ==   IW_TOOL_LEFT_STATION_EVENT:
            station_physical_mac_address = output_line_as_word_array[INDEX_IW_EVENT_MAC_ADDRESS]
            logger.info( '\nDisconnected Station MAC: ' + station_physical_mac_address )
            try:
                handle_disconnected_station(
                    station_physical_mac_address=station_physical_mac_address, control_queue=control_queue)
            except Exception as e:
                logger.error(f'Error handling disconnected station: {station_physical_mac_address}')
                logger.error(e)



def ap_id_to_vxlan_id(access_point_id):
    vxlan_id = config.vxlan_ids[access_point_id]
    return vxlan_id

        
               
def main():
    logger.debug("Program Started")
    initialize_program()
    
    # a queue from communicating to the control thread, for sending updates
    # TODO: delete this
    control_queue = queue.Queue()
    
    # thread for monitoring connected devices to the AP WiFi network
    monitor_stations_on_thread = threading.Thread(target=monitor_stations, args=(control_queue,)).start()
    

            
    
if __name__ == '__main__':
    atexit.register(exit_handler)
    main()
    