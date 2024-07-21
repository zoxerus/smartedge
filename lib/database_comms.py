import lib.db.cassandra_db as cassandra_db
import lib.db.redis_db as redis_db
import lib.db.defines as db_defines


# SET PARAMETERS FOR CONNECTING TO THE DATABASE
# CASSANDRA_HOST = '172.18.0.2'

STR_DATABASE_TYPE_REDIS = 'redis'
STR_DATABASE_TYPE_CASSANDRA = 'cassandra'


def init_database(database_type, host, port):
    
    if database_type == STR_DATABASE_TYPE_REDIS:
        return redis_db.redis.Redis(host=host, port=port, decode_responses=True)

    elif database_type == STR_DATABASE_TYPE_CASSANDRA:        
        # CONNECT TO THE DATABASE
        cluster = cassandra_db.Cluster(
            contact_points=[host], 
                        port=port, 
                        load_balancing_policy=cassandra_db.DCAwareRoundRobinPolicy(local_dc='datacenter1'),
                        protocol_version=5
        )
        session = cluster.connect()
        session.execute(f'DROP TABLE IF EXISTS {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE}.{db_defines.NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES}')
        # CREATE A NAME SPACE IN THE DATABSE FOR STORING SWARM INFO
        session.execute( cassandra_db.QUERY_DATABASE_CREATE_KEYSPACE )
        # CREATE A TABLE TO MANAGE ACTIVE SWARM NODES
        session.execute(cassandra_db.QUERY_DATABASE_CREATE_TABLE)
        return session
    
def connect_to_database(database_type, host, port):
    if database_type == STR_DATABASE_TYPE_REDIS:
        return redis_db.redis.Redis(host=host, port=port, decode_responses=True)

    elif database_type == STR_DATABASE_TYPE_CASSANDRA:        
        # CONNECT TO THE DATABASE
        cluster = cassandra_db.Cluster(
            contact_points=[host], 
                        port=port, 
                        load_balancing_policy=cassandra_db.DCAwareRoundRobinPolicy(local_dc='datacenter1'),
                        protocol_version=5
        )
        session = cluster.connect()
        return session


def get_node_swarm_mac_by_swarm_ip(database_type, session, node_swarm_ip):
    if database_type == STR_DATABASE_TYPE_CASSANDRA:
        query = f"""SELECT {db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_MAC} from 
        {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE}.{db_defines.NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES}
        WHERE {db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_IP} = '{node_swarm_ip}' ALLOW FILTERING; """
        result = session.execute(query)
        if (result.one() == None or len(result.one()) > 1 ):
            print(f'Node {node_swarm_ip} not found in database or is duplicate, Node rejected')
        return result.one()[0]


def update_db_with_joined_node(database_type, session, node_uuid, node_swarm_id):
    
    if database_type == STR_DATABASE_TYPE_CASSANDRA:
        query = f"""UPDATE {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE}.{db_defines.NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES}
        SET {db_defines.NAMEOF_DATABASE_FIELD_NODE_UUID} = {node_uuid}, 
        {db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_STATUS} = '{db_defines.SWARM_STATUS.JOINED.value}'
        WHERE {db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_ID} = {node_swarm_id};
        """
        return session.execute(query)