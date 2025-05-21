#!/bin/bash


SE_BB_VXLAN_ID=10000

### Function Definitions
### this function extracts a string between quotations from the provided input
### used to read the configs from the global_config.py file
extract_quoted_strings() {
  local input="$1"
  # Use grep to extract quoted strings, then remove the quotes using sed
  echo "$input" | grep -Eo '"[^"]*"|'\''[^'\'']*'\''' | sed -E 's/^["'\''"]|["'\''"]$//g'
}


# This function is used to generate swarm IPs
nextip(){
    IP=$1
    IP_HEX=$(printf '%.2X%.2X%.2X%.2X\n' `echo $IP | sed -e 's/\./ /g'`)

    NEXT_IP_HEX=$(printf %.8X `echo $(( 0x$IP_HEX + $2 ))`)
    NEXT_IP=$(printf '%d.%d.%d.%d\n' `echo $NEXT_IP_HEX | sed -r 's/(..)/0x\1 /g'`)
    echo "$NEXT_IP"
}

### This while loop looks into the global_config.py file and extracts the relevant configurations
while IFS= read -r line; do 
    if [[ "$line" == *"this_swarm_subnet="* ]]; then 
        SWARM_SUBNET=$(extract_quoted_strings "$line"); 
        echo "This Swarm Subnet $SWARM_SUBNET"; 

    elif [[ "$line" == *"this_swarm_subnet_mask="* ]]; then 
        SWARM_SUBNET_MASK=$(extract_quoted_strings "$line"); 
        echo "This Swarm Subnet MASK $SWARM_SUBNET_MASK "; 

    elif [[ "$line" == *"backbone_subnet="* ]]; then 
        BACKBONE_SUBNET=$(extract_quoted_strings "$line"); 
        echo "Backbone Subnet $SWARM_SUBNET_MASK "; 

    elif [[ "$line" == *"backbone_subnetmask="* ]]; then 
        BACKBONE_MASK=$(extract_quoted_strings "$line"); 
        echo "Backbone Subnet MASK $SWARM_SUBNET_MASK "; 
    fi 

done < ./lib/global_config.py


# Check if number of parameters passed to the script is equal to 2
if [ "$#" != '2' ] || [[ "${BASH_SOURCE[0]}" == "${0}" ]] ; then
    echo -e "\e[32mError:\e[0m"
    echo -e "Script must be sourced with parameters: \nparam1 Script Type: [ap, co, nd] \nparam2 Log LeveL: [10,20,30,40,50] where 10 is for Debug, 20 for info, 30 for warning, 40 for Error, and 50 is for Critical"
    echo -e "for example:\nsource ./run.sh ap 1\n"
    return
fi

# read the script Role from first parameters and the numeric ID of the node from the second parameter
export ROLE=$1
# export NUMID=$2
export LOGLEVEL=$2


# Get Node ID from hostname
# HOST_NAME=$(cat /etc/hostname)
# NUMID=$(echo "$HOST_NAME" | grep -oE '[0-9]+' | head -n 1)



# generate the IP addresses for the node

l0_ip=$(ifconfig lo:0 | grep "inet " | awk '{print $2}' | cut -d/ -f1)
# Split the IP address into its four octets (bytes) using IFS

IFS='.' read -r octet1 octet2 octet3 octet4 <<< "$l0_ip"

# Validate each octet is between 0 and 255
for octet in $octet1 $octet2 $octet3 $octet4; do
    # Check if it's purely numeric and within the valid range
    if ! [[ "$octet" =~ ^[0-9]+$ ]] || [ "$octet" -lt 0 ] || [ "$octet" -gt 255 ]; then
        echo "Error: Invalid octet value '$octet' in IP address. Each octet must be between 0 and 255."
        exit 1
    fi
done


# Convert the lowest three bytes (octets 2, 3, and 4) to an integer
# The formula is: (octet2 * 256^2) + (octet3 * 256^1) + (octet4 * 256^0)
# which simplifies to: (octet2 * 65536) + (octet3 * 256) + octet4
# Bash arithmetic expansion $((...)) is used for the calculation.

NUMID=$(( (octet2 * 65536) + (octet3 * 256) + octet4 ))

[[ "$VIRTUAL_ENV" == "" ]]; INVENV=$?

if [ $INVENV -eq "0" ]; then
    echo -e "Virtual Environment not sourced"
    if [ -d ".venv"  ]; then
        echo "sourcing from .venv"

        source ./.venv/bin/activate
        
    else 
        echo -e "Create and setup a Virtual Environment first"
        exit 1
        
    fi
fi 


