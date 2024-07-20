#!/usr/bin/env python3
import sys, time
import argparse
import os

from scapy.all import sniff
from scapy.all import Packet
from scapy.all import UDP
from scapy.all import XByteField, ShortField, BitField
from scapy.all import bind_layers

parser = argparse.ArgumentParser(description='receive packets')
parser.add_argument('-if','--interface', help='interface to receive on',
                    type=str, action="store", default='eth0')
parser.add_argument('-p','--port', help='port to listen to',
                    type=int, action="store", default='45000')
args = parser.parse_args()


class INT_MD(Packet):
    name = 'INT_MD'
    fields_desc = [
        ShortField(name='node_id', default=0),
        ShortField(name='flow_id', default=0),
        BitField(name='delay', default=0, size=64)
    ]

def handle_pkt(pkt):
    if UDP in pkt and pkt[UDP].dport == args.port:
        data = pkt[INT_MD]
        print(data.delay)

    sys.stdout.flush()


def main():

    bind_layers(UDP, INT_MD, dport=45000)

    iface = args.interface
    print(("sniffing on %s" % iface))
    sys.stdout.flush()
    sniff(iface = iface,
          prn = lambda x: handle_pkt(x))

if __name__ == '__main__':
    main()
    print('\r Received: {} Packets'.format(x) )
