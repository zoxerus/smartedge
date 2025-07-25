#include <core.p4>
#include <v1model.p4>

// Constants for DDS/RTPS protocol
const bit<16> ETHERTYPE_IPV4 = 0x0800;
const bit<8>  IPPROTO_UDP = 0x11;
const bit<32> RTPS_PROTOCOL_ID = 0x52545053; // "RTPS"
const bit<16> TYPE_ARP  = 0x0806;

const bit<16> TYPE_IPV4 = 0x0800;

// ARP RELATED CONST VARS
const bit<16> ARP_HTYPE = 0x0001; //Ethernet Hardware type is 1
const bit<16> ARP_PTYPE = TYPE_IPV4; //Protocol used for ARP is IPV4
const bit<8>  ARP_HLEN  = 6; //Ethernet address size is 6 bytes
const bit<8>  ARP_PLEN  = 4; //IP address size is 4 bytes
const bit<16> ARP_REQ = 1; //Operation 1 is request
const bit<16> ARP_REPLY = 2; //Operation 2 is reply


// ROS2 Discovery constants
const bit<32> ROS2_DISCOVERY_MULTICAST = 0xEFFF0001; // 239.255.0.1
const bit<16> ROS2_DISCOVERY_PORT = 7400;

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

// Header definitions
header ethernet_t {
    bit<48> dst_addr;
    bit<48> src_addr;
    bit<16> ether_type;
}

header ipv4_t {
    bit<4>  version;
    bit<4>  ihl;
    bit<8>  diffserv;
    bit<16> total_len;
    bit<16> identification;
    bit<3>  flags;
    bit<13> frag_offset;
    bit<8>  ttl;
    bit<8>  protocol;
    bit<16> hdr_checksum;
    bit<32> src_addr;
    bit<32> dst_addr;
}

header arp_t {
  bit<16>   h_type;
  bit<16>   p_type;
  bit<8>    h_len;
  bit<8>    p_len;
  bit<16>   op_code;
  bit<48> src_mac;
  bit<32> src_ip;
  bit<48> dst_mac;
  bit<32> dst_ip;
  }


header udp_t {
    bit<16> src_port;
    bit<16> dst_port;
    bit<16> length;
    bit<16> checksum;
}

struct metadata_t {
    bit<16> mcast_grp;
    bit<1>  is_multicast;
    bit<1>  is_ros2_discovery;
    bit<9>  inter_switch_port;
}



// Header stack for multiple RTPS submessages
struct headers_t {
    ethernet_t              ethernet;
    arp_t                   arp;
    ipv4_t                  ipv4;
    udp_t                   udp;
    rtps_t           rtps;
}


// Parser implementation
parser MyParser(packet_in packet,
                out headers_t hdr,
                inout metadata_t meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.ether_type) {
            ETHERTYPE_IPV4: parse_ipv4;
            TYPE_ARP:       parse_arp;
            default: accept;
        }
    }

    state parse_arp {
        packet.extract(hdr.arp);
        transition accept;
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol) {
            IPPROTO_UDP: parse_udp;
            default: accept;
        }
    }

    state parse_udp {
        packet.extract(hdr.udp);
        // Check if this is a DDS/RTPS port range (7400-9999 typical range)
        transition select(hdr.udp.dst_port) {
            7400: parse_rtps_discovery;
            7410: parse_rtps_data;  // Example data port
            default: accept;
        }
    }

}

// Checksum verification (simplified for demo)
control MyVerifyChecksum(inout headers_t hdr, inout metadata_t meta) {
    apply { }
}

