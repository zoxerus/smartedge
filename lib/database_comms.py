import lib.db.cassandra_db as cassandra_db
# import lib.db.redis_db as redis_db
import lib.db.defines as db_defines

db_logger = None

STR_DATABASE_TYPE_REDIS = 'redis'
STR_DATABASE_TYPE_CASSANDRA = 'cassandra'

DATABASE_IN_USE = None
DATABASE_SESSION = None

def init_database(host, port):
    
    if DATABASE_IN_USE == STR_DATABASE_TYPE_REDIS:
        return # redis_db.redis.Redis(host=host, port=port, decode_responses=True)

    elif DATABASE_IN_USE == STR_DATABASE_TYPE_CASSANDRA:        
        # CONNECT TO THE DATABASE
        cluster = cassandra_db.Cluster(
            contact_points=[host], 
                        port=port, 
                        load_balancing_policy=cassandra_db.DCAwareRoundRobinPolicy(local_dc='datacenter1'),
                        protocol_version=5
        )
        session = cluster.connect()
        # session.execute(f'DROP TABLE IF EXISTS {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE}.{db_defines.NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES}')
        # CREATE A NAME SPACE IN THE DATABSE FOR STORING SWARM INFO
        query = cassandra_db.QUERY_DATABASE_CREATE_KEYSPACE
        result = session.execute( query )
        db_logger.debug(f"Executed database query:\n\t {query}\n\tgot result:\n\t\t{result.all()}")
        
        # CREATE A TABLE TO MANAGE ACTIVE SWARM NODES
        query = cassandra_db.QUERY_DATABASE_CREATE_TABLE_ACTIVE_NODES
        result = session.execute(cassandra_db.QUERY_DATABASE_CREATE_TABLE_ACTIVE_NODES)
        db_logger.debug(f"Executed database query:\n\t {query}\n\tgot result:\n\t\t{result.all()}")
        
        # query = cassandra_db.QUERY_DATABASE_CREATE_TABLE_DEFAULT_SWARM
        # result = session.execute(cassandra_db.QUERY_DATABASE_CREATE_TABLE_DEFAULT_SWARM)
        # db_logger.debug(f"Executed database query:\n\t {query}\n\tgot result:\n\t\t{result.all()}")
        return session
    
def connect_to_database(host, port):
    if DATABASE_IN_USE == STR_DATABASE_TYPE_REDIS:
        return # redis_db.redis.Redis(host=host, port=port, decode_responses=True)

    elif DATABASE_IN_USE == STR_DATABASE_TYPE_CASSANDRA:        
        # CONNECT TO THE DATABASE
        cluster = cassandra_db.Cluster(
            contact_points=[host], 
                        port=port, 
                        load_balancing_policy=cassandra_db.DCAwareRoundRobinPolicy(local_dc='datacenter1'),
                        protocol_version=5
        )
        session = cluster.connect()
        return session


def get_node_swarm_mac_by_swarm_ip(node_swarm_ip):
    if DATABASE_IN_USE == STR_DATABASE_TYPE_CASSANDRA:
        query = f"""SELECT {db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_MAC} from 
        {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE}.{db_defines.NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES}
        WHERE {db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_IP} = '{node_swarm_ip}' ALLOW FILTERING; """
        result = DATABASE_SESSION.execute(query)
        db_logger.debug(f"Executed database query:\n\t {query}\n\tgot result:\n\t\t{result.all()}")
        if (result.one() == None or len(result.one()) > 1 ):
            db_logger.error(f'Node {node_swarm_ip} not found in database or is duplicate, Node rejected')
        return result.one()[0]


def update_db_with_joined_node(node_uuid, node_swarm_id):
    if DATABASE_IN_USE == STR_DATABASE_TYPE_CASSANDRA:
        query = f"""UPDATE {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE}.{db_defines.NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES}
        SET {db_defines.NAMEOF_DATABASE_FIELD_NODE_UUID} = '{node_uuid}', 
        {db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_STATUS} = '{db_defines.SWARM_STATUS.JOINED.value}'
        WHERE {db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_ID} = {node_swarm_id};
        """
        result =  DATABASE_SESSION.execute(query)
        db_logger.debug(f"Executed database query:\n\t {query}\n\tgot result:\n\t\t{result.all()}")
        return result
    