case $ROLE in
# Coordinator:
    co)
    echo "Role is set to Coordinator"
    /bin/bash ./shell_scripts/run_cassandra_docker.sh

    # Genereate the MAC address for the Coordinator
    # SWARM_IP=$(nextip $SWARM_SUBNET 254)
    
    SWARM_IP=10.1.255.254
    # BACKBONE_IP=$(nextip $BACKBONE_SUBNET 254)
    oldMAC=00:00:00:00:00:00
    IP_HEX=$(printf '%.2X%.2X%.2X%.2X\n' `echo $SWARM_IP | sed -e 's/\./ /g'`)
    rawOldMac=$(echo $oldMAC | tr -d ':')
    rawNewMac=$(( 0x$rawOldMac + 0x$IP_HEX ))

    final_mac=$(printf "%012x" $rawNewMac | sed 's/../&:/g;s/:$//')
    
    # sudo ip link delete smartedge-bb
    sudo ip link add smartedge-bb type vxlan id $SE_BB_VXLAN_ID group 239.1.1.1 dstport 0 dev eth0
    sudo ip address flush smartedge-bb
    
    sudo ip address add 10.0.255.254/16 dev smartedge-bb
    sudo ip address add 10.1.255.254/16 dev smartedge-bb

    sudo ip link set dev smartedge-bb address $final_mac
    sudo ip link set dev smartedge-bb up

    # Run the python script for the coordinator
    sudo .venv/bin/python ./coordinator/coordinator.py --log-level $LOGLEVEL --num-id $octet4
    ;;
# Access Point: 
    ap)
    echo "Role is set as Access Point"
    /bin/bash ./shell_scripts/run_bmv2_docker.sh
    # Genereate the MAC and IP address for the AP
    BACKBONE_IP=$(nextip $BACKBONE_SUBNET $octet4)
    IP_HEX=$(printf '%.2X%.2X%.2X%.2X\n' `echo $BACKBONE_IP | sed -e 's/\./ /g'`)
    oldMAC=00:00:00:00:00:00
    rawOldMac=$(echo $oldMAC | tr -d ':')
    rawNewMac=$(( 0x$rawOldMac + 0x$IP_HEX ))
    final_mac=$(printf "%012x" $rawNewMac | sed 's/../&:/g;s/:$//')

    # sudo ifconfig lo:0 $l0_ip netmask 255.255.255.255 up
    # Start the hotspot
    if  nmcli connection show | grep -q 'SmartEdgeHotspot'; then
        echo -e "Connection SmartEdgeHotspot exists: starting wifi hotspot"
        sudo nmcli con up SmartEdgeHotspot
    else
        echo -e "Connection SmartEdgeHotspot does not exists: \n\tcreating connection and starting wifi hotspot"
        sudo nmcli con add type wifi ifname wlan0 con-name SmartEdgeHotspot autoconnect yes ssid R${octet4}AP
        sudo nmcli con modify SmartEdgeHotspot 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared
        sudo nmcli con modify SmartEdgeHotspot wifi-sec.key-mgmt wpa-psk
        sudo nmcli con modify SmartEdgeHotspot wifi-sec.psk "123456123"
        sudo nmcli con up SmartEdgeHotspot
    fi

    sudo ip link add smartedge-bb type vxlan id $SE_BB_VXLAN_ID group 239.1.1.1 dstport 0 dev eth0
    sudo ip link set dev smartedge-bb address $final_mac
    
    sudo ip address add ${BACKBONE_IP}${BACKBONE_MASK} dev smartedge-bb
    sudo ip link set dev smartedge-bb up

    sudo .venv/bin/python ./ap_manager/ap_manager.py --log-level $LOGLEVEL --num-id $octet4
    ;;
# Smart Node
    sn)
    echo "Role is set as Smart Node"

    sudo ip link add veth0 type veth peer name veth1

    # Genereate the MAC address
    oldMAC=00:00:00:00:00:00
    rawOldMac=$(echo $oldMAC | tr -d ':')
    rawNewMac=$(( 0x$rawOldMac + $NUMID ))
    final_mac=$(printf "%012x" $rawNewMac | sed 's/../&:/g;s/:$//')

    # get current mac and check if its the same as the one to be assigned
    wlan0_OldMac=$(cat /sys/class/net/wlan0/address)


    if [[ "$wlan0_OldMac" != "$final_mac" ]];
    then
        echo "Setting Mac of wlan0"
        sudo ip link set dev wlan0 down
        sudo ip link set dev wlan0 address $final_mac
        sudo ip link set dev wlan0 up
    fi
    # sudo ifconfig lo:0 $l0_ip netmask 255.255.255.255 up
    sudo .venv/bin/python ./node_manager/node_manager.py --log-level $LOGLEVEL
    ;;

    *)
    echo "unkown"
    ;;
esac









