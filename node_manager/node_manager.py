import subprocess
import sys
import json
import logging
import threading
import atexit
import queue
import time
import socket
import config
import os

PROGRAM_LOG_FILE_NAME = './logs/program.log'
os.makedirs(os.path.dirname(PROGRAM_LOG_FILE_NAME), exist_ok=True)

NODE_UUID = config.NODE_UUID

ACCESS_POINT_IP = ''
DEFAULT_IFNAME = config.default_ifname

logger = logging.getLogger(__name__)

# this part handles logging to console and to a file for debugging purposes
log_formatter = logging.Formatter("Line:%(lineno)d at %(asctime)s [%(levelname)s]: %(message)s \n")
log_file_handler = logging.FileHandler(PROGRAM_LOG_FILE_NAME, mode='w')

log_file_handler.setLevel(logging.DEBUG)
log_file_handler.setFormatter(log_formatter)


log_console_handler = logging.StreamHandler(sys.stdout)  # (sys.stdout)
log_console_handler.setLevel(logging.INFO)
log_console_handler.setFormatter(log_formatter)
logger.setLevel(logging.DEBUG)

logger.addHandler(log_file_handler)
logger.addHandler(log_console_handler)

STR_VXLAN_ID = 'vxlan_id'
STR_VETH1_VIP = 'veth1_vip'
STR_VETH1_VMAC = 'veth1_vmac'
STR_COORDINATOR_VIP = 'coordnator_vip'
STR_COORDINATOR_VMAC = 'coonrdinator_vmac'
STR_COORDINATOR_TCP_PORT = 'coordinator_tcp_port'
STR_AP_ID = 'ap_id'
STR_AP_IP = 'ap_ip'
STR_AP_MAC = 'ap_mac'

join_queue = queue.Queue()

swarmNode_config = {
    STR_VXLAN_ID : None,
    STR_VETH1_VIP: '',
    STR_VETH1_VMAC: '',
    STR_COORDINATOR_VIP: '',
    STR_COORDINATOR_VMAC: '',
    STR_COORDINATOR_TCP_PORT: '',
    STR_AP_ID: '',
    STR_AP_IP: '',
    STR_AP_MAC: ''
}

last_request_id = 0


