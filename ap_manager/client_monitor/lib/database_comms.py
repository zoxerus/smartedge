try:
    from cassandra.cluster import Cluster
    from cassandra.policies import DCAwareRoundRobinPolicy
    from lib.db.cassandra_db import *
except:
    print('Problem importing Cassandra')
try:
    from db.redis_db import *
    from db.cassandra_db import *
except:
    print('Problem importing Redis')
    


# SET PARAMETERS FOR CONNECTING TO THE DATABASE
CASSANDRA_HOST = '192.168.100.1'
CASSANDRA_PORT = 9042

STR_DATABASE_TYPE_REDIS = 'redis'
STR_DATABASE_TYPE_CASSANDRA = 'cassandra'


def init_database(database_type, host, port):
    
    if database_type == STR_DATABASE_TYPE_REDIS:
        return redis.Redis(host='localhost', port=6379, decode_responses=True)

    elif database_type == STR_DATABASE_TYPE_CASSANDRA:        
        # CONNECT TO THE DATABASE
        cluster = Cluster(
            contact_points=[host], 
                        port=port, 
                        load_balancing_policy=DCAwareRoundRobinPolicy(local_dc='datacenter1'),
                        protocol_version=5
        )
        session = cluster.connect()
        # session.execute(f'DROP TABLE IF EXISTS {NAMEOF_DATABASE_SWARM_KEYSPACE}.{NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES}')
        # CREATE A NAME SPACE IN THE DATABSE FOR STORING SWARM INFO
        # session.execute( QUERY_DATABASE_CREATE_KEYSPACE )
        # CREATE A TABLE TO MANAGE ACTIVE SWARM NODES
        # session.execute(QUERY_DATABASE_CREATE_TABLE)
        return session



def get_node_swarm_mac_by_swarm_ip(database_type, session, node_swarm_ip):
    if database_type == STR_DATABASE_TYPE_CASSANDRA:
        query = f"""SELECT {NAMEOF_DATABASE_FIELD_NODE_SWARM_MAC} from 
        {NAMEOF_DATABASE_SWARM_KEYSPACE}.{NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES}
        WHERE {NAMEOF_DATABASE_FIELD_NODE_SWARM_IP} = '{node_swarm_ip}' ALLOW FILTERING; """
        result = session.execute(query)
        if (result.one() == None or len(result.one()) > 1 ):
            print(f'Node {node_swarm_ip} not found in database or is duplicate, Node rejected')
        return result.one()[0]


def update_db_with_joined_node(database_type, session, node_uuid, node_swarm_id):
        query = f"""UPDATE {NAMEOF_DATABASE_SWARM_KEYSPACE}.{NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES}
        SET {NAMEOF_DATABASE_FIELD_NODE_UUID} = {node_uuid}, 
        {NAMEOF_DATABASE_FIELD_NODE_SWARM_STATUS} = {SWARM_STATUS.JOINED.value}
        WHERE {NAMEOF_DATABASE_FIELD_NODE_SWARM_ID} = {node_swarm_id};
        """
        return session.execute(query)


def insert_node_into_swarm_database(database_type, session, host_id, this_ap_id, node_vip, node_vmac, node_phy_mac):
    query = f"""
    INSERT INTO {NAMEOF_DATABASE_SWARM_KEYSPACE}.{NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES} (
    {NAMEOF_DATABASE_FIELD_NODE_SWARM_ID}, {NAMEOF_DATABASE_FIELD_NODE_CURRENT_AP},
    {NAMEOF_DATABASE_FIELD_NODE_SWARM_STATUS}, {NAMEOF_DATABASE_FIELD_LAST_UPDATE_TIMESTAMP}, 
    {NAMEOF_DATABASE_FIELD_NODE_SWARM_IP}, {NAMEOF_DATABASE_FIELD_NODE_SWARM_MAC},
    {NAMEOF_DATABASE_FIELD_NODE_PHYSICAL_MAC})
    VALUES ({host_id}, '{this_ap_id}', '{SWARM_STATUS.PENDING.value}', toTimeStamp(now() ),
    '{node_vip}', '{node_vmac}', '{node_phy_mac}') IF NOT EXISTS;
    """
    session.execute(query)


def get_next_available_host_id_from_swarm_table(database_typ, session, first_host_id, max_host_id):
    if database_typ == STR_DATABASE_TYPE_CASSANDRA:    
        query = f""" SELECT {NAMEOF_DATABASE_FIELD_NODE_SWARM_ID} FROM 
            {NAMEOF_DATABASE_SWARM_KEYSPACE}.{NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES}"""
        result = session.execute(query)
        id_list = []
        for row in result:

            id_list.append(row[0])
        print(id_list)
        if (id_list == []):
            return first_host_id
        return min(set(range(first_host_id, max_host_id + 1 )) - set(id_list))
    
def delete_node_from_swarm_database(database_type, session, node_swarm_id):
    if database_type == STR_DATABASE_TYPE_CASSANDRA:
        query = f"""
            DELETE FROM {NAMEOF_DATABASE_SWARM_KEYSPACE}.{NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES} 
            WHERE {NAMEOF_DATABASE_FIELD_NODE_SWARM_ID} = {node_swarm_id};
            """
        session.execute(query)