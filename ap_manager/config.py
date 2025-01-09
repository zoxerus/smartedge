import psutil 
import socket
import lib.global_config as global_config

# This a P4 switch port number for forwardign packets to other APs
# over the backbone network
ap_communication_switch_port = global_config.swarm_backbone_switch_port
wlan_switch_port = 509
ethernet_switch_port = 510

# This is the switch port number that goes to the coordinator
swarm_coordinator_switch_port = global_config.swarm_backbone_switch_port

# name of the default wlan interface to use
default_wlan_interface = 'wlan0'
default_ethernet_device = 'smartedge-bb'

default_coordinator_device =  default_ethernet_device


# currently assuming a /24 mask
this_swarm_subnet= global_config.this_swarm_subnet
this_swarm_dhcp_start = global_config.this_swarm_dhcp_start
this_swarm_dhcp_end = global_config.this_swarm_dhcp_end


# Hostname and Port numbers to connect to the database
database_hostname = global_config.database_hostname
database_port = global_config.database_port

# Coordinator IP and MAC to forward packets to the coordinator
coordinator_physical_ip = global_config.coordinator_physical_ip
coordinator_physical_mac = global_config.coordinator_physical_mac
coordinator_vip= global_config.coordinator_vip


# Coordinator TCP port for the node manager to communicate with the coordinator
# this info is sent by the AP to the swarm node.
coordinator_tcp_port = global_config.coordinator_tcp_port

# a TCP port number for the AP Manager to commmunicate with the node manager
node_manager_tcp_port = global_config.node_manager_tcp_port


# list of other APs in the network to communicate updates.
ap_list = global_config.ap_list
