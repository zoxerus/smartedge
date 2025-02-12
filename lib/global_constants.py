from enum import Enum, auto

class String_Constants(str, Enum):
    def __repr__(self):
        return self.name   
    VXLAN_ID = auto()
    VETH1_VIP = auto()
    VETH1_VMAC = auto()
    COORDINATOR_VIP = auto()
    COORDINATOR_TCP_PORT = auto()
    AP_ID = auto()
    AP_IP = auto()
    AP_MAC = auto()
    SWARM_ID = auto()
    JOIN_REQUEST_00 = auto()
    JOIN_REQUEST_01 = auto()

class Control_Message_Keys(str, Enum):
    def __repr__(self):
        return self.name   
    TYPE = auto()
    REQUIST_ID = auto()
    THIS_NODE_UUID = auto()
    THIS_NODE_APID = auto()
    
    