def get_ip_from_arp_by_physical_mac(physical_mac):
    shell_command = "arp -en"
    proc = subprocess.run( shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in proc.stdout.strip().splitlines():
        if physical_mac in line:
            return line.split()[0]



def get_ap_physical_ip_by_ifname(ifname):
    cli_command = f"iwconfig {ifname}"
    command_as_word_array = cli_command.split()
    proc = subprocess.run(command_as_word_array, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    res_lines = proc.stdout.strip().splitlines()
    for line in res_lines:
      if 'Access Point' in line:
            mac = line.split()[5]
            print(f'AP MAC {mac}')
            return get_ip_from_arp_by_physical_mac(mac)
                

def handle_connection():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as node_manager_socket:
        try:
            node_manager_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            node_manager_socket.bind( ('0.0.0.0', 29997) )
        except Exception as e:
            print(f'Exception in Node Manager Socket: {e}')
        while True:
            node_manager_socket.listen()
            ap_socket, ap_address = node_manager_socket.accept()
            comm_buffer = ap_socket.recv(1024).decode()
            print('received: ', comm_buffer)
            comm_buffer_as_word_array = comm_buffer.split()
            if comm_buffer_as_word_array[0] == 'setConfig':
                swarmNode_config[STR_VXLAN_ID] = comm_buffer_as_word_array[1]
                swarmNode_config[STR_VETH1_VIP] = comm_buffer_as_word_array[2]
                swarmNode_config[STR_VETH1_VMAC] = comm_buffer_as_word_array[3]
                swarmNode_config[STR_COORDINATOR_VIP] = comm_buffer_as_word_array[4]
                swarmNode_config[STR_COORDINATOR_VMAC] = comm_buffer_as_word_array[5]
                swarmNode_config[STR_COORDINATOR_TCP_PORT] = int(comm_buffer_as_word_array[6])
                swarmNode_config[STR_AP_ID] = comm_buffer_as_word_array[7]
                swarmNode_config[STR_AP_IP] = ap_address[0]
                try:
                    install_swarmNode_config()
                except Exception as e:
                    print(f'Error installing config: {e} Leaving Access Point' )
                    cli_command = f'nmcli connection show --active'
                    res = subprocess.run(cli_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
                    ap_ssid = ''
                    for line in res.stdout.strip().splitlines():
                        if DEFAULT_IFNAME in line:
                            ap_ssid = line.split()[0]
                    cli_command = f'nmcli connection down id {ap_ssid}'
                    res = subprocess.run(cli_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )

                


def install_swarmNode_config():
    global swarmNode_config, join_queue, last_request_id
    
    
    vxlan_id = swarmNode_config[STR_VXLAN_ID]
    swarm_veth1_vip = swarmNode_config[STR_VETH1_VIP]
    swarm_veth1_vmac = swarmNode_config[STR_VETH1_VMAC]
    
    commands = [ # add the vxlan interface to the AP
                f'ip link add vxlan{vxlan_id} type vxlan id {vxlan_id} dev wlan0 remote {swarmNode_config[STR_AP_IP]} dstport 4789',
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
        # print('executing: ' + command)
        subprocess.run(command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
        
    get_if1_index_command = 'cat /sys/class/net/veth0/ifindex'
    get_if2_index_command = f'cat /sys/class/net/vxlan{vxlan_id}/ifindex'
    if1_index = subprocess.run(get_if1_index_command.split(), text=True , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if2_index = subprocess.run(get_if2_index_command.split(), text=True , stdout=subprocess.PIPE, stderr=subprocess.PIPE)   
    
    commands = [
        'nikss-ctl pipeline unload id 0',        
        'nikss-ctl pipeline load id 0 ./utils/nikss.o',
        f'nikss-ctl add-port pipe 0 dev veth0',
        f'nikss-ctl add-port pipe 0 dev vxlan{vxlan_id}',
        f'nikss-ctl table add pipe 0 ingress_route action id 2 key {if1_index.stdout} data {if2_index.stdout}',
        f'nikss-ctl table add pipe 0 ingress_route action id 2 key {if2_index.stdout} data {if1_index.stdout}',
        f"arp -s {swarmNode_config[STR_COORDINATOR_VIP]} {swarmNode_config[STR_COORDINATOR_VMAC]}" # THIS IS THE MAC OF THE COORDINATOR
    ]
    
    for command in commands:
        # print('executing: ' + command)
        subprocess.run(command.split(), text=True   , stdout=subprocess.PIPE, stderr=subprocess.PIPE )
    
    join_request_data = f"Join_Request {last_request_id} {NODE_UUID} {swarmNode_config[STR_VXLAN_ID]} {swarmNode_config[STR_VETH1_VIP]} {swarmNode_config[STR_VETH1_VMAC]} {swarmNode_config[STR_AP_ID]}"
    last_request_id = last_request_id + 1
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as coordinator_socket:
        print(f'connecting to {swarmNode_config[STR_COORDINATOR_VIP]}:{swarmNode_config[STR_COORDINATOR_TCP_PORT]}')
        coordinator_socket.settimeout(5)
        coordinator_socket.connect((swarmNode_config[STR_COORDINATOR_VIP], swarmNode_config[STR_COORDINATOR_TCP_PORT] ))
        coordinator_socket.sendall(bytes( join_request_data.encode() ))
        print(f'sent {join_request_data} to coordinator')

def exit_handler():
    logger.info('Handling exit')
    handle_disconnection()
        
        
def handle_disconnection():
    logger.debug( '\nHandling Disconnection:\n'  )
    exit_commands = [
        'ifconfig veth1 0.0.0.0',
        'nikss-ctl del-port pipe 0 dev veth0',
        'nikss-ctl del-port pipe 0 dev veth1',
        f"nikss-ctl del-port pipe 0 dev vxlan{swarmNode_config[STR_VXLAN_ID]}",
        'nikss-ctl table delete pipe 0 ingress_route',
        'nikss-ctl pipeline unload id 0 ',
        f"ip link delete vxlan{swarmNode_config[STR_VXLAN_ID]}"
    ]
    try:
        for command in exit_commands:
            res = subprocess.run( command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE )
            if (res.stderr != None):
                pass
              #  print(res.stderr)
        logger.debug( '\nDone Handling Disconnection:\n'  )
    except Exception as e:
        print(e)    

def monitor_wifi(control_queue):
    global ACCESS_POINT_IP
  
   
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
        logger.debug( '\noutput_line: ' + output_line )
        if output_line_as_word_array[1] == 'disconnected':
            print('disconnected from wifi')
            handle_disconnection()
        # if output_line_as_word_array[1] == 'connected':
        #     ACCESS_POINT_IP = get_ap_physical_ip_by_ifname('wlan0')
        #     print(ACCESS_POINT_IP)
        #     print('Connected To wifi')            
        #     handle_connection(node_manager_socket)

  
def main():
    print('program started')
    threading.Thread(target=handle_connection, args=() ).start()
    threading.Thread(target= monitor_wifi, args=(join_queue,) ).start()


if __name__ == '__main__':
    atexit.register(exit_handler)
    main()
