# Copyright 2020 (C) Raster Software Vigo (Sergio Costas)
#
# This file is part of OpenDoñita
#
# OpenDoñita is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# OpenDoñita is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import logging
import datetime
import json
import struct

from congaModules.robotManager import robot_manager
from congaModules.baseServer import BaseTcpServer
from congaModules.multiplexer import multiplexer
from congaModules.observer import Signal

class RobotServer(BaseTcpServer):
    def __init__(self):
        super().__init__()
        self._port = 20008

    def data_available(self):
        # there is a new connection
        print("Robot connected")
        newsock, address = self._sock.accept()
        return RobotConnection(newsock, address)


class RobotConnection(BaseTcpServer):
    def __init__(self, sock, address):
        super().__init__(sock)
        logging.info("Connected a new robot")
        self._address = address
        self._identified = False
        self._packet_queue = []
        self._packet_id = 1
        self._token = None
        self._deviceId = None
        self._appKey = None
        self._authCode = None
        self._deviceIP = None
        self._devicePort = None
        self._waiting_for_command = None
        multiplexer.timer.connect(self.timeout)
        self.statusUpdate = Signal("status", self)
        self._state = 0

    def timeout(self, signame, caller, now):
        self._next_command()

    def _next_command(self):
        if self._waiting_for_command is not None:
            return
        if len(self._packet_queue) == 0:
            return
        command, params = self._packet_queue.pop(0)
        if command == 'waitState':
            if (params == self._state) or ((params == 'home') and ((self._state == '5') or (self._state == '6'))):
                self._next_command()
            else:
                self._packet_queue.insert(0, (command, params))
            return
        if command == 'waitFor':
            print(f"WaitFor {params} ({datetime.datetime.now().timestamp()})")
            if datetime.datetime.now().timestamp() >= params:
                self._next_command()
            else:
                self._packet_queue.insert(0, (command, params))
            return
        self.send_command(command, params, True)


    def send_command(self, command, params, from_next_command = False):
        if not self._identified:
            logging.error("Sent a command before the robot has identified itself")
            return 4, "Not identified"

        wait_for_ack = True
        extraCommand = None
        extraCommand2 = None

        if command == 'wait':
            if 'seconds' not in params:
                return 6, "Missing parameter (seconds)"
            if self._waiting_for_command is not None:
                self._packet_queue.append((command, params))
            else:
                self._packet_queue.insert(0, ('waitFor', (datetime.datetime.now().timestamp() + int(params['seconds']))))
            return 0, "{}"

        if command == 'waitState':
            if 'state' not in params:
                return 6, "Missing parameter (state)"
            if params['state'] == 'cleaning':
                state = '1'
            elif params['state'] == 'stopped':
                state = '2'
            elif params['state'] == 'returning':
                state = '4'
            elif params['state'] == 'charging':
                state = '5'
            elif params['state'] == 'charged':
                state = '6'
            elif params['state'] == 'home':
                state = 'home'
            else:
                return 7, "Invalid value (valid values are 'cleaning', 'stopped', 'returning', 'charging', 'charged' and 'home'"
            if (self._waiting_for_command is not None) or (self._state != state):
                self._packet_queue.append((command, state))
            return 0, "{}"

        if command == 'clean':
            logging.info("Starting to clean")
            ncommand = '100'
        elif command == 'stop':
            logging.info("Stopping cleaning")
            ncommand = '102'
        elif command == 'return':
            logging.info("Returning to base")
            ncommand = '104'
        elif command == 'updateMap':
            logging.info("Asking map")
            ncommand = '131'
        elif command == 'sound':
            if "status" not in params:
                return 6, "Missing parameter (status)"
            if params['status'] == '0':
                logging.info("Disabling sound")
                ncommand = '125'
            elif params['status'] == '1':
                logging.info("Enabling sound")
                ncommand = '123'
            else:
                return 7, "Invalid value (valid values are 0 and 1)"
        elif command == 'fan':
            ncommand = '110'
            if 'speed' not in params:
                return 6, "Missing parameter (speed)"
            if params['speed'] == '0':
                extraCommand = '"fan":"1"' # OFF
            elif params['speed'] == '1':
                extraCommand = '"fan":"4"' # ECO
            elif params['speed'] == '2':
                extraCommand = '"fan":"2"' # NORMAL
            elif params['speed'] == '3':
                extraCommand = '"fan":"3"' # TURBO
            else:
                return 7, "Invalid value (valid values are 0, 1, 2 and 3)"
            logging.info(f"Setting fan to {params['speed']}")
        elif command == 'watertank':
            ncommand = '145'
            if 'speed' not in params:
                return 6, "Missing parameter (speed)"
            if params['speed'] == '0':
                extraCommand2 = '"waterTank":"255"' # OFF
            elif params['speed'] == '1':
                extraCommand2 = '"waterTank":"60"' # SMALL
            elif params['speed'] == '2':
                extraCommand2 = '"waterTank":"40"' # NORMAL
            elif params['speed'] == '3':
                extraCommand2 = '"waterTank":"20"' # FAST
            else:
                return 7, "Invalid value (valid values are 0, 1, 2 and 3)"
            logging.info(f"Setting water to {params['speed']}")
        elif command == 'mode':
            ncommand = '106'
            if 'type' not in params:
                return 6, "Missing parameter (type)"
            if params['type'] == 'auto':
                extraCommand = '"mode":"11"'
            elif params['type'] == 'gyro':
                extraCommand = '"mode":"1"'
            elif params['type'] == 'random':
                extraCommand = '"mode":"3"'
            elif params['type'] == 'borders':
                extraCommand = '"mode":"4"'
            elif params['type'] == 'area':
                extraCommand = '"mode":"6"'
            elif params['type'] == 'x2':
                extraCommand = '"mode":"8"'
            elif params['type'] == 'scrub':
                extraCommand = '"mode":"10"'
            else:
                return 7, "Invalid value (valid values are 'auto','giro','random','borders','area','x2','scrub')"
            logging.info(f"Setting mode to {params['type']}")
        elif command == 'notifyConnection': # seems to be sent whenever the tablet connects to the server
            ncommand = '400'
            wait_for_ack = False
            logging.info("Web client opened")
        elif command == 'askStatus': # seems to ask the robot to send a Status packet
            ncommand = '98'
            wait_for_ack = False
            logging.info("Asking status")
        else:
            logging.error(f"Unknown command {command}")
            return 5, "Unknown command"

        if self._waiting_for_command is not None:
            print("waiting for command")
            self._packet_queue.append((command, params))
            return 0, "{}"

        self._packet_id += 1
        if wait_for_ack:
            self._waiting_for_command = self._packet_id
        data = '{"cmd":0,"control":{"authCode":"'
        data += self._authCode
        data += '","deviceIp":"'
        data += self._deviceIP
        data += '","devicePort":"'
        data += self._devicePort
        data += '","targetId":"1","targetType":"3"},"seq":0,"value":{'
        if extraCommand is not None:
            data += extraCommand+','
        data += '"transitCmd":"'
        data += ncommand
        data += '"'
        if extraCommand2 is not None:
            data += ','+extraCommand2
        data += '}}\n'
        print(f"Sending command {data}")
        self._send_packet(0x00c800fa, 0x01090000, self._packet_id, 0x00, data)
        if not wait_for_ack:
            self._next_command()
        return 0, "{}"


    def close(self):
        print("Robot disconnected")
        multiplexer.timer.disconnect(self.timeout)
        super().close()
        self._identified = False


    def new_data(self):

        if len(self._data) < 20:
            return False
        header = struct.unpack("<LLLLL", self._data[0:20])
        if len(self._data) < header[0]:
            return False
        payload = self._data[20:header[0]]
        self._data = self._data[header[0]:]

        # process the packet
        # PING
        if self._check_header(header, 0x14, 0x00c80100, 0x01,0x03e7):
            print("Pong")
            self._send_packet(0x00c80111, 0x01080001, header[3], 0x03e7)
            return True
        # Identification
        if self._check_header(header, None, 0x0010, 0x0001, 0x00):
            self._send_payload(payload)
            self._log_payload(payload, "connection")
            payload = json.loads(payload)
            self._token = payload['value']['token']
            self._deviceId = payload['value']['deviceId']
            self._appKey = payload['value']['appKey']
            self._authCode = payload['value']['authCode']
            self._deviceIP = payload['value']['deviceIp']
            self._devicePort = payload['value']['devicePort']
            robot_manager.get_robot(self._deviceId).connected(self)
            self._identified = True
            now = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            self._send_packet(0x00c80011, 0x01, header[3], 0x00, '{"msg":"login succeed","result":0,"version":"1.0","time":"'+now+'"}')
            logging.info(f"Robot identified as {self._deviceId} at IP {self._deviceIP}")
            return True
        # Status
        if self._check_header(header, None, 0x0018, 0x0001, 0x00):
            print("Status")
            self._send_packet(0x00c80019, 0x01, header[3], 0x01, '{"msg":"OK","result":0,"version":"1.0"}\n')
            self._send_payload(payload)
            self._log_payload(payload, "status")
            self._next_command()
            return True
        # ACK
        if self._check_header(header, None, 0x000000fa, 0x0001, 0x00):
            if self._waiting_for_command is not None:
                if header[3] == self._waiting_for_command:
                    self._send_payload(payload)
                    self._waiting_for_command = None
                    print("ACK fine")
                    self._next_command()
                else:
                    print("ACK error")
            return True
        # Map
        if self._check_header(header, None, 0x0014, 0x0001, 0x00):
            print("Map")
            self._send_payload(payload)
            self._log_payload(payload, "map")
            return True
        # Error
        if self._check_header(header, None, 0x0016, 0x0001, 0x00):
            print("Error")
            self._log_payload(payload, "error")
            self._send_packet(0x00c80019, 0x01, header[3], 0x01, '{"msg":"OK","result":0,"version":"1.0"}\n')
            self._packet_queue = []
            return True
        print("Unknown packet")
        print(header)
        print(payload)
        logging.info(f"Unknown packet {header} {payload}")
        return True

    def _log_payload(self, payload, type):
        try:
            jsonPayload = json.loads(payload)
        except:
            print(f'Payload is not a JSON file: "{payload}"')
            logging.error(f'Payload is not a JSON file: "{payload}"')
            return
        logging.info(f"New {type}: {json.dumps(jsonPayload, sort_keys=True, indent=4)}\n\n")

    def _send_payload(self, payload):
        if len(payload) == 0:
            return
        try:
            jsonPayload = json.loads(payload)
        except:
            print(f'Payload is not a JSON file: "{payload}"')
            return

        if ('value' in jsonPayload) and ('workState' in jsonPayload['value']):
            self._state = jsonPayload['value']['workState']

        self.statusUpdate.emit(jsonPayload)

    def _check_header(self, header, value0, value1, value2, value4):
        if (value0 is not None) and (value0 != header[0]):
            return False
        if (value1 is not None) and (value1 != header[1]):
            return False
        if (value2 is not None) and (value2 != header[2]):
            return False
        if (value4 is not None) and (value4 != header[4]):
            return False
        return True

    def _send_packet(self, value1, value2, packet_id, value3, data = b""):
        if isinstance(data, str):
            data = data.encode('utf8')
        header = bytearray(struct.pack("<LLLLL", 20 + len(data), value1, value2, packet_id, value3))
        self._sock.send(header + data)
        # data2 = struct.unpack("BBBBBBBBBBBBBBBBBBBB", header)
        # c = 0
        # for n in data2:
        #     d = hex(n)[2:]
        #     if n < 16:
        #         d = "0"+d
        #     print(d + " ", end="")
        #     c += 1
        #     if (c%4 == 0) and (c < 20):
        #         print("| ", end="")
        # print()
        # if len(data) > 0:
        #     print("    '"+ data.decode('utf8').replace('\n','\\n\n    ').replace('\r','\\r') + "'")
        # print()

robot_server = RobotServer()
