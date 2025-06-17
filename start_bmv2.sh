sudo docker run --privileged --rm --net=host --volume $(pwd):$(pwd) --workdir $(pwd) -i -t --name bmv2smartedge -d p4jet
sudo docker exec -d bmv2smartedge  pip install thrift
sudo docker exec -d bmv2smartedge  simple_switch ./p4app/ap.json
