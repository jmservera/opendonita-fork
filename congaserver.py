#!/usr/bin/env python3

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


import socket
import select
import sys
import datetime
from urllib.parse import parse_qs
import json
import struct
import random

robot_data = {}

def robot_clear_time(server_object):
    server_object.convert_data()
    send_robot_header(server_object)
    server_object.send_chunked('{"msg":"ok","result":"0","version":"1.0.0"}')
    server_object.close()


def robot_get_token(server_object):
    server_object.convert_data()

    data = server_object.get_data()
    robot_data['appKey'] = data['appKey']
    robot_data['deviceId'] = data['deviceId']
    robot_data['deviceType'] = data['deviceType']
    robot_data['authCode'] = data['authCode']
    robot_data['funDefine'] = data['funDefine']
    robot_data['nonce'] = data['nonce_str']

    send_robot_header(server_object)
    token = ''
    for a in range(32):
        v = random.randint(0,9)
        token += chr(48 + v)
    data = '{"msg":"ok","result":"0","data":{"appKey":"'+robot_data['appKey']+'","deviceNo":"'+robot_data['deviceId']+'","token":"'
    data += token
    data += '"},"version":"1.0.0"}'
    server_object.send_chunked(data)
    server_object.close()


def robot_global(server_object):
    server_object.send_chunked('{"msg":"ok","result":"0","version":"1.0.0"}')
    server_object.close()


def send_robot_header(server_object):
    server_object.protocol = 'HTTP/1.1'
    server_object.add_header('Content-Type', 'application/json;charset=UTF-8')
    server_object.add_header('Transfer-Encoding', 'chunked')
    server_object.add_header('Connection', 'close')
    server_object.add_header('Set-Cookie', 'SERVERID=2423aa26fbdf3112bc4aa0453e825ac8|1592686775|1592686775;Path=/')


def robot_action(server_object):
    robots = robotManager.get_robot_list()
    uri = server_object.get_uri()
    if uri == '/action/clean':
        print("Action: clean")
        for robot_id in robots:
            robot = robotManager.get_robot(robot_id)
            robot.clean()
    elif uri == '/action/stop':
        print("Action: stop")
        for robot_id in robots:
            robot = robotManager.get_robot(robot_id)
            robot.stop()
    elif uri == '/action/return':
        print("Action: return")
        for robot_id in robots:
            robot = robotManager.get_robot(robot_id)
            robot.return_base()
    server_object.send_answer("OK\n", 200, "OK")
    server_object.close()


def robot_control(server_object):
    with open("index.html", "r") as page:
        data = page.read()

    server_object.send_answer(data, 200, "OK")
    server_object.close()

registered_pages = {
    '/baole-web/common/sumbitClearTime.do': robot_clear_time,
    '/baole-web/common/getToken.do': robot_get_token,
    '/baole-web/common/*': robot_global,
    '/action/*': robot_action,
    '/': robot_control
}


class RobotManager(object):
    def __init__(self):
        self._robots = {} # contains Robot objects, one per physical robot, identified by the DeviceId

    def get_robot(self, deviceId):
        if deviceId not in self._robots:
            self._robots[deviceId] = Robot()
        return self._robots[deviceId]

    def get_robot_list(self):
        l = []
        for a in self._robots:
            l.append(a)
        return l

robotManager = RobotManager()

class BaseServer(object):
    def __init__(self, sock = None):
        if sock is None:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self._sock = sock
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self._data = b""
        self._closed = False

    def fileno(self):
        return self._sock.fileno()

    def timeout(self):
        """ Called once per second. Useful for timeouts """
        pass

    def new_data(self):
        """ Called every time new data is added to self._data
            Overwrite to process arriving data. The function must
            remove from self._data the data already processed """

        # here just remove the read data
        self._data = b""
        pass

    def close(self):
        """ Called when the socket is closed and the class will be destroyed """
        if not self._closed:
            self._sock.close()
        self._closed = True

    def get_closed(self):
        return self._closed

    def data_available(self):
        """ Called whenever there is data to be read in the socket.
            Overwrite only to detect when there are new connections """
        try:
            data = self._sock.recv(65536)
        except:
            self.close()
            print("Connection closed")
            return
        if len(data) > 0:
            self._data += data
            self.new_data()
        else:
            # socket closed
            self.close()


