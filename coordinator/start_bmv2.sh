sudo docker run --privileged --rm --net=host --volume $(pwd):$(pwd) --workdir $(pwd) -i -t --name bmv2smartedge -d bmv2ap
sudo docker exec -d bmv2smartedge pip install thrift

