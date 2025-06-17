#!/usr/bin/env python3
import argparse
import sys
import socket
import random
import struct
import time

from scapy.all import sendp, get_if_hwaddr

from scapy.all import Ether, IP, UDP



parser = argparse.ArgumentParser(description='send packets using scapy')
parser.add_argument('-sip','--source-ip', help='source IP',
                    type=str, action="store", default='1.1.1.1')
parser.add_argument('-dip','--destination-ip', help='destination IP',
                    type=str, action="store", default='2.2.2.2')
parser.add_argument('-sport','--source-port', help='source sport',
                    type=int, action="store", default='35000')
parser.add_argument('-dport','--destination-port', help='destination port',
                    type=int, action="store", default='45000')
parser.add_argument('-pl','--payload', help='packet payload',
                    type=str, action="store", default='Hi')
parser.add_argument('-nmsg','--num-packets', help='number of packets to send',
                    type=int, action="store", default=1)
parser.add_argument('-intv','--interval', help='interval between packet sends',
                    type=float, action="store", default=0)
parser.add_argument('-if','--interface', help='interface to send on',
                    type=str, action="store", default='eth0')

args = parser.parse_args()

def main():
    print ("sending on interface %s to %s" % (args.interface, args.destination_ip)   )
    pkt =  Ether(src=get_if_hwaddr(args.interface), dst='00:00:00:00:00:02')
    pkt = pkt /IP(src= args.source_ip, dst=args.destination_ip, tos =0) / UDP(dport=args.destination_port ,
                                                         sport= args.source_port ) / args.payload
    #pkt.show2()
    for i in range(args.num_packets):
        sendp(pkt, iface=args.interface, verbose=False)
        time.sleep(args.interval)
        print("\rSent {0} Packets".format(i+1),end = "")
    print("")


if __name__ == '__main__':
    main()
