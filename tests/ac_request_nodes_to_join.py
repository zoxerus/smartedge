import socket
import json 


str_TYPE = 'Type'
str_NODE_JOIN_LIST = 'njl'
str_NODE_IDS = 'nids'



message = {'Type': str_NODE_JOIN_LIST,
           str_NODE_IDS: ['SN:00:00:02', 'SN:00:00:03'] 
           }

str_message = json.dumps(message)

host = 'localhost'
port = 9999

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect(('0.0.0.0', 9999))
    s.sendall( bytes( str_message.encode() ) )
    # data = s.recv(1024) #receive up to 1024 bytes.
