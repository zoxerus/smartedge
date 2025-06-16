#include <core.p4>
#include <v1model.p4>

// Constants for DDS/RTPS protocol
const bit<16> ETHERTYPE_IPV4 = 0x0800;
const bit<8>  IPPROTO_UDP = 0x11;
const bit<32> RTPS_PROTOCOL_ID = 0x52545053; // "RTPS"
const bit<16> TYPE_ARP  = 0x0806;

// ARP RELATED CONST VARS
const bit<16> ARP_HTYPE = 0x0001; //Ethernet Hardware type is 1
const bit<16> ARP_PTYPE = TYPE_IPV4; //Protocol used for ARP is IPV4
const bit<8>  ARP_HLEN  = 6; //Ethernet address size is 6 bytes
const bit<8>  ARP_PLEN  = 4; //IP address size is 4 bytes
const bit<16> ARP_REQ = 1; //Operation 1 is request
const bit<16> ARP_REPLY = 2; //Operation 2 is reply

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
  macAddr_t src_mac;
  ip4Addr_t src_ip;
  macAddr_t dst_mac;
  ip4Addr_t dst_ip;
  }


header udp_t {
    bit<16> src_port;
    bit<16> dst_port;
    bit<16> length;
    bit<16> checksum;
}

// RTPS Message Header based on DDSI-RTPS specification
header rtps_header_t {
    bit<32> protocol;        // "RTPS" identifier
    bit<8>  major_version;   // Protocol major version
    bit<8>  minor_version;   // Protocol minor version
    bit<16> vendor_id;       // Vendor identifier
    bit<96> guid_prefix;     // 12-byte GUID prefix
}

// RTPS Submessage Header
header rtps_submessage_header_t {
    bit<8>  submessage_id;
    bit<8>  flags;
    bit<16> submessage_length;
}

// Common RTPS submessage types based on specification
header rtps_data_submessage_t {
    bit<16> extra_flags;
    bit<16> octets_to_inline_qos;
    bit<32> reader_id;
    bit<32> writer_id;
    bit<64> sequence_number;
}

header rtps_heartbeat_submessage_t {
    bit<32> reader_id;
    bit<32> writer_id;
    bit<64> first_sn;
    bit<64> last_sn;
    bit<32> count;
}

// ROS message metadata
header ros_metadata_t {
    bit<8>  message_type;    // Custom field to identify ROS message types
    bit<8>  qos_class;       // Quality of Service classification
    bit<16> topic_id;        // Topic identifier
    bit<32> timestamp;       // Message timestamp
}

// Header stack for multiple RTPS submessages
struct headers_t {
    ethernet_t              ethernet;
    ipv4_t                  ipv4;
    arp_t                   arp;
    udp_t                   udp;
    rtps_header_t           rtps_header;
    rtps_submessage_header_t rtps_submsg_hdr;
    rtps_data_submessage_t  rtps_data;
    rtps_heartbeat_submessage_t rtps_heartbeat;
    ros_metadata_t          ros_meta;
}

