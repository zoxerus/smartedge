# the ID of the current Access Point

this_swarm_id = '1000'

swarm_backbone_switch_port = 510

REDIS_PORT = 6379
CASSANDRA_PORT = 9402

# here configure the subnet range that need to be allocated to the swarm
# here we assume a /24 subnet mask
this_swarm_subnet='10.0.1.0'  ## this is the subnet to use for the swarm
this_swarm_dhcp_start = 2         # this is the first IP to be assigned to the swarm node e.g: 192.168.10.2
this_swarm_dhcp_end  = 200        # last IP to be assigned e.g: 192.168.10.200  so it supports 199 nodes (arbitrary number can be changed to any)


# This is the ip and port number of the database
## This is the IP of the database, in my implementation the DB is running on the same node as the coordinator
## so for the coordinator, this is an internal IP on the docker network.
## in case of Access Points (and the DB is running on the coordinator node) this would be the IP of the coordinator (IP of the smartedge-bb interface of the coordinator)
## e.g 192.168.100.6
database_hostname = '0.0.0.0'  
database_port = 9042

# This IP is used by the access points to reach the coordinator,
# this IP is the one configured on the smartedge-bb vxlan interface of the coordinator
coordinator_physical_ip = '10.2.1.6'

# this is the mac that is of the  smartedge-bb of the coordinator
coordinator_physical_mac = '02:00:10:00:00:06'  


# this IP is used to reach the coordinator by the swarm nodes
# this IP is also configured on the smartedge-bb interface of the coordinator
coordinator_vip='10.0.1.1'



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
    # ID of AP       MAC of smartedge-bb    IP of smartedge-bb
    'AP:004': [     '00:00:00:00:00:04',    '192.168.100.4'],
    'AP:005': [     '00:00:00:00:00:05',    '192.168.100.5']
    }
