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

import json
from urllib.parse import parse_qs

from congaModules.baseServer import BaseTcpServer

class HTTPServer(BaseTcpServer):
    def __init__(self):
        super().__init__()
        self._registered_pages = {}
        self._port = 80

    def set_pages(self, registered_pages):
        self._registered_pages = registered_pages

    def data_available(self):
        # there is a new connection
        newsock, address = self._sock.accept()
        return HTTPConnection(self._registered_pages, newsock, address)

class HTTPConnection(BaseTcpServer):
    """ Manages an specific connection to the HTTP server """

    def __init__(self, registered_pages, sock, address):
        super().__init__(sock)
        self._registered_pages = registered_pages
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
                return False
            header = self._data[:pos].split(b"\r\n")
            self._data = self._data[pos+4:]
            self.headers = {}
            http_line = header[0].decode('utf8').split(" ")
            self._command = http_line[0]
            self._URI = http_line[1]
            if (len(self._URI) == 0) or (self._URI[0] != '/'):
                self._URI = '/' + self._URI
            self._protocol = http_line[2]
            for entry in header[1:]:
                pos = entry.find(b":")
                if pos != -1:
                    self.headers[entry[:pos].decode('utf8').strip()] = entry[pos+1:].decode('utf8').strip()
        if 'Content-Length' in self.headers:
            if len(self._data) < int(self.headers['Content-Length']):
                return False
        self._process_data()
        return False

    def _process_data(self):
        length = 0
        jump = None
        path = self.get_path()
        for page in self._registered_pages:
            if page[-1] == '*':
                if path.startswith(page[:-1]):
                    if length < len(page):
                        jump = page
                        length = len(page)
                continue
            if path == page:
                #print(f'{self._URI}')
                #print(f'{self._data}')
                self._registered_pages[page](self)
                return
        if jump is not None:
            #print(f'{self._URI}')
            #print(f'{self._data}')
            self._registered_pages[jump](self)
            return
        self.send_answer("", 404, "NOT FOUND")
        self.close()

    def add_header(self, name, value):
        self._headers_answer += (f'{name}: {value}\r\n').encode('utf8')

    def send_answer_json_close(self, data):
        result = '{"error":0, "value": '+json.dumps(data)+'}'
        self.add_header("Content-Type", "application/json")
        self.send_answer(result.encode('utf8'), 200, 'OK')
        self.close()

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

    def get_path(self):
        pos = self._URI.find("?")
        if pos == -1:
            return self._URI
        else:
            return self._URI[:pos]

    def get_params(self):
        pos = self._URI.find("?")
        if pos == -1:
            return {}
        else:
            tmpdata = parse_qs(self._URI[pos+1:])
            data = {}
            for element in tmpdata:
                data[element] = tmpdata[element][0]
            return data

    def convert_data(self):
        if ('Content-Type' in self.headers):
            if self.headers['Content-Type'] == 'application/x-www-form-urlencoded':
                tmpdata = parse_qs(self._data.decode('utf8'))
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


http_server = HTTPServer()
