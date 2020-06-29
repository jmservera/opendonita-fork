#!/usr/bin/env python3

import http.server
from urllib.parse import parse_qs
import socketserver
import json
import random
import time
import os

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

robot_data = {}

class ServidorHTTP(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self._process_petition()

    def do_POST(self):
        self._process_petition()

    def _process_petition(self):
        global robot_data

        data = None
        self._cabecera = "HTTP/1.1 200 \r\n"
        if 'Content-Length' in self.headers:
            length = int(self.headers['Content-Length'])
            if length != 0:
                content = self.rfile.read(length)
                if ('Content-Type' in self.headers):
                    if self.headers['Content-Type'] == 'application/x-www-form-urlencoded':
                        tmpdata = parse_qs(content.decode('utf8'))
                        data = {}
                        for element in tmpdata:
                            data[element] = tmpdata[element][0]
                    elif self.headers['Content-Type'].startswith('application/json'):
                        data = json.loads(content)

        if self.path == '/baole-web/common/sumbitClearTime.do':
            robot_data['appKey'] = data['appKey']
            robot_data['deviceId'] = data['deviceId']
            robot_data['deviceType'] = data['deviceType']
            self._send_robot_header()
            self._send_chunked('{"msg":"ok","result":"0","version":"1.0.0"}')
            return

        if self.path == '/baole-web/common/getToken.do':
            robot_data['appKey'] = data['appKey']
            robot_data['deviceId'] = data['deviceId']
            robot_data['deviceType'] = data['deviceType']
            robot_data['authCode'] = data['authCode']
            robot_data['funDefine'] = data['funDefine']
            robot_data['nonce'] = data['nonce_str']
            if 'Set-Cookie' in data:
                robot_data['cookie'] = data['Set-Cookie']
            token = ''
            for a in range(32):
                v = random.randint(0,9)
                token += chr(48 + v)
            robot_data['token'] = token
            self._send_robot_header()
            data = '{"msg":"ok","result":"0","data":{"appKey":"'+robot_data['appKey']+'","deviceNo":"'+robot_data['deviceId']+'","token":"'
            data += 'j0PoVqC988Vyk89I3562951732429679'
            data += '"},"version":"1.0.0"}'
            self._send_chunked(data)
            return

        if self.path.startswith('/baole-web/common/'):
            self._send_robot_header()
            self._send_chunked('{"msg":"ok","result":"0","version":"1.0.0"}')
            return

    def send_header(self, token, data):
        if token != 'Server':
            self._cabecera += f"{token}: {data}\r\n"

    def end_headers(self):
        self._cabecera += "\r\n"

    def _send_robot_header(self):
        self.protocol_version = 'HTTP/1.1'
        self.send_response(200, message="")
        self.send_header('Content-Type', 'application/json;charset=UTF-8')
        self.send_header('Transfer-Encoding', 'chunked')
        self.send_header('Connection', 'close')
        self.send_header('Set-Cookie', 'SERVERID=2423aa26fbdf3112bc4aa0453e825ac8|1592686775|1592686775;Path=/')
        self.end_headers()

    def _send_chunked(self, text):
        chunk = f'{hex(len(text))[2:]}\r\n{text}\r\n'
        print(f"Envio {chunk}")
        os.write(self.wfile.fileno(),(self._cabecera + chunk).encode('utf8'))
        time.sleep(.4)
        os.write(self.wfile.fileno(),'0\r\n\r\n'.encode('utf8'))

httpd = http.server.HTTPServer(('', 80), ServidorHTTP)
httpd.serve_forever()
