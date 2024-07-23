# the ID of the current Access Point



this_ap_id = '1101'
this_swarm_id = '1000'
# ap_communication_switch_port = 500


swarm_backbone_switch_port = 501

REDIS_PORT = 6379
CASSANDRA_PORT = 9402

# currently assuming a /24 mask
this_swarm_subnet='192.168.10.0'
this_swarm_dhcp_start = 2
database_hostname = '172.18.0.2'
database_port = 9042

this_ap_vip='192.168.10.1'
this_ap_vmac='00:00:00:00:00:01'

coordinator_tcp_port = 29998


ap_list = {
    'AP:004': ['4e:fb:2e:69:a7:53', '192.168.100.4'],
    'AP:005': ['52:3c:a9:f6:e2:29', '192.168.100.5'], 
    'AP:006': ['5a:62:5c:4a:87:59', '192.168.100.6']
    }
