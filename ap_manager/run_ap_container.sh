sudo docker run --privileged --rm --net=host --volume $(pwd):$(pwd) --workdir $(pwd) -i -t --name bmv2ap -d p4jet
