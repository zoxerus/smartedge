try:
    from cassandra.cluster import Cluster
    from cassandra.policies import DCAwareRoundRobinPolicy
except:
    print('Cassandra python module not installed')

import lib.db.defines as db_defines

CASSANDRA_DEFAULT_PORT = 9042

# DATABASE QUERIES
QUERY_DATABASE_CREATE_KEYSPACE = f"""\
CREATE KEYSPACE IF NOT EXISTS {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE} \
WITH REPLICATION = {{ \
'class' : '{db_defines.NAMEOF_DATABASE_REPLICATION_STRATEGY}', \
'replication_factor' : '{db_defines.NUMBEROF_DATABASE_REPLICATION_FACTOR}' }}; \
                                """
                                
QUERY_DATABASE_CREATE_TABLE_ACTIVE_NODES =  f"""
CREATE TABLE IF NOT EXISTS {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE}.{db_defines.NAMEOF_DATABASE_SWARM_TABLE_ACTIVE_NODES}
(
{db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_ID} {db_defines.TYPEOF_DATABASE_FIELD_NODE_SWARM_ID} PRIMARY KEY,
{db_defines.NAMEOF_DATABASE_FIELD_NODE_UUID} {db_defines.TYPEOF_DATABASE_FIELD_NODE_UUID},
{db_defines.NAMEOF_DATABASE_FIELD_NODE_CURRENT_AP} {db_defines.TYPEOF_DATABASE_FIELD_NODE_CURRENT_AP},
{db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_STATUS} {db_defines.TYPEOF_DATABASE_FIELD_NODE_SWARM_STATUS},
{db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_IP} {db_defines.TYPEOF_DATABASE_FIELD_NODE_SWARM_IP},
{db_defines.NAMEOF_DATABASE_FIELD_NODE_SWARM_MAC} {db_defines.TYPEOF_DATABASE_FIELD_NODE_SWARM_MAC},
{db_defines.NAMEOF_DATABASE_FIELD_NODE_PHYSICAL_MAC} {db_defines.TYPEOF_DATABASE_FIELD_NODE_PHYSICAL_MAC},
{db_defines.NAMEOF_DATABASE_FIELD_LAST_UPDATE_TIMESTAMP} {db_defines.TYPEOF_DATABASE_FIELD_LAST_UPDATE_TIMESTAMP}
);
"""

QUERY_DATABASE_CREATE_TABLE_DEFAULT_SWARM =  f"""
CREATE TABLE IF NOT EXISTS {db_defines.NAMEOF_DATABASE_SWARM_KEYSPACE}.{db_defines.NAMEOF_DATABASE_SWARM_TABLE_DEFAULT_SWARM}
(
{db_defines.NAMEOF_DATABASE_FIELD_NODE_UUID} {db_defines.TYPEOF_DATABASE_FIELD_NODE_UUID} PRIMARY KEY,
{db_defines.NAMEOF_DATABASE_FIELD_NODE_CURRENT_AP} {db_defines.TYPEOF_DATABASE_FIELD_NODE_CURRENT_AP},
{db_defines.NAMEOF_DATABASE_FIELD_NODE_CURRENT_SWARM} {db_defines.TYPEOF_DATABASE_FIELD_NODE_CURRENT_SWARM},
{db_defines.NAMEOF_DATABASE_FIELD_LAST_UPDATE_TIMESTAMP} {db_defines.TYPEOF_DATABASE_FIELD_LAST_UPDATE_TIMESTAMP}
);
"""