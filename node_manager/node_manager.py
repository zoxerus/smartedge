# This tells python to look for files in parent folders
import sys
# setting path
sys.path.append('.')
sys.path.append('..')
sys.path.append('../..')


import subprocess
import psutil
import logging
import threading
import atexit
import queue
import time
import socket
import ipaddress
import os
import json
import lib.global_config as cfg
import lib.helper_functions as utils
import lib.global_constants as cts

STRs = cts.String_Constants 


from argparse import ArgumentParser
parser = ArgumentParser()
parser.add_argument("-l", "--log-level",type=int, default=10, help="logging level")
args = parser.parse_args()


PROGRAM_LOG_FILE_NAME = './logs/program.log'
os.makedirs(os.path.dirname(PROGRAM_LOG_FILE_NAME), exist_ok=True)
logger = logging.getLogger('SN_Logger')

# this part handles logging to console and to a file for debugging purposes
log_formatter =  logging.Formatter("\n\nLine:%(lineno)d at %(asctime)s [%(levelname)s] %(filename)s :\n\t %(message)s \n\n")

# log_file_handler = logging.FileHandler(PROGRAM_LOG_FILE_NAME, mode='w')
# log_file_handler.setLevel(args.log_level)
# log_file_handler.setFormatter(log_formatter)

log_console_handler = logging.StreamHandler(sys.stdout)  # (sys.stdout)
# log_console_handler.setLevel(args.log_level)
log_console_handler.setFormatter(log_formatter)


logger.setLevel(args.log_level)
# logger.addHandler(log_file_handler)
logger.addHandler(log_console_handler)



DEFAULT_IFNAME = 'wlan0'

loopback_if = 'lo:0'
def int_to_mac(macint):
    if type(macint) != int:
        raise ValueError('invalid integer')
    return ':'.join(['{}{}'.format(a, b)
                     for a, b
                     in zip(*[iter('{:012x}'.format(macint + 2199023255552))]*2)])  

THIS_NODE_UUID = None

for snic in psutil.net_if_addrs()[loopback_if]:
    if snic.family == socket.AF_INET:        
        temp_mac = int_to_mac(int(ipaddress.ip_address(snic.address) - 1))
        THIS_NODE_UUID = f'SN:{temp_mac[9:]}'
if THIS_NODE_UUID == None:
    logger.error("Could not Assign UUID to Node")
    exit()
print("UUID:", THIS_NODE_UUID)


if THIS_NODE_UUID == None:
    print('Error: Could not assign UUID')
    exit()

print('Assign Node UUID:', THIS_NODE_UUID)



ACCESS_POINT_IP = ''



join_queue = queue.Queue()

gb_swarmNode_config = {
    # STRs.VXLAN_ID : None,
    # STRs.VETH1_VIP: '',
    # STRs.SWARM_ID: '',
    # STRs.VETH1_VMAC: '',
    # STRs.COORDINATOR_VIP: '',
    # STRs.COORDINATOR_TCP_PORT: '',
    # STRs.AP_ID: '',
    # STRs.AP_IP: '',
    # STRs.AP_MAC: ''
}

last_request_id = 0


def get_ip_from_arp_by_physical_mac(physical_mac):
    shell_command = "arp -en"
    proc = subprocess.run( shell_command.split(), text=True, stdout=subprocess.PIPE)
    for line in proc.stdout.strip().splitlines():
        if physical_mac in line:
            return line.split()[0]



def get_ap_physical_ip_by_ifname(ifname):
    cli_command = f"iwconfig {ifname}"
    command_as_word_array = cli_command.split()
    proc = subprocess.run(command_as_word_array, text=True, stdout=subprocess.PIPE)
    res_lines = proc.stdout.strip().splitlines()
    for line in res_lines:
      if 'Access Point' in line:
            mac = line.split()[5]
            print(f'AP MAC {mac}')
            return get_ip_from_arp_by_physical_mac(mac)
        
        
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