class HTTPConnection(BaseServer):
    """ Manages an specific connection to the HTTP server """

    def __init__(self, sock, address):
        super().__init__(sock)
        self._address = address
        self.headers = None
        self.protocol = 'HTTP/1.0'
        self._headers_answer = b""
        self._return_error = 200
        self._return_error_text = ""
        self._answer_sent = False

    def new_data(self):
        if self.headers is None:
            pos = self._data.find(b"\r\n\r\n")
            if pos == -1:
                return
            header = self._data[:pos].split(b"\r\n")
            self._data = self._data[pos+4:]
            self.headers = {}
            http_line = header[0].decode('latin1').split(" ")
            self._command = http_line[0]
            self._URI = http_line[1]
            self._protocol = http_line[2]
            for entry in header[1:]:
                pos = entry.find(b":")
                if pos != -1:
                    self.headers[entry[:pos].decode('latin1').strip()] = entry[pos+1:].decode('latin1').strip()
        if 'Content-Length' in self.headers:
            if len(self._data) != int(self.headers['Content-Length']):
                return
        self._process_data()

    def _process_data(self):
        global registered_pages

        length = 0
        jump = None
        for page in registered_pages:
            if page[-1] == '*':
                if self._URI.startswith(page[:-1]):
                    if length < len(page):
                        jump = page
                        length = len(page)
                continue
            if self._URI == page:
                print(f'{self._URI}')
                registered_pages[page](self)
                return
        if jump is not None:
            print(f'{self._URI}')
            registered_pages[jump](self)
            return
        self.send_answer("", 404, "NOT FOUND")

    def add_header(self, name, value):
        self._headers_answer += (f'{name}: {value}\r\n').encode('utf8')

    def send_answer(self, data, error = 200, text = ''):
        if isinstance(data, str):
            data = data.encode('utf8')
        if not self._answer_sent:
            cmd = (f'{self.protocol} {error} {text}\r\n').encode('utf8')
            cmd += self._headers_answer
            cmd += b'\r\n'
            cmd += data
        else:
            cmd = data
        self._answer_sent = True
        self._sock.send(cmd)

    def get_data(self):
        return self._data

    def get_uri(self):
        return self._URI

    def convert_data(self):
        if ('Content-Type' in self.headers):
            if self.headers['Content-Type'] == 'application/x-www-form-urlencoded':
                tmpdata = parse_qs(self._data.decode('latin1'))
                data = {}
                for element in tmpdata:
                    data[element] = tmpdata[element][0]
                self._data = data
            elif self.headers['Content-Type'].startswith('application/json'):
                self._data = json.loads(self._data)

    def send_chunked(self, text):
        chunk = f'{hex(len(text))[2:]}\r\n{text}\r\n'
        self.send_answer(chunk)
        self.send_answer('0\r\n\r\n')


class HTTPServer(BaseServer):
    def __init__(self, port = 80):
        super().__init__()
        self._sock.bind(('', port))
        self._sock.listen(10)

    def data_available(self):
        # there is a new connection
        newsock, address = self._sock.accept()
        return HTTPConnection(newsock, address)


class RobotServer(BaseServer):
    def __init__(self, port = 20008):
        super().__init__()
        self._sock.bind(('', port))
        self._sock.listen(10)

    def data_available(self):
        # there is a new connection
        print("Robot connected")
        newsock, address = self._sock.accept()
        return RobotConnection(newsock, address)


