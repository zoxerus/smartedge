sudo docker run --privileged --rm --net=host --volume $(pwd):$(pwd) --workdir $(pwd) -i -t --name bmv2smartedge -d p4jet
