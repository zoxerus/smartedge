import psutil 
loopback_if = 'lo:0'
loopback_id = psutil.net_if_addrs()[loopback_if][0][1].split('.')

NODE_UUID = f'SN:{int(loopback_id[3]):03}'

default_ifname = 'wlan0'