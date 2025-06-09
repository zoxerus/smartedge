# Installing Dependencies
### 1- For Access Point and Coordinator nodes, you need to have thrift libraries installed  
For this run from the main directory
```
./shell_scripts/install_requirements.sh
```
Then make sure to install the following packages
```
sudo apt install python3-venv python3-dev net-tools screen
```
Now create a virtual environment running the command
```
python3 -m venv .venv
```

Source the virtual environment 
```
source .venv/bin/activate
```

Then install the required python3 modules
```
.venv/bin/pip install aenum cassandra-driver psutil netifaces thrift==0.13.0
```

You might as well need to install docker engine for the later steps  
It can be installed from the link:
https://docs.docker.com/engine/install/

### 2- For coordinator node only, a cassandra docker image is needed
This image is installed automatically when the coordinator script is run  
Have a look at the script in ./shell_scripts/run_cassandra_docker.sh

### 3- For Access Points only, a P4 switch is needed  
For devices with x86 processors it can be installed from the link:  
https://github.com/p4lang/behavioral-model

While for devices wit ARM processors e.g Raspberry Pi a docker image can be installed.
Check the script  
./shell_scripts/fetch_se_network_images.sh



### 4- For Smart Nodes only, a P4 ebpf software switch is needed
First make sure to install the following packages
```
sudo apt install python3-venv python3-dev net-tools screen
```

The switch can be installed from the link:  
https://github.com/NIKSS-vSwitch/nikss

Now create a virtual environment running the command
```
python3 -m venv .venv
```

Source the virtual environment 
```
source .venv/bin/activate
```

Then install the required python3 modules
```
.venv/bin/pip install aenum psutil netifaces
```


# Configuration

1- add a lo:0 interface on each of the nodes each with a unique ip. this is used to generate the IDs of the nodes. for example use the following to add a device with ID 2.
```
sudo ip addr add 127.1.0.2/32 dev lo label lo:0
```

keep all the ids low integers preferably start at 2, 3, 4, ...

The format for IDs will be 'XX123456' where xx could be AP for access point, SN for smart node, or CO for coordinator

if you need to change the ip addresses of the 192.168.100.0 network to something else, make sure to also change the variable: 
```
backbone_subnet='192.168.100.0'  #smartedge-bb
```


# Running the scripts
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


# Integration with TUB
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