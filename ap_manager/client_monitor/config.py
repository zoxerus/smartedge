import psutil 
loopback_if = 'lo:0'
loopback_id = psutil.net_if_addrs()[loopback_if][0][1].split('.')

this_ap_id = f'AP:{int(loopback_id[3]):03}'

ap_communication_switch_port = 501


swarm_coordinator_switch_port = 501

default_wlan_interface = 'wlan0'

# currently assuming a /24 mask
this_swarm_subnet='192.168.10.0'
this_swarm_dhcp_start = 2
this_swarm_dhcp_end = 200



database_hostname = '192.168.100.1'
database_port = 9042

coordinator_vip='192.168.10.1'
coordinator_mac=' d6:87:bb:03:e0:11'

coordinator_tcp_port = 29997
node_manager_tcp_port = 29997

ap_list = {
    'AP:004': '192.168.100.4',
    'AP:005': '192.168.100.5', 
    'AP:006': '192.168.100.6'
    }
