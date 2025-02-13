from enum import Enum, auto

class String_Constants(str, Enum):
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self.value)
    
    TYPE = auto()
    REQUIST_ID = auto()
    THIS_NODE_UUID = auto()
    THIS_NODE_APID = auto()
    VXLAN_ID = auto()
    VETH1_VIP = auto()
    VETH1_VMAC = auto()
    COORDINATOR_VIP = auto()
    COORDINATOR_TCP_PORT = auto()
    xcv = auto()
    AP_IP = auto()
    AP_MAC = auto()
    SWARM_ID = auto()
    JOIN_REQUEST_00 = auto()
    JOIN_REQUEST_01 = auto()
    LEAVE_REQUEST = auto()