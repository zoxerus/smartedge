try:
    import redis
    from redis_om import (
        EmbeddedJsonModel,
        JsonModel,
        Field,
        Migrator,
    )


    class Swarm_Node(EmbeddedJsonModel):
        pass
except:
    print('Problem importing Redis')