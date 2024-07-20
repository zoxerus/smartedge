import logging
import subprocess
import sys
import re


SWITCH_RESPONSE_ERROR = -1
SWITCH_RESPONSE_INVALID = -2
SWITCH_RESPONSE_LAST_LINE_INDEX = -2
P4_CONTROL_METHOD_THRIFT_CLI = 'THRIFT_CLI'
P4_CONTROL_METHOD_P4RT_GRPC = 'P4RT_GRPC'
BMV2_LOG_FILE_NAME = './logs/bmv2_log.log'

BMV2_DOCKER_CONTAINER_NAME = 'bmv2ap'

DEFAULT_THRIFT_PORT = 9090

bmv2_logger = logging.getLogger('bmv2_logger')

bmv2_lib_log_formatter = logging.Formatter("Line:%(lineno)d at %(asctime)s [%(levelname)s]: %(message)s \n")

bmv2_file_handler = logging.FileHandler(BMV2_LOG_FILE_NAME, mode='w')
bmv2_file_handler.setLevel(logging.DEBUG)
bmv2_file_handler.setFormatter(bmv2_lib_log_formatter)

bmv2_console_handler = logging.StreamHandler(sys.stdout)
bmv2_console_handler.setLevel(logging.INFO)
bmv2_console_handler.setFormatter(bmv2_lib_log_formatter)

bmv2_logger.setLevel(logging.DEBUG)
bmv2_logger.addHandler(bmv2_console_handler)
bmv2_logger.addHandler(bmv2_file_handler)



def send_cli_command_to_bmv2(cli_command, thrift_ip = '0.0.0.0', thrift_port=DEFAULT_THRIFT_PORT ):
    command_as_word_array = ['docker','exec',BMV2_DOCKER_CONTAINER_NAME,'sh', '-c', f"echo \'{cli_command}\' | simple_switch_CLI --thrift-ip {thrift_ip} --thrift-port {thrift_port}"  ]

    proc = subprocess.run(command_as_word_array, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    response = proc.stdout.strip()
    bmv2_logger.debug(f'\nResponse from bmv2 for sending command:\n{cli_command}\nis:\n{response}')
    return response
    

def add_entry_to_bmv2(communication_protocol, table_name, action_name,
                      match_keys, action_params, thrift_ip = '0.0.0.0', thrift_port=DEFAULT_THRIFT_PORT):
    if communication_protocol == P4_CONTROL_METHOD_THRIFT_CLI:
        cli_command = f'table_dump_entry_from_key {table_name} {match_keys}'
        response = send_cli_command_to_bmv2(cli_command, thrift_ip, thrift_port)
        #  print(f'Sent command: {cli_command} \nresponse: {response}')
        if 'Invalid table operation (BAD_MATCH_KEY)' in response: # entry doesn't exist
            cli_command = "table_add " + table_name + ' ' + action_name + ' ' + match_keys + ' => ' + action_params
            response = send_cli_command_to_bmv2(cli_command, thrift_ip, thrift_port)
            bmv2_logger.debug('\nresponse received: ' + response )
            response_as_lines = response.splitlines()
            if ( 'Error' in response_as_lines[SWITCH_RESPONSE_LAST_LINE_INDEX] ):
                bmv2_logger.error( f'P4 Command Error:\n {cli_command} \nResponse Obtained: {response} ')
                return SWITCH_RESPONSE_ERROR
            elif 'Invalid' in response_as_lines[SWITCH_RESPONSE_LAST_LINE_INDEX]:
                bmv2_logger.error( f'P4 Command Invalid:\n {cli_command} \nResponse Obtained: {response} ')
                return SWITCH_RESPONSE_INVALID
            elif response_as_lines[-2].startswith("Entry has been added with handle"):
                handle = [int(s) for s in response_as_lines[4] if s.isdigit()][0]
                bmv2_logger.debug("add entry with handle %d " % handle)
                return handle
        else:
            for line in response.splitlines():
                if 'Dumping entry' in line:
                    entry_handle = int( re.findall(r'0x[0-9A-F]+', line, re.I)[0] , 16  )
                    bmv2_logger.debug(f'entr_handle exists: {entry_handle}')
                    cli_command = f'table_modify {table_name} {action_name} {entry_handle} {action_params}'
                    break
            
             


def get_entry_handle(table_name, key, thrift_ip = '0.0.0.0', thrift_port=DEFAULT_THRIFT_PORT):
    command = f'table_dump_entry_from_key {table_name} {key}'
    response = send_cli_command_to_bmv2(command, thrift_ip, thrift_port)
    bmv2_logger.debug(f'getting entry handle from bmv2 for: {key}\n {response}')
    for line in response.splitlines():
        if 'Dumping entry' in line:
            handle = int( re.findall(r'0x[0-9A-F]+', line, re.I)[0] , 16  )
            bmv2_logger.debug(f'handle is: {handle}')
            return handle
    bmv2_logger.debug(f'could not find entry handle')
    return None


def delete_forwarding_entry_from_bmv2(
    communication_protocol, table_name, key, thrift_ip = '0.0.0.0', thrift_port=DEFAULT_THRIFT_PORT ):
    if communication_protocol == P4_CONTROL_METHOD_THRIFT_CLI:
        handle = get_entry_handle(table_name, key, thrift_ip, thrift_port)
        if handle != None:
            cli_command = f'table_delete {table_name} {handle}'
            send_cli_command_to_bmv2(cli_command, thrift_ip, thrift_port)
            return
        bmv2_logger.error(f'Entry Handle is None for table: {table_name}, and key: {key}')
