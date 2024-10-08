This code has been tested or Raspberry Pi 5 devices and is comprised of three parts: 
1. Access Point Manager: runs in the RPi5 devices that are meant to act as Access Point, it monitors new nodes joining the wifi network, and inserts their details in the swarm database, and assigns swarm IDs.
2. Coordinator: it handles join and leave requests from the nodes in the swarm, and it install the forwarding entries in the AP P4 switch to handle traffic routing.
3. Node Manager: when the node joins an AP, the node manager recieves the swarm configuration from the AP Manager, and then forms and sends a join request to the coordinator.

# Requirements
1. in the RPi5 devices that are meant to work as Access Points:
   - start a wifi hotspot. for example using nmcli:
     ```
       nmcli con add type wifi ifname wlan0 con-name Hotspot autoconnect yes ssid R1AP
       nmcli con modify Hotspot 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared
       nmcli con modify Hotspot wifi-sec.key-mgmt wpa-psk
       nmcli con modify Hotspot wifi-sec.psk "123456123"
       nmcli con up Hotspot
     ```
   - Install the bmv2 docker image `docker pull p4lang/pi`
   - create a virtual python environment inside the folder ./ap_manager/client_monitor `python3 -m venv .venv`
   - source the new environment `source ./.venv/bin/activate`
   - Install the required python modules: `pip install psutil aenum cassandra-driver`
2. In the RPi5 devices that are meant to work as swarm nodes:
   -  download and install the NIKSS switch, follow instructions on the link: https://github.com/NIKSS-vSwitch/nikss
3. In the device that is meant to work as a coordinator:
   - install the bmv2 docker container `docker pull p4lang/pi`
   - install the cassandra docker container `docker pull cassandra`
   - install python modules `pip install aenum cassandra-driver`
  
# Configuring the Network
1. Configure loopback addresses on APs and Nodes, consult the files /ap_manager/client_monitor/config.py and /node_manager/config.py for instructions on how to do so
2. in the respective config.py files mentioned in step 1, configure the default_wlan_interface to point to the wifi device name.
3. In the global config file /lib/config.py configure the list ap_list with names, mac, and ip addresses of the access points in the network for example.
4. In the global config file set the ip where the database is hosted by setting the variabla database_hostname and database_port
5. In the global config file set the IP where the coordinator is located by setting the variables coordinator_physical_ip and coordinator_mac
6. In the global config file set the variables this_swarm_subnet and coordinator_vip (you can also keep the default values )

# Starting the Network
1. Clone the Repo to the devices meant to work as Access Points and set the config as in the section Congifuring the Network
2. Run the file ./ap_manager/run_ap_container.sh
3. Start the ap_manager by source the file ./ap_manager/client_monitor/run.sh for example:
   ```
   cd ./ap_manager/client_monitor
   . ./run.sh
   ```
4. Clone the repo to the coordinator device and se the config as in the section Configuring the Network
5. Start the bmv2 in the coordinator by running the file ./coordinator/start_bmv2.sh
6. Start the database in the coordinator by running the file ./coordinator/start_cassandra_docker.sh
7. Start the coordinator by sourcing the file run.sh for example `. ./run.sh`
8. Clone the repo to the devices meant to work as swarm nodes and set the config as in the section Configuring the Network.
9. Start the node_manager by source the file ./node_manager/run.sh for example `. ./run.sh`
10. Connect the swarm node to one of the APs by using the command `nmcli dev wifi connect R1AP password 123456123 ifname wlan0`
