# the ID of the current Access Point

this_swarm_id = '1000'
# ap_communication_switch_port = 500

swarm_backbone_switch_port = 501

REDIS_PORT = 6379
CASSANDRA_PORT = 9402

# currently assuming a /24 mask
this_swarm_subnet='192.168.10.0'
this_swarm_dhcp_start = 2
this_swarm_dhcp_end  = 200

database_hostname = '172.18.0.2'
database_port = 9042

coordinator_physical_ip = '192.168.100.6'
coordinator_vip='192.168.10.1'
coordinator_mac = '5a:62:5c:4a:87:59 '
coordinator_tcp_port = 29997
node_manager_tcp_port = 29997

default_thrift_port = 9090


ap_list = {
    'AP:004': ['4e:fb:2e:69:a7:53', '192.168.100.4'],
    'AP:005': ['52:3c:a9:f6:e2:29', '192.168.100.5']
    }