struct metadata_t {
    bit<9>  ingress_port;
    bit<9>  egress_port;
    bit<16> dds_domain_id;
    bit<32> participant_id;
    bit<8>  submessage_count;
    bit<8>  ros_message_priority;
    bit<1>  is_discovery_traffic;
    bit<1>  is_user_traffic;
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
            7400 &&& 0xE000: parse_rtps;  // Match ports 7400-9999
            default: accept;
        }
    }

    state parse_rtps {
        packet.extract(hdr.rtps_header);
        // Verify RTPS protocol identifier
        transition select(hdr.rtps_header.protocol) {
            RTPS_PROTOCOL_ID: parse_rtps_submessage;
            default: accept;
        }
    }

    state parse_rtps_submessage {
        packet.extract(hdr.rtps_submsg_hdr);
        transition select(hdr.rtps_submsg_hdr.submessage_id) {
            0x15: parse_rtps_data;      // DATA submessage
            0x07: parse_rtps_heartbeat; // HEARTBEAT submessage
            0x09: parse_ros_metadata;   // INFO_TS or custom ROS metadata
            default: accept;
        }
    }

    state parse_rtps_data {
        packet.extract(hdr.rtps_data);
        meta.is_user_traffic = 1;
        transition parse_ros_metadata;
    }

    state parse_rtps_heartbeat {
        packet.extract(hdr.rtps_heartbeat);
        meta.is_discovery_traffic = 1;
        transition accept;
    }

    state parse_ros_metadata {
        packet.extract(hdr.ros_meta);
        transition accept;
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

    counter (1, CounterType.packets) mcast_counter;
    counter(32w1, CounterType.packets) unicast_counter;


    
    action ac_ipv4_forward_mac(egressSpec_t port, macAddr_t dMac) {
        standard_metadata.egress_spec = port;
        // hdr.ethernet.srcMac = hdr.ethernet.dstMac;
        hdr.ethernet.dstMac = dMac;
        // hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    action ac_ipv4_forward_mac_from_dst_ip(egressSpec_t port) {
        standard_metadata.egress_spec = port;
        // hdr.ethernet.srcMac = hdr.ethernet.dstMac;
        hdr.ethernet.dstMac = (bit<48>) hdr.ipv4.dstIP;
        // hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    /* Experimental; forward WTHOUT setting MAC address */
    action ac_ipv4_forward(egressSpec_t port) {
        standard_metadata.egress_spec = port;
        // hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    table tb_ipv4_lpm {
        key = {            
            hdr.ipv4.dstIP: lpm;
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
            hdr.ethernet.dstMac             :   ternary;
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







    // Actions for ROS/DDS traffic handling
    action set_ros_priority(bit<8> priority) {
        meta.ros_message_priority = priority;
    }

    action forward_to_subscriber(bit<9> egress_port) {
        standard_metadata.egress_spec = egress_port;
        meta.egress_port = egress_port;
    }

    action multicast_to_domain(bit<16> mcast_group) {
        standard_metadata.mcast_grp = mcast_group;
    }

    action extract_domain_info() {
        // Extract domain ID from UDP port using DDS port mapping formula
        // Port = 7400 + (250 * Domain) + offset
        meta.dds_domain_id = (hdr.udp.dst_port - 7400) / 250;
    }

    action drop_packet() {
        mark_to_drop(standard_metadata);
    }

    // Table for ROS topic-based forwarding
    table ros_topic_forwarding {
        key = {
            hdr.ros_meta.topic_id: exact;
            meta.dds_domain_id: exact;
        }
        actions = {
            forward_to_subscriber;
            multicast_to_domain;
            drop_packet;
        }
        default_action = drop_packet();
        size = 1024;
    }

    // Table for QoS-based priority handling
    table ros_qos_policy {
        key = {
            hdr.ros_meta.qos_class: exact;
            hdr.ros_meta.message_type: exact;
        }
        actions = {
            set_ros_priority;
        }
        default_action = set_ros_priority(0);
        size = 256;
    }

    // Table for DDS discovery traffic handling
    table dds_discovery_handling {
        key = {
            hdr.rtps_submsg_hdr.submessage_id: exact;
            meta.dds_domain_id: exact;
        }
        actions = {
            multicast_to_domain;
            forward_to_subscriber;
        }
        default_action = multicast_to_domain(1);
        size = 128;
    }

    // Main processing logic
    apply {

        if (hdr.ethernet.ether_type == TYPE_ARP && hdr.arp.op_code == ARP_REQ ) {
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
            hdr.ethernet.src_addr = (bit<48>) hdr.arp.dst_ip;

            //send it back to the same port
            standard_metadata.egress_spec = standard_metadata.ingress_port;
            exit;
        } 



        if (hdr.rtps_header.isValid()) {
            extract_domain_info();
            
            // Handle discovery traffic (HEARTBEAT, ACKNACK, etc.)
            if (meta.is_discovery_traffic == 1) {
                dds_discovery_handling.apply();
            }
            // Handle user data traffic
            else if (meta.is_user_traffic == 1 && hdr.ros_meta.isValid()) {
                ros_qos_policy.apply();
                ros_topic_forwarding.apply();
            }
        }
    }
}

// Egress processing
control MyEgress(inout headers_t hdr,
                 inout metadata_t meta,
                 inout standard_metadata_t standard_metadata) {

    action update_rtps_timestamp() {
        // Update RTPS timestamp for outgoing messages
        hdr.ros_meta.timestamp = (bit<32>)standard_metadata.egress_global_timestamp;
    }

    apply {
        if (hdr.ros_meta.isValid()) {
            update_rtps_timestamp();
        }


        if (standard_metadata.ingress_port == standard_metadata.egress_port && 
                hdr.ethernet.ether_type != TYPE_ARP) {

                    mark_to_drop(standard_metadata);
        }

    }
}

// Checksum computation
control MyComputeChecksum(inout headers_t hdr, inout metadata_t meta) {
    apply {
        update_checksum(
            hdr.ipv4.hdr_checksum,
            {
                hdr.ipv4.version,
                hdr.ipv4.ihl,
                hdr.ipv4.diffserv,
                hdr.ipv4.total_len,
                hdr.ipv4.identification,
                hdr.ipv4.flags,
                hdr.ipv4.frag_offset,
                hdr.ipv4.ttl,
                hdr.ipv4.protocol,
                hdr.ipv4.src_addr,
                hdr.ipv4.dst_addr
            },
            HashAlgorithm.csum16
        );
    }
}

// Deparser
control MyDeparser(packet_out packet, in headers_t hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.udp);
        packet.emit(hdr.rtps_header);
        packet.emit(hdr.rtps_submsg_hdr);
        packet.emit(hdr.rtps_data);
        packet.emit(hdr.rtps_heartbeat);
        packet.emit(hdr.ros_meta);
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
