# This tells python to look for files in parent folders
import sys
# setting path
sys.path.append('..')
sys.path.append('../..')

import lib.db.cassandra_db as cassandra_db
import lib.database_comms as db

db_in_use = db.STR_DATABASE_TYPE_CASSANDRA


def connect_to_database(host, port):
        # CONNECT TO THE DATABASE
        cluster = cassandra_db.Cluster(
            contact_points=[host], 
                        port=port, 
                        load_balancing_policy=cassandra_db.DCAwareRoundRobinPolicy(local_dc='datacenter1'),
                        protocol_version=5
        )
        session = cluster.connect()
        return session

print('\n\n\n')
database_session = connect_to_database('0.0.0.0', 9042)

database_session.execute(cassandra_db.QUERY_DATABASE_CREATE_TABLE_DEFAULT_SWARM)

db.insert_into_thing_directory_with_node_info(database_typ=db_in_use, session=database_session,
                                                node_uuid='SN:01', current_ap='AP:01',swarm_id=0)


db.update_tdd_with_new_node_status(database_type=db_in_use, session=database_session, node_uuid='SN:01', node_current_ap='AP:02', node_current_swarm=1)