# Set the working directory to where the script path is stored
# This makes the script executable from anywhere
SCRIPT_PATH="${BASH_SOURCE[0]:-$0}";
cd "$( dirname -- "$SCRIPT_PATH"; )";

##

# IP Configurations
BACKBONE_SUBNET=10.1.0.0
BACKBONE_MASK=/24

SWARM_SUBNET=10.0.1.0
SWARM_SUBNET_MASK=/24

# This function prints the next IP
nextip(){
    IP=$1
    IP_HEX=$(printf '%.2X%.2X%.2X%.2X\n' `echo $IP | sed -e 's/\./ /g'`)

    NEXT_IP_HEX=$(printf %.8X `echo $(( 0x$IP_HEX + $2 ))`)
    NEXT_IP=$(printf '%d.%d.%d.%d\n' `echo $NEXT_IP_HEX | sed -r 's/(..)/0x\1 /g'`)
    echo "$NEXT_IP"
}


# Check if number of parameters passed to the script is equal to 2
if [ "$#" != '2' ] || [[ "${BASH_SOURCE[0]}" == "${0}" ]] ; then
    echo -e "\e[32mError:\e[0m"
    echo -e "Script must be sourced with parameters: \nparam1 Script Type: [ap, co, nd] \nparam2 a numeric id\n"
    echo -e "for example:\nsource ./run ap 1\n"
    return
fi

# read the script Role from first parameters and the numeric ID of the node from the second parameter
export ROLE=$1
export NUMID=$2


# generate the IP addresses for the node

BACKBONE_IP=$(nextip $BACKBONE_SUBNET $NUMID)
SWARM_IP=$(nextip $SWARM_SUBNET $NUMID)
l0_ip=$(nextip 127.0.0.1 $NUMID)



[[ "$VIRTUAL_ENV" == "" ]]; INVENV=$?

if [ $INVENV -eq "0" ]; then
    echo -e "Virtual Environment not sourced"
    if [ -d ".venv"  ]; then
        echo "sourcing from .venv"

        . ./.venv/bin/activate
        
    else 
        echo -e "Creating a new Virtual Environment"
        python -m venv .venv
        . ./.venv/bin/activate
        echo -e "Installing Python Modules"
        pip install aenum cassandra-driver psutil
    fi
    source ~/.bashrc
    alias python='$VIRTUAL_ENV/bin/python'
    alias sudo='sudo '
else
    alias python='$VIRTUAL_ENV/bin/python'
    alias sudo='sudo '
fi 


case $ROLE in
# Coordinator:
    co)
    echo "Role is set to Coordinator"
    IP_HEX=$(printf '%.2X%.2X%.2X%.2X\n' `echo $SWARM_IP | sed -e 's/\./ /g'`)
    echo -e "IP $IP in HEX: $IP_HEX"
    # Genereate the MAC address
    oldMAC=00:00:0a:00:01:01
    # rawOldMac=$(echo $oldMAC | tr -d ':')
    # rawNewMac=$(( 0x$rawOldMac + 0x$IP_HEX ))
    # # rawNewMac=$(( 0x$rawOldMac + $NUMID ))
    # final_mac=$(printf "%012x" $rawNewMac | sed 's/../&:/g;s/:$//')

    sudo ip link add smartedge-bb type vxlan id 1000 group 239.1.1.1 dstport 0 dev eth0
    sudo ip address add ${BACKBONE_IP}${BACKBONE_MASK} dev smartedge-bb
    sudo ip link set dev smartedge-bb address $oldMAC

    sudo ip address add 10.0.1.1/24 dev smartedge-bb
    sudo ip link set dev smartedge-bb up

    # sudo ip link set dev eth0.1 address $final_mac
    # sudo ip address add ${SWARM_IP}${SWARM_SUBNET_MASK} dev eth0.1
    sudo python ./coordinator/coordinator.py
    ;;
# Access Point: 
    ap)
    echo "Role is set as Access Point"

    IP_HEX=$(printf '%.2X%.2X%.2X%.2X\n' `echo $SWARM_IP | sed -e 's/\./ /g'`)
    echo -e "IP $IP in HEX: $IP_HEX"
    # Genereate the MAC address
    oldMAC=00:00:00:00:00:00
    rawOldMac=$(echo $oldMAC | tr -d ':')
    rawNewMac=$(( 0x$rawOldMac + 0x$IP_HEX ))
    # rawNewMac=$(( 0x$rawOldMac + $NUMID ))
    final_mac=$(printf "%012x" $rawNewMac | sed 's/../&:/g;s/:$//')

    sudo ifconfig lo:0 $l0_ip netmask 255.255.255.255 up
    if  nmcli connection show | grep -q 'SmartEdgeHotspot'; then
        echo -e "Connection SmartEdgeHotspot exists: starting wifi hotspot"
        sudo nmcli con up SmartEdgeHotspot
    else
        echo -e "Connection SmartEdgeHotspot does not exists: \n\tcreating connection and starting wifi hotspot"
        sudo nmcli con add type wifi ifname wlan0 con-name SmartEdgeHotspot autoconnect yes ssid R${NUMID}AP
        sudo nmcli con modify SmartEdgeHotspot 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared
        sudo nmcli con modify SmartEdgeHotspot wifi-sec.key-mgmt wpa-psk
        sudo nmcli con modify SmartEdgeHotspot wifi-sec.psk "123456123"
        sudo nmcli con up SmartEdgeHotspot
    fi
    sudo ip link add smartedge-bb type vxlan id 1000 group 239.1.1.1 dstport 0 dev eth0
    sudo ip link set dev smartedge-bb address $final_mac
    sudo ip address add ${BACKBONE_IP}${BACKBONE_MASK} dev smartedge-bb
    sudo ip link set dev smartedge-bb up
    # sudo ip link set dev eth0.1 address $final_mac

    # oldMAC=16:00:00:00:00:00
    # rawOldMac=$(echo $oldMAC | tr -d ':')
    # rawNewMac=$(( 0x$rawOldMac + $NUMID ))
    # final_mac=$(printf "%012x" $rawNewMac | sed 's/../&:/g;s/:$//')
    # sudo ip link set dev wlan0 address $final_mac
    sudo python ./ap_manager/ap_manager.py
    ;;
# Smart Node
    sn)
    echo "Role is set as Smart Node"
    # Genereate the MAC address
    oldMAC=00:00:00:00:00:00
    rawOldMac=$(echo $oldMAC | tr -d ':')
    rawNewMac=$(( 0x$rawOldMac + $NUMID ))
    final_mac=$(printf "%012x" $rawNewMac | sed 's/../&:/g;s/:$//')

    # get current mac and check if its the same as the one to be assigned
    wlan0_OldMac=$(cat /sys/class/net/wlan0/address)
    if [ "$wlan0_OldMac" != "$final_mac" ] 
    then
        echo "Setting Mac of Wlan0"
        # sudo ip link set dev wlan0 down
        sudo ip link set dev wlan0 address $final_mac
        # sudo ip link set dev wlan0 up
    fi
    sudo ifconfig lo:0 $l0_ip netmask 255.255.255.255 up
    sudo python ./node_manager/node_manager.py
    ;;

    *)
    echo "unkown"
    ;;
esac









