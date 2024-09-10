import psutil 

# Configuring a unique IP on the loopback interface to be used
# as an ID for nodes and Access Points.
# Currently only using last byte of lo:0 as an ID
# This can be configured for example using:
# ifconfig lo:0 127.0.1.1 netmask 255.255.255.255 up
loopback_if = 'lo:0'
loopback_id = psutil.net_if_addrs()[loopback_if][0][1].split('.')

NODE_UUID = f'SN:{int(loopback_id[3]):03}'

default_ifname = 'wlan0'