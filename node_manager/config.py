import psutil 
loopback_if = 'lo1'
loopback_id = psutil.net_if_addrs()[loopback_if][0][1]

NODE_UUID = f'SN:{loopback_id[2]:03}'

default_ifname = 'wlan0'