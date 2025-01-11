try:
    import redis
    from redis_om import (
        EmbeddedJsonModel,
        JsonModel,
        Field,
        Migrator,
    )
    
    
    
    
    
    REDIS_DEFAULT_PORT = 6379


    class Swarm_Node(EmbeddedJsonModel):
        pass


except:
    print('Error Importing Redis Python Module, Skpping Redis Database')

