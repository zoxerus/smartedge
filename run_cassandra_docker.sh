if [ "$(sudo docker container inspect -f '{{.State.Status}}' 'cassandra' )" != "running" ]; then
    echo "Starting Cassandra Container"
    sudo docker network create cassandra
    sudo docker run --rm -d --name cassandra --hostname cassandra --network cassandra --expose 9042 --publish 9042:9042 cassandra
else echo "Cassandra container is running"
fi