def insert_node_into_swarm_database(host_id, this_ap_id, node_vip, node_vmac, node_phy_mac):
    if DATABASE_IN_USE == STR_DATABASE_TYPE_CASSANDRA:
        query = f"""
        INSERT INTO {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE}.{db_defines.NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES} (
        {db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_ID}, {db_defines.NAMEOF_DATABASE_FIELD_NODE_CURRENT_AP},
        {db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_STATUS}, {db_defines.NAMEOF_DATABASE_FIELD_LAST_UPDATE_TIMESTAMP}, 
        {db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_IP}, {db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_MAC},
        {db_defines.NAMEOF_DATABASE_FIELD_NODE_PHYSICAL_MAC}
        )
        VALUES ({host_id}, '{this_ap_id}', '{db_defines.SWARM_STATUS.PENDING.value}', toTimeStamp(now() ),
        '{node_vip}', '{node_vmac}', '{node_phy_mac}') IF NOT EXISTS;
        """
        result =  DATABASE_SESSION.execute(query)
        db_logger.debug(f"Executed database query:\n\t {query}\n\tgot result:\n\t\t{result.all()}")
        return result


# GET NEXT AVAILABLE HOST ID FROM SWARM TABLE
def get_next_available_host_id_from_swarm_table(first_host_id, max_host_id):
    if DATABASE_IN_USE == STR_DATABASE_TYPE_CASSANDRA:    
        query = f""" SELECT {db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_ID} FROM 
            {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE}.{db_defines.NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES}"""
        result = DATABASE_SESSION.execute(query)
        db_logger.debug(f"Executed database query:\n\t {query}\n\tgot result:\n\t\t{result.all()}")
        id_list = []
        for row in result:
            id_list.append(row[0])
        if (id_list == []):
            db_logger.debug(f"getting next host id: id_list is empty: {id_list} returning {first_host_id}")
            return first_host_id
        result = min(set(range(first_host_id, max_host_id + 1 )) - set(id_list)) 
        db_logger.debug(f"getting next host id: {result}")
        return result 


# GET NODE INFO FROM TDD
def get_node_info_from_tdd(node_uuid):
    if DATABASE_IN_USE == STR_DATABASE_TYPE_CASSANDRA:    
        query = f""" 
        SELECT * FROM 
            {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE}.{db_defines.NAMEOF_DATABASE_SWARM_TABLE_DEFAULT_SWARM}
        WHERE {db_defines.NAMEOF_DATABASE_FIELD_NODE_UUID} = '{node_uuid}';
        """
        result =  DATABASE_SESSION.execute(query)
        db_logger.debug(f"Executed database query:\n\t {query}\n\tgot result:\n\t\t{result.all()}")
        return result
  

# INSERT INTO TDD
def insert_into_thing_directory_with_node_info(node_uuid, current_ap, swarm_id):
    if DATABASE_IN_USE == STR_DATABASE_TYPE_CASSANDRA:    
        query = f"""
        INSERT INTO {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE}.{db_defines.NAMEOF_DATABASE_SWARM_TABLE_DEFAULT_SWARM} (
            {db_defines.NAMEOF_DATABASE_FIELD_NODE_UUID}, 
            {db_defines.NAMEOF_DATABASE_FIELD_NODE_CURRENT_AP}, 
            {db_defines.NAMEOF_DATABASE_FIELD_NODE_CURRENT_SWARM}, 
            {db_defines.NAMEOF_DATABASE_FIELD_LAST_UPDATE_TIMESTAMP}
        ) VALUES 
        (
            '{node_uuid}', 
            '{current_ap}', 
            {swarm_id}, 
            toTimeStamp(now()) 
        ) IF NOT EXISTS;
            """
        result =  DATABASE_SESSION.execute(query)
        db_logger.debug(f"Executed database query:\n\t {query}\n\tgot result:\n\t\t{result.all()}")
        return result


    
def delete_node_from_swarm_database(node_swarm_id):
    if DATABASE_IN_USE == STR_DATABASE_TYPE_CASSANDRA:
        query = f"""
            DELETE FROM {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE}.{db_defines.NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES} 
            WHERE {db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_ID} = {node_swarm_id};
            """
        result =  DATABASE_SESSION.execute(query)
        db_logger.debug(f"Executed database query:\n\t {query}\n\tgot result:\n\t\t{result.all()}")
        return result
        
        
        
def update_tdd_with_new_node_status(node_uuid, node_current_ap, node_current_swarm):
    if DATABASE_IN_USE == STR_DATABASE_TYPE_CASSANDRA:
        query = f"""
        UPDATE 
        {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE}.{db_defines.NAMEOF_DATABASE_SWARM_TABLE_DEFAULT_SWARM}
        SET 
        {db_defines.NAMEOF_DATABASE_FIELD_NODE_CURRENT_AP} = '{node_current_ap}', 
        {db_defines.NAMEOF_DATABASE_FIELD_NODE_CURRENT_SWARM} = {node_current_swarm}
        WHERE {db_defines.NAMEOF_DATABASE_FIELD_NODE_UUID} = '{node_uuid}';
        """
        result =  DATABASE_SESSION.execute(query)
        db_logger.debug(f"Executed database query:\n\t {query}\n\tgot result:\n\t\t{result.all()}")
        return result