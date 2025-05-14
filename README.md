# instlling python requirements
- tested with python 3.11: install python venv module
```
sudo apt install python3-venv
```

# installing dependencies
1- run ./shell_scripts/install_requirements.

2- make sure thrift libraries are installed correctly, if not try to manuall run thrift installation,
     files are in ./shell_scripts/ci first run ./install-thrift-deps.sh and then run ./install-thrift.sh

3- make sure to install thrift libraries in the virtual environment, the run.sh script should handle the creation of the virtual environment and installing the python modules. if some modules are not installed correctly (for example thrift) source the virtual environment 

    source .venv/bin/activate and then
    sudo .venv/bin/pip install thrift==0.13.0

# configuration

1- add a lo:0 interface on each of the nodes each with a unique ip. this is used to generate the IDs of the nodes. for example use the following to add a device with ID 2.
```
sudo ip addr add 127.0.0.2/32 dev lo label lo:0
```

keep all the ids low integers preferably start at 2, 3, 4, ...

The format for IDs will be 'XX:12:34:56' where xx could be AP for access point, SN for smart node

open ./lib/global_config.py at the top of the file is the list of the access points, each with two IP addresses, make sure to set the correct IDs, with the corresponding IP address of eth0.
also set the COORDINATOR_IP variable to point to the coordinator.

you can change the ips to the 192.168.137.0 network to something else that corresponds to your physcial ip addresses.

if you need to change the ip addresses of the 192.168.100.0 network to something else, make sure to also change the variable: 
```
backbone_subnet='192.168.100.0'  #smartedge-bb
```


# running the scripts
on the coordinator node run the log collector
```
python3 log_server.py
```

run the cassandra database 
```
sudo docker run --rm -d --name cassandra --hostname cassandra --network host cassandra
```
wait about a minute or two, as it takes some time to run

then

start the scripts by sourcing the run.sh file with the correct arguments:
    first argument: type of node, second argument logging level [10,20,30,40,50] 10 is for debug 50 is for critical.

to run node as coordinator do ```source run.sh co 10```

to run node as access point do ```source run.sh ap 10```

to run node as smart node do ```source run.sh ap 10```


# integration with TUB
- The Swarm coordinator can be reached on the TCP port 9999.

- message format for requesting nodes to join is :
```
message = {'Type': 'Type of message',
           'nids': ['id1', 'id2'] 
           }
```
 
Where Type can be 'njl' for node joinning list or 'nll' for nodes leaving list.


- message format for requesting nodes to join is :
```
message = {'Type': 'njl',
           'nids': ['SN:00:00:02', 'SN:00:00:03'] 
           }
```


- message format for requesting nodes to be kicked out is :
```
message = {'Type': 'nll',
           'nids': ['SN:00:00:02', 'SN:00:00:03'] 
           }

```