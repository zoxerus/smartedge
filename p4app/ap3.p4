#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x800;
const bit<8>  TYPE_UDP  = 17;

// ROS2 DDS Discovery multicast addresses
const bit<32> ROS2_DISCOVERY_MULTICAST = 0xEFFF0001; // 239.255.0.1
const bit<16> ROS2_DISCOVERY_PORT = 7400;

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}

header udp_t {
    bit<16> srcPort;
    bit<16> dstPort;
    bit<16> length_;
    bit<16> checksum;
}

struct metadata {
    bit<16> mcast_grp;
    bit<1>  is_multicast;
    bit<1>  is_ros2_discovery;
    bit<9>  inter_switch_port;
}

struct headers {
    ethernet_t ethernet;
    ipv4_t     ipv4;
    udp_t      udp;
}

/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol) {
            TYPE_UDP: parse_udp;
            default: accept;
        }
    }

    state parse_udp {
        packet.extract(hdr.udp);
        transition accept;
    }
}

/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply { }
}

/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    action drop() {
        mark_to_drop(standard_metadata);
    }

    action ipv4_forward(macAddr_t dstAddr, egressSpec_t port) {
        standard_metadata.egress_spec = port;
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    action set_multicast_group(bit<16> mcast_grp) {
        standard_metadata.mcast_grp = mcast_grp;
        meta.mcast_grp = mcast_grp;
        meta.is_multicast = 1;
    }

    action set_inter_switch_port(bit<9> port) {
        meta.inter_switch_port = port;
    }

    // Table for unicast forwarding
    table ipv4_lpm {
        key = {
            hdr.ipv4.dstAddr: lpm;
        }
        actions = {
            ipv4_forward;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = drop();
    }

    // Table for multicast group assignment
    table multicast_exact {
        key = {
            hdr.ipv4.dstAddr: exact;
        }
        actions = {
            set_multicast_group;
            drop;
            NoAction;
        }
        size = 64;
        default_action = drop();
    }

    // Table to identify inter-switch port
    table switch_config {
        key = {
            standard_metadata.ingress_port: exact;
        }
        actions = {
            set_inter_switch_port;
            NoAction;
        }
        size = 16;
        default_action = NoAction();
    }

    apply {
        // Initialize metadata
        meta.is_multicast = 0;
        meta.is_ros2_discovery = 0;
        meta.inter_switch_port = 0;

        if (hdr.ipv4.isValid()) {
            // Check if this is ROS2 discovery traffic
            if (hdr.ipv4.dstAddr == ROS2_DISCOVERY_MULTICAST && 
                hdr.udp.isValid() && hdr.udp.dstPort == ROS2_DISCOVERY_PORT) {
                meta.is_ros2_discovery = 1;
            }

            // Apply switch configuration to identify inter-switch links
            switch_config.apply();

            // Check if destination is multicast
            if ((hdr.ipv4.dstAddr & 0xF0000000) == 0xE0000000) {
                // Multicast address range (224.0.0.0/4)
                multicast_exact.apply();
            } else {
                // Unicast forwarding
                ipv4_lpm.apply();
            }
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {

    action update_mac_addresses(macAddr_t srcAddr, macAddr_t dstAddr) {
        hdr.ethernet.srcAddr = srcAddr;
        hdr.ethernet.dstAddr = dstAddr;
    }

    table egress_mac_rewrite {
        key = {
            standard_metadata.egress_port: exact;
        }
        actions = {
            update_mac_addresses;
            NoAction;
        }
        size = 64;
        default_action = NoAction();
    }

    apply {
        if (hdr.ipv4.isValid()) {
            // Update MAC addresses based on egress port
            egress_mac_rewrite.apply();
        }
    }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.udp);
    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
