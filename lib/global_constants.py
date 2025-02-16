from enum import Enum, auto

class String_Constants(str, Enum):
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self.value)
    
    TYPE = auto()
    REQUIST_ID = auto()
    NODE_UUID = auto()
    AP_UUID = auto()
    VXLAN_ID = auto()
    VETH1_VIP = auto()
    VETH1_VMAC = auto()
    COORDINATOR_VIP = auto()
    COORDINATOR_TCP_PORT = auto()
    AP_IP = auto()
    AP_MAC = auto()
    SWARM_ID = auto()
    JOIN_REQUEST_00 = auto()
    JOIN_REQUEST_01 = auto()
    SET_CONFIG = auto()
    LEAVE_REQUEST = auto()
    

STRs = String_Constants
    
node_config_json = {
    STRs.TYPE.name: '',
    STRs.VETH1_VIP.name: '',
    STRs.VETH1_VMAC.name: '',
    STRs.VXLAN_ID.name: '',
    STRs.SWARM_ID.name: '',
    STRs.COORDINATOR_VIP.name: '',
    STRs.COORDINATOR_TCP_PORT.name: '',
    STRs.AP_UUID.name: ''
}