// Main ingress processing
control MyIngress(inout headers_t hdr,
                  inout metadata_t meta,
                  inout standard_metadata_t standard_metadata) {

    counter(1, CounterType.packets) mcast_counter;
    counter(1, CounterType.packets) unicast_counter;
    
    action drop() {
        mark_to_drop(standard_metadata);
        exit;
    }

    action ac_ipv4_forward_mac(egressSpec_t port, macAddr_t dMac) {
        unicast_counter.count(0);
        standard_metadata.egress_spec = port;
        // hdr.ethernet.srcMac = hdr.ethernet.dstMac;
        hdr.ethernet.dst_addr = dMac;
        // hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    action ac_ipv4_forward_mac_from_dst_ip(egressSpec_t port) {
        unicast_counter.count(0);
        standard_metadata.egress_spec = port;
        // hdr.ethernet.srcMac = hdr.ethernet.dstMac;
        hdr.ethernet.dst_addr = (bit<48>) hdr.ipv4.dst_addr;
        // hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    /* Experimental; forward WTHOUT setting MAC address */
    action ac_ipv4_forward(egressSpec_t port) {
        unicast_counter.count(0);
        standard_metadata.egress_spec = port;
        // hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    table tb_ipv4_lpm {
        key = {            
            hdr.ipv4.dst_addr: lpm;
            // hdr.udp.dst_port: ternary;
        }
        actions = {
            ac_ipv4_forward;
            ac_ipv4_forward_mac;
            ac_ipv4_forward_mac_from_dst_ip;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = NoAction();
    }

    //------------------------------------------------------//
    //---------------  L 2  H A N D L I N G  ---------------//

    action ac_l2_forward(egressSpec_t eif ){
        standard_metadata.egress_spec = eif;
    }

    action ac_l2_broadcast(bit<16> mcast_grp ){
        mcast_counter.count(0);
        standard_metadata.mcast_grp = mcast_grp;
    }

    table tb_l2_forward {
        key = {
            hdr.ethernet.dst_addr             :   ternary;
        } 
        actions = {
            ac_l2_forward;
            ac_l2_broadcast;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = NoAction();
        counters = mcast_counter;
    }






    action set_mcast_group(bit<16> group_id) {
        standard_metadata.mcast_grp = group_id;
        // hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }
    
    action unicast_forward(bit<9> port) {
        standard_metadata.egress_spec = port;
        // hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }
    
    table ros2_discovery {
        key = {
            hdr.udp.dst_port: exact;
        }
        actions = {
            unicast_forward;
            set_mcast_group;
        }
        size = 1024;
        default_action = unicast_forward(1);  // Default to control plane
    }
    
    table ros2_multicast_routing {
        key = {
            hdr.ipv4.dst_addr: lpm;
        }
        actions = {
            set_mcast_group;
            drop;
        }
        size = 4096;
        default_action = drop;
    }
    

action ac_default_response_to_arp() {
        //update operation code from request to reply
        hdr.arp.op_code = ARP_REPLY;
        
        //reply's dst_mac is the request's src mac
        hdr.arp.dst_mac = hdr.arp.src_mac;
        
        //reply's dst_ip is the request's src ip
        hdr.arp.src_mac = (bit<48>) hdr.arp.dst_ip;

        //reply's src ip is the request's dst ip
        hdr.arp.src_ip = hdr.arp.dst_ip;

        //update ethernet header
        hdr.ethernet.dst_addr = hdr.ethernet.src_addr;
        hdr.ethernet.src_addr = hdr.arp.src_mac;

        //send it back to the same port
        standard_metadata.egress_spec = standard_metadata.ingress_port;
    }

    action ac_respond_to_arp(bit<48> requested_mac) {
        //update operation code from request to reply
        hdr.arp.op_code = ARP_REPLY;
        
        //reply's dst_mac is the request's src mac
        hdr.arp.dst_mac = hdr.arp.src_mac;
        
        //reply's dst_ip is the request's src ip
        hdr.arp.src_mac = requested_mac;

        //reply's src ip is the request's dst ip
        hdr.arp.src_ip = hdr.arp.dst_ip;

        //update ethernet header
        hdr.ethernet.dst_addr = hdr.ethernet.src_addr;
        hdr.ethernet.src_addr = requested_mac;

        //send it back to the same port
        standard_metadata.egress_spec = standard_metadata.ingress_port;
    }

    direct_counter(CounterType.packets) arp_req_counter;

    table tb_arp {
        key = {
            hdr.arp.dst_ip: exact;
        }
        actions = {
            ac_respond_to_arp;
            ac_default_response_to_arp;
        }
        size = 1024;
        default_action = ac_default_response_to_arp();
        counters = arp_req_counter;
    }

    // Main processing logic
    apply {

        if (hdr.ethernet.ether_type == TYPE_ARP && hdr.arp.op_code == ARP_REQ ) {
            tb_arp.apply();
            // exit;
        } 

        if (tb_l2_forward.apply().hit){
            // exit;
        }

        if (hdr.ipv4.isValid()) {
            if (meta.is_discovery == 1) {
                ros2_discovery.apply();
            }
            else if (hdr.ipv4.dst_addr[31:28] == 0xE0) {  // Multicast range
                ros2_multicast_routing.apply();
            } else {
                tb_ipv4_lpm.apply();
                // inter_switch_routing.apply();
            }
                // else tb_ipv4_lpm.apply();
        }
    }
}

// Egress processing
control MyEgress(inout headers_t hdr,
                 inout metadata_t meta,
                 inout standard_metadata_t standard_metadata) {

    apply {

        if (standard_metadata.ingress_port == standard_metadata.egress_port && 
                hdr.ethernet.ether_type != TYPE_ARP) {

                    mark_to_drop(standard_metadata);
        }

    }
}

control MyComputeChecksum(inout headers_t hdr, inout metadata_t meta) {
     apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.total_len,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.frag_offset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.src_addr,
              hdr.ipv4.dst_addr },
            hdr.ipv4.hdr_checksum,
            HashAlgorithm.csum16);
    }
}
// Deparser
control MyDeparser(packet_out packet, in headers_t hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.arp);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.udp);
        packet.emit(hdr.rtps);
    }
}

// V1Switch instantiation for BMv2
V1Switch(
    MyParser(),
    MyVerifyChecksum(),
    MyIngress(),
    MyEgress(),
    MyComputeChecksum(),
    MyDeparser()
) main;