def handle_tcp_communication():
    global last_request_id, gb_swarmNode_config, ACCESS_POINT_IP
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as node_manager_socket:
        try:
            set_keepalive_linux(sock= node_manager_socket, after_idle_sec=1, interval_sec=3, max_fails= 5)
            node_manager_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            node_manager_socket.bind( ('0.0.0.0', cfg.node_manager_tcp_port) )

            logger.debug(f'Node Manager Listening on port {cfg.node_manager_tcp_port} ...')
        except Exception as e:
            logger.error(f'Exception in Node Manager Socket: {e}')
        while True:
            node_manager_socket.listen()
            ap_socket, ap_address = node_manager_socket.accept()
            comm_buffer = ap_socket.recv(1024).decode()
            logger.debug(f'received: {comm_buffer}')
            config_data = json.loads(comm_buffer)
            logger.debug(f'config_data: {config_data}')
            gb_swarmNode_config = config_data
            
            ACCESS_POINT_IP = ap_address[0]
            
            logger.debug(f'Handling Join Type { config_data[STRs.TYPE] } and the thing {STRs.JOIN_REQUEST_00.value}')   
                                         
            if config_data[STRs.TYPE] == STRs.JOIN_REQUEST_00.value:
                logger.debug(f'Handling Join Type {STRs.JOIN_REQUEST_00.name}')
                try:
                    install_swarmNode_config(config_data)
                    ap_socket.sendall(bytes( "OK!".encode() ))
                except Exception as e:
                    logger.error(repr(e))
                    
                while True:
                    user_input = input("Enter 1 to send a join request")
                    if user_input == '1':
                        break
                try:                        
                    join_request_dic = {
                        STRs.TYPE:           STRs.JOIN_REQUEST,
                        STRs.REQUIST_ID:     last_request_id,
                        STRs.THIS_NODE_UUID: THIS_NODE_UUID,
                        STRs.THIS_NODE_APID: config_data[STRs.AP_ID]
                    }
                    last_request_id = last_request_id + 1
                    
                    join_request_json_string = json.dumps(join_request_dic)
                    
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as coordinator_socket:
                        print(f'connecting to {config_data[STRs.COORDINATOR_VIP]}:{config_data[STRs.COORDINATOR_TCP_PORT]}')
                        coordinator_socket.settimeout(10)
                        coordinator_socket.connect((config_data[STRs.COORDINATOR_VIP], config_data[STRs.COORDINATOR_TCP_PORT] ))
                        coordinator_socket.sendall(bytes( join_request_json_string.encode() ))
                        
                        print(f'sent {join_request_dic} to coordinator')
                        
                        response = coordinator_socket.recv(1024).decode()
                        if (response.split()[0] == 'Accepted:'):
                            pass                       
                        
                except Exception as e:
                    print(f'Error installing config: {e} Leaving Access Point' )
                    cli_command = f'nmcli connection show --active'
                    res = subprocess.run(cli_command.split(), text=True, stdout=subprocess.PIPE)
                    ap_ssid = ''
                    for line in res.stdout.strip().splitlines():
                        if DEFAULT_IFNAME in line:
                            ap_ssid = line.split()[0]
                    cli_command = f'nmcli connection down id {ap_ssid}'
                    subprocess.run(cli_command.split(), text=True)
                    cli_command = f'nmcli connection delete id {ap_ssid}'
                    subprocess.run(cli_command.split(), text=True)
                    
            elif config_data[STRs.TYPE] == STRs.JOIN_REQUEST_01:
                install_swarmNode_config()
                coordinator_socket.sendall(bytes( "OK!".encode() ))
            else:
                logger.error(f'Unkown Message Type {config_data[STRs.TYPE]}')

