import psutil 

# Configuring a unique IP on the loopback interface to be used as a node UUID
# Currently only using las byte of lo:0 as an ID
# This can be configured for example using:
# ifconfig lo:0 127.0.1.1 netmask 255.255.255.255 up
loopback_if = 'lo:0'
loopback_id = psutil.net_if_addrs()[loopback_if][0][1].split('.')
this_ap_id = f'AP:{int(loopback_id[3]):03}'


# This a P4 swithc port number for forwardign packets to other APs
# over the backbone network
ap_communication_switch_port = 501

# This is the switch port number that goes to the coordinator
swarm_coordinator_switch_port = 501

# name of the default wlan interface to use
default_wlan_interface = 'wlan0'


# currently assuming a /24 mask
this_swarm_subnet='192.168.10.0'
this_swarm_dhcp_start = 2
this_swarm_dhcp_end = 200


# Hostname and Port numbers to connect to the database
database_hostname = '192.168.100.1'
database_port = 9042

# Coordinator IP and MAC to forward packets to the coordinator
coordinator_vip='192.168.10.1'
coordinator_mac=' d6:87:bb:03:e0:11'

# Coordinator TCP port for the node manager to communicate with the coordinator
# this info is sent by the AP to the swarm node.
coordinator_tcp_port = 29997

# a TCP port number for the AP Manager to commmunicate with the coordinator
# TODO: implement or delete this
node_manager_tcp_port = 29997


# list of other APs in the network to communicate updates.
ap_list = {
    'AP:004': '192.168.100.4',
    'AP:005': '192.168.100.5', 
    'AP:006': '192.168.100.6'
    }
