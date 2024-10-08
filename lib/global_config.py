# the ID of the current Access Point

this_swarm_id = '1000'
# ap_communication_switch_port = 500

swarm_backbone_switch_port = 501

REDIS_PORT = 6379
CASSANDRA_PORT = 9402

# here configure the subnet range that need to be allocated to the swarm
# here we assume a /24 subnet mask
this_swarm_subnet='192.168.10.0'
this_swarm_dhcp_start = 2
this_swarm_dhcp_end  = 200

# This is the ip and port number of the database
database_hostname = '172.18.0.2'
database_port = 9042

# This IP is used by the access points to reach the coordinator,
# this IP is the one configured on the smartedge-bb vxlan interface of the coordinator
coordinator_physical_ip = '192.168.100.6'

# this IP is used to reach the coordinator by the swarm nodes
# this IP is also configured on the smartedge-bb interface of the coordinator
coordinator_vip='192.168.10.1'

# this is the mac that is configured on the  smartedge-bb of the coordinator
coordinator_mac = '3e:a9:ef:fd:15:9e'

# this is a tcp port number used to reach the coordinator from the swarm nodes
coordinator_tcp_port = 29997

# this is a tcp port number used to reach the swarm node manager from the access points
# in order to send the swarm config
node_manager_tcp_port = 29997

# this is the default thrift port used for configuring the P4 switches in the network
default_thrift_port = 9090

# list of access points in the network, used to propagate configuration changes
# this list of IPs and MACs are the ones configured on the smartedge-bb on each access point
ap_list = {
    'AP:004': ['ae:41:1c:2d:6d:5c', '192.168.100.4'],
    'AP:003': ['72:33:e0:66:b3:8e', '192.168.100.3']
    }
