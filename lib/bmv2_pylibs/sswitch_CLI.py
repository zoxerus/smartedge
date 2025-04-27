#!/usr/bin/env python3
# Copyright 2013-present Barefoot Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

#
# Antonin Bas (antonin@barefootnetworks.com)
#
#

import runtime_CLI
from runtime_CLI import UIn_Error

from functools import wraps
import os
import sys
import  io
import time
import timeit
import subprocess

from sswitch_runtime import SimpleSwitch
from sswitch_runtime.ttypes import *
from contextlib import redirect_stdout 


def handle_bad_input(f):
    @wraps(f)
    @runtime_CLI.handle_bad_input
    def handle(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except InvalidMirroringOperation as e:
            error = MirroringOperationErrorCode._VALUES_TO_NAMES[e.code]
            print("Invalid mirroring operation (%s)" % error)
    return handle

class SimpleSwitchAPI(runtime_CLI.RuntimeAPI):
    @staticmethod
    def get_thrift_services():
        return [("simple_switch", SimpleSwitch.Client)]

    def __init__(self, pre_type, standard_client, mc_client, sswitch_client):
        runtime_CLI.RuntimeAPI.__init__(self, pre_type,
                                        standard_client, mc_client)
        self.sswitch_client = sswitch_client

    @handle_bad_input
    def do_set_queue_depth(self, line):
        "Set depth of one / all egress queue(s): set_queue_depth <nb_pkts> [<egress_port> [<priority>]]"
        args = line.split()
        self.at_least_n_args(args, 1)
        depth = self.parse_int(args[0], "nb_pkts")
        if len(args) > 2:
            port = self.parse_int(args[1], "egress_port")
            priority = self.parse_int(args[2], "priority")
            self.sswitch_client.set_egress_priority_queue_depth(port, priority, depth)
        elif len(args) == 2:
            port = self.parse_int(args[1], "egress_port")
            self.sswitch_client.set_egress_queue_depth(port, depth)
        else:
            self.sswitch_client.set_all_egress_queue_depths(depth)

    @handle_bad_input
    def do_set_queue_rate(self, line):
        "Set rate of one / all egress queue(s): set_queue_rate <rate_pps> [<egress_port> [<priority>]]"
        args = line.split()
        self.at_least_n_args(args, 1)
        rate = self.parse_int(args[0], "rate_pps")
        if len(args) > 2:
            port = self.parse_int(args[1], "egress_port")
            priority = self.parse_int(args[2], "priority")
            self.sswitch_client.set_egress_priority_queue_rate(port, priority, rate)
        elif len(args) == 2:
            port = self.parse_int(args[1], "egress_port")
            self.sswitch_client.set_egress_queue_rate(port, rate)
        else:
            self.sswitch_client.set_all_egress_queue_rates(rate)

    @handle_bad_input
    def do_mirroring_add(self, line):
        "Add mirroring session to unicast port: mirroring_add <mirror_id> <egress_port>"
        args = line.split()
        self.exactly_n_args(args, 2)
        mirror_id = self.parse_int(args[0], "mirror_id")
        egress_port = self.parse_int(args[1], "egress_port")
        config = MirroringSessionConfig(port=egress_port)
        self.sswitch_client.mirroring_session_add(mirror_id, config)

    @handle_bad_input
    def do_mirroring_add_mc(self, line):
        "Add mirroring session to multicast group: mirroring_add_mc <mirror_id> <mgrp>"
        args = line.split()
        self.exactly_n_args(args, 2)
        mirror_id = self.parse_int(args[0], "mirror_id")
        mgrp = self.parse_int(args[1], "mgrp")
        config = MirroringSessionConfig(mgid=mgrp)
        self.sswitch_client.mirroring_session_add(mirror_id, config)

    @handle_bad_input
    def do_mirroring_delete(self, line):
        "Delete mirroring session: mirroring_delete <mirror_id>"
        args = line.split()
        self.exactly_n_args(args, 1)
        mirror_id = self.parse_int(args[0], "mirror_id")
        self.sswitch_client.mirroring_session_delete(mirror_id)

    @handle_bad_input
    def do_mirroring_get(self, line):
        "Display mirroring session: mirroring_get <mirror_id>"
        args = line.split()
        self.exactly_n_args(args, 1)
        mirror_id = self.parse_int(args[0], "mirror_id")
        config = self.sswitch_client.mirroring_session_get(mirror_id)
        print(config)

    @handle_bad_input
    def do_get_time_elapsed(self, line):
        "Get time elapsed (in microseconds) since the switch started: get_time_elapsed"
        print(self.sswitch_client.get_time_elapsed_us())

    @handle_bad_input
    def do_get_time_since_epoch(self, line):
        "Get time elapsed (in microseconds) since the switch clock's epoch: get_time_since_epoch"
        print(self.sswitch_client.get_time_since_epoch_us())

def main():
    # args = runtime_CLI.get_parser().parse_args()

    # args.pre = runtime_CLI.PreType.SimplePreLAG

    # services = runtime_CLI.RuntimeAPI.get_thrift_services(args.pre)
    # services.extend(SimpleSwitchAPI.get_thrift_services())


    # THRIFT_IP = '192.168.137.105'


    # standard_client, mc_client, sswitch_client = runtime_CLI.thrift_connect(
    #     THRIFT_IP, 9090, services
    # )

    # runtime_CLI.load_json_config(standard_client, args.json)

    # cli_instance = SimpleSwitchAPI(args.pre, standard_client, mc_client, sswitch_client)
    
    
    # output_capture = io.StringIO()
    # def run_cli_command(command, instance):
    #     command_output = ""
    #     with redirect_stdout(output_capture):
    #         instance.onecmd(command)
    #     command_output = output_capture.getvalue()
    #     output_capture.truncate(0)
    #     return command_output

    # def send_cli_command_to_bmv2(cli_command, thrift_ip = THRIFT_IP, thrift_port = 9090):
    #     command_as_word_array = ['docker','exec','bmv2smartedge','sh', '-c',
    #                             f"echo \'{cli_command}\' | simple_switch_CLI --thrift-ip {thrift_ip} --thrift-port {thrift_port}"  ]

    #     proc = subprocess.run(command_as_word_array, text=True, stdout=subprocess.PIPE , stderr=subprocess.PIPE)
    #     response = proc.stdout.strip()
    #     print(response + '\n')
        
    
    # num_entries = 1
    
    # def add_entries_directly():
    #     for i in range(num_entries):
    #         command = f"table_add MyIngress.tb_ipv4_lpm MyIngress.ac_ipv4_forward 10.10.10.{i}/32 => 1"
    #         run_cli_command(command)
            
    # def add_entries_docker():
    #     for i in range(num_entries):
    #         command = f"table_add MyIngress.tb_ipv4_lpm MyIngress.ac_ipv4_forward 10.10.10.{i}/32 => 1"
    #         send_cli_command_to_bmv2(command)
            
    # print('running add_entries_local')
    # run_cli_command('table_clear MyIngress.tb_ipv4_lpm')
    # time1 = timeit.timeit(stmt=add_entries_directly, number=1)
    # run_cli_command('table_clear MyIngress.tb_ipv4_lpm')
    # print('\n------------------------------------------------------\n')
    # print('running add_entires_docker:')
    # time2 = timeit.timeit(stmt=add_entries_docker, number=1)
    
    
    # print(f"Execution Time direct': {time1:.6f} seconds")
    # print(f"Execution Time docker': {time2:.6f} seconds")
    
    

# if __name__ == '__main__':
#     main()