def install_swarmNode_config(swarmNode_config):
    global last_request_id, join_queue, ACCESS_POINT_IP
    
    vxlan_id = swarmNode_config[STRs.VXLAN_ID]
    swarm_veth1_vip = swarmNode_config[STRs.VETH1_VIP]
    swarm_veth1_vmac = swarmNode_config[STRs.VETH1_VMAC]

        
    commands = [ # add the vxlan interface to the AP
                f'ip link add vxlan{vxlan_id} type vxlan id {vxlan_id} dev {DEFAULT_IFNAME} remote {ACCESS_POINT_IP} dstport 4789',
                # bring the vxlan up
                    f'ip link set dev vxlan{vxlan_id} up',    
                # add the veth interface pair, will be ignored if name is duplicate
                    f'ip link add veth0 type veth peer name veth1',
                # add the vmac and vip (received from the AP manager) to the veth1 interface,
                    f'ifconfig veth1 hw ether {swarm_veth1_vmac} ',
                    f'ifconfig veth1 {swarm_veth1_vip} netmask 255.255.255.0 up',
                    f'ifconfig veth0 up',
                # disable HW offloads of checksum calculation, (as this is a virtual interface)
                    f'ethtool --offload veth1 rx off tx off'
                ]
    
    for command in commands:
        logger.debug('executing: ' + command)
        process_ret = subprocess.run(command, text=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
        if (process_ret.stderr):
            logger.error(f"Error executing command {command}: \n{process_ret.stderr}")
        
    get_if1_index_command = 'cat /sys/class/net/veth0/ifindex'
    get_if2_index_command = f'cat /sys/class/net/vxlan{vxlan_id}/ifindex'
    if1_index = subprocess.run(get_if1_index_command.split(), text=True , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if2_index = subprocess.run(get_if2_index_command.split(), text=True , stdout=subprocess.PIPE, stderr=subprocess.PIPE)   
    
    commands = [
        'nikss-ctl pipeline unload id 0',        
        'nikss-ctl pipeline load id 0 ./node_manager/utils/nikss.o',
        f'nikss-ctl add-port pipe 0 dev veth0',
        f'nikss-ctl add-port pipe 0 dev vxlan{vxlan_id}',
        f'nikss-ctl table add pipe 0 ingress_route action id 2 key {if1_index.stdout} data {if2_index.stdout}',
        f'nikss-ctl table add pipe 0 ingress_route action id 2 key {if2_index.stdout} data {if1_index.stdout}'
    ]
    
    for command in commands:
        logger.debug('executing: ' + command)
        process_ret = subprocess.run(command, text=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
        if (process_ret.stderr):
            logger.error(f"Error executing command {command}: \n{process_ret.stderr}")
    
def exit_handler():
    logger.info('Handling exit')
    handle_disconnection()
        
        
def handle_disconnection():
    global gb_swarmNode_config
    logger.debug( '\nHandling Disconnection:\n'  )
    try:
        exit_commands = [
            'ifconfig veth1 0.0.0.0',
            'nikss-ctl del-port pipe 0 dev veth0',
            f"nikss-ctl del-port pipe 0 dev vxlan{gb_swarmNode_config[STRs.VXLAN_ID]}",
            'nikss-ctl table delete pipe 0 ingress_route',
            'nikss-ctl pipeline unload id 0 ',
            f"ip link delete vxlan{gb_swarmNode_config[STRs.VXLAN_ID]}"
        ]
        for command in exit_commands:
            res = subprocess.run( command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if (res.stderr):
                logger.error(f'Error running command: {command}\n\tError Message:{res.stderr}')
        logger.debug( '\nDone Handling Disconnection:\n'  )
    except Exception as e:
        print(e)    

def monitor_wifi_status(): 
    # this command is run in the shell to monitor wireless events using the iw tool
    monitoring_command = 'nmcli device monitor wlan0'

    # python runs the shell command and monitors the output in the terminal
    process = subprocess.Popen( monitoring_command.split() , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    previous_line = ''
    # we iterate over the output lines to read the event and react accordingly
    for output_line in iter(lambda: process.stdout.readline().decode("utf-8"), ""):
        if (output_line.strip() == previous_line.strip()):
            continue
        previous_line = output_line
        output_line_as_word_array = output_line.split()
        # logger.debug( '\noutput_line: ' + output_line )
        if output_line_as_word_array[1] == 'disconnected':
            logger.debug('Disconnected from WiFi')
            # handle_disconnection()

  
def main():
    print('program started')
    threading.Thread(target=handle_tcp_communication, args=() ).start()
    threading.Thread(target= monitor_wifi_status, args=() ).start()


if __name__ == '__main__':
    atexit.register(exit_handler)
    main()