class RobotConnection(BaseServer):
    def __init__(self, sock, address):
        super().__init__(sock)
        self._address = address
        self._robot = None
        self._packet_queue = []
        self._packet_id = 1
        self._token = None
        self._deviceId = None
        self._appKey = None
        self._authCode = None
        self._deviceIP = None
        self._devicePort = None
        self._waiting_for_command = False

    def timeout(self):
        self._next_command()

    def _next_command(self):
        if self._waiting_for_command:
            return
        if len(self._packet_queue) == 0:
            return
        command = self._packet_queue.pop(0)
        if command == "clean":
            self.clean()
            return
        if command == "stop":
            self.stop()
            return
        if command == "base":
            self.return_base()

    def clean(self):
        if self._robot is None:
            return
        if self._waiting_for_command:
            self._packet_queue.append("clean")
            return
        self._packet_id += 1
        data = '{"cmd":0,"control":{"authCode":"'
        data += self._authCode
        data += '","deviceIp":"'
        data += self._deviceIP
        data += '","devicePort":"'
        data += self._devicePort
        data += '","targetId":"1","targetType":"3"},"seq":0,"value":{"transitCmd":"100"}}'
        self._send_packet(0x00c800fa, 0x01090000, self._packet_id, 0x00, data)

    def return_base(self):
        if self._robot is None:
            return
        if self._waiting_for_command:
            self._packet_queue.append("clean")
            return
        self._packet_id += 1
        data = '{"cmd":0,"control":{"authCode":"'
        data += self._authCode
        data += '","deviceIp":"'
        data += self._deviceIP
        data += '","devicePort":"'
        data += self._devicePort
        data += '","targetId":"1","targetType":"3"},"seq":0,"value":{"transitCmd":"104"}}'
        self._send_packet(0x00c800fa, 0x4cd60000, self._packet_id, 0x00, data)


    def stop(self):
        if self._robot is None:
            return
        if self._waiting_for_command:
            self._packet_queue.append("stop")
            return
        self._packet_id += 1
        data = '{"cmd":0,"control":{"authCode":"'
        data += self._authCode
        data += '","deviceIp":"'
        data += self._deviceIP
        data += '","devicePort":"'
        data += self._devicePort
        data += '","targetId":"1","targetType":"3"},"seq":0,"value":{"transitCmd":"102"}}'
        self._send_packet(0x00c800fa, 0x01090000, self._packet_id, 0x00, data)


    def close(self):
        print("Robot disconnected")
        super().close()
        if self._robot is not None:
            self._robot.disconnected()
        self._robot = None

    def new_data(self):
        global robotManager

        if len(self._data) < 20:
            return
        header = struct.unpack("<LLLLL", self._data[0:20])
        if len(self._data) < header[0]:
            return
        payload = self._data[20:header[0]]
        self._data = self._data[header[0]:]

        # process the packet
        # PING
        if self._check_header(header, 0x14, 0x00c80100, 0x01,0x03e7):
            print("Pong")
            self._send_packet(0xc80111, 0x01, header[3], 0x03e7)
            return
        # Identification
        if self._check_header(header, None, 0x0010, 0x0001, 0x00):
            print("Identification")
            payload = json.loads(payload)
            self._token = payload['value']['token']
            self._deviceId = payload['value']['deviceId']
            self._appKey = payload['value']['appKey']
            self._authCode = payload['value']['authCode']
            self._deviceIP = payload['value']['deviceIp']
            self._devicePort = payload['value']['devicePort']
            self._robot = robotManager.get_robot(self._deviceId)
            self._robot.connected(self)
            now = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            self._send_packet(0x00c80011, 0x01, header[3], 0x00, '{"msg":"login succeed","result":0,"version":"1.0","time":"'+now+'"}')
            return
        # Status
        if self._check_header(header, None, 0x0018, 0x0001, 0x00):
            print("Status")
            self._send_packet(0x00c80019, 0x01, header[3], 0x01, '{"msg":"OK","result":0,"version":"1.0"}')
            return
        # ACK
        if self._check_header(header, None, 0x000000fa, 0x0001, 0x00):
            if header[3] == self._packet_id:
                print("ACK fine")
            else:
                print("ACK error")
            self._waiting_for_command = False
            return
        print("Unknown packet")
        print(header)
        print(payload)


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
            data = data.encode('latin1')
        header = bytearray(struct.pack("<LLLLL", 20 + len(data), value1, value2, packet_id, value3))
        self._sock.send(header + data)



class Robot(object):
    """ Manages each physical robot """
    def __init__(self):
        self._connection = None
        self._status = "idle"

    def connected(self, connection):
        self._connection = connection

    def disconnected(self):
        self._connection = None

    def get_status(self):
        return self._status

    def clean(self):
        if self._connection is None:
            print("No conectado")
            return False
        print("Lanzo clean")
        self._connection.clean()

    def stop(self):
        if self._connection is None:
            print("No conectado")
            return False
        print("Lanzo stop")
        self._connection.stop()

    def return_base(self):
        if self._connection is None:
            print("No conectado")
            return False
        print("Lanzo return")
        self._connection.return_base()


class Multiplexer(object):
    def __init__(self, port = 80):
        self._socklist = []
        self._http_server = HTTPServer(port)
        self._add_socket(self._http_server)
        self._robot_server = RobotServer()
        self._add_socket(self._robot_server)

    def _add_socket(self, socket_class):
        if socket_class not in self._socklist:
            self._socklist.append(socket_class)

    def _remove_socket(self, socket_class):
        if socket_class in self._socklist:
            self._socklist.remove(socket_class)

    def run(self):
        self._second = datetime.datetime.now().time().second
        while True:
            readable, writable, exceptions = select.select(self._socklist[:], [], self._socklist[:])
            for has_data in readable:
                retval = has_data.data_available()
                if retval is not None:
                    self._add_socket(retval)
                if has_data.get_closed():
                    self._remove_socket(has_data)
            second = datetime.datetime.now().time().second
            if second != self._second:
                self._second = second
                for to_call in self._socklist:
                    to_call.timeout()


if len(sys.argv) > 1:
    port = int(sys.argv[1])
else:
    port = 80
multiplexer = Multiplexer(port)
multiplexer.run()
