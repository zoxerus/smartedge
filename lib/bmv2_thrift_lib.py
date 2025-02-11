import logging
import subprocess
import sys
import re
import os

SWITCH_RESPONSE_ERROR = -1
SWITCH_RESPONSE_INVALID = -2
SWITCH_RESPONSE_LAST_LINE_INDEX = -2
P4_CONTROL_METHOD_THRIFT_CLI = 'THRIFT_CLI'
P4_CONTROL_METHOD_P4RT_GRPC = 'P4RT_GRPC'

# BMV2_DOCKER_CONTAINER_NAME = 'bmv2smartedge'


bmv2_logger = None

DEFAULT_THRIFT_PORT = 9090

def send_cli_command_to_bmv2(cli_command, thrift_ip = '0.0.0.0', thrift_port = DEFAULT_THRIFT_PORT):
    # command = f"simple_switch_CLI --thrift-ip {thrift_ip} --thrift-port {thrift_port} <<< {cli_command}"

    # bmv2_logger.debug(f'Sending command "{cli_command}" to bmv2')
    proc = subprocess.run(f"echo '{cli_command}' | simple_switch_CLI --thrift-ip {thrift_ip} --thrift-port {thrift_port}",
                          shell=True, text=True, stdout=subprocess.PIPE , stderr=subprocess.PIPE)
    # proc = subprocess.run(command.split(), text=True, stdout=subprocess.PIPE , stderr=subprocess.PIPE)
    if (proc.stderr):
        bmv2_logger.error(f'\nBMV2ERROR:\nsending command:\n{cli_command}\nERROR MESSAGE:\n{proc.stderr}')
    response = proc.stdout.strip()

    bmv2_logger.debug(f'Sent command "{cli_command}" to bmv2\nResponse Received: {response}')
    return response
    

def add_entry_to_bmv2(communication_protocol, table_name, action_name, match_keys, action_params, thrift_ip = '0.0.0.0', thrift_port = DEFAULT_THRIFT_PORT,):
    if communication_protocol == P4_CONTROL_METHOD_THRIFT_CLI:
        cli_command = f'table_dump_entry_from_key {table_name} {match_keys}'
        response = send_cli_command_to_bmv2(cli_command, thrift_ip, thrift_port)
        # print(f'Sent command: {cli_command} \nresponse: {response}')
        if 'Invalid table operation (BAD_MATCH_KEY)' in response: # entry doesn't exist
            cli_command = "table_add " + table_name + ' ' + action_name + ' ' + match_keys + ' => ' + action_params
            response = send_cli_command_to_bmv2(cli_command, thrift_ip, thrift_port)
            # bmv2_logger.debug('\nresponse received: ' + response )
            response_as_lines = response.splitlines()
            for line in response_as_lines:
                if ( 'Error' in line ):
                    bmv2_logger.error( f'P4 Command Error:\n {cli_command} \nResponse Obtained: {response} ')
                    return SWITCH_RESPONSE_ERROR
                elif 'Invalid' in line:
                    bmv2_logger.error( f'P4 Command Invalid:\n {cli_command} \nResponse Obtained: {response} ')
                    return SWITCH_RESPONSE_INVALID
                elif line.startswith("Entry has been added with handle"):
                    handle =  re.findall(r'\b\d+\b', line, re.I)[0]
                    bmv2_logger.debug(f"Added entry with handle {handle} detected from line: {line} ")
                    return handle
        else:
            for line in response.splitlines():
                if 'Dumping entry' in line:
                    entry_handle = int( re.findall(r'0x[0-9A-F]+', line, re.I)[0] , 16  )
                    bmv2_logger.debug(f'entr_handle exists: {entry_handle}')
                    cli_command = f'table_modify {table_name} {action_name} {entry_handle} {action_params}'
                    break
            
             


def get_entry_handle(table_name, key, thrift_ip = '0.0.0.0', thrift_port = DEFAULT_THRIFT_PORT):
    command = f'table_dump_entry_from_key {table_name} {key}'
    response = send_cli_command_to_bmv2(command, thrift_ip, thrift_port)
    bmv2_logger.debug(f'Getting entry handle from bmv2 for: {key}\n {response}')
    for line in response.splitlines():
        if 'Dumping entry' in line:
            handle = int( re.findall(r'0x[0-9A-F]+', line, re.I)[0] , 16 )
            bmv2_logger.debug(f'Found handle for key: {key} is: {handle}')
            return handle
    bmv2_logger.debug(f'Could not find entry handle for key: {key}')
    return None


def delete_forwarding_entry_from_bmv2(
    communication_protocol, table_name, key, thrift_ip = '0.0.0.0', thrift_port = DEFAULT_THRIFT_PORT ):
    if communication_protocol == P4_CONTROL_METHOD_THRIFT_CLI:
        handle = get_entry_handle(table_name, key, thrift_ip, thrift_port)
        if handle != None:
            cli_command = f'table_delete {table_name} {handle}'
            send_cli_command_to_bmv2(cli_command, thrift_ip, thrift_port)
            return
        bmv2_logger.debug(f'Entry Handle is None for table: {table_name}, and key: {key}')
