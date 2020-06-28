#!/usr/bin/env python3

import socket
import select
import sys
import datetime
from urllib.parse import parse_qs
import json

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
    data = '{"msg":"ok","result":"0","data":{"appKey":"'+robot_data['appKey']+'","deviceNo":"'+robot_data['deviceId']+'","token":"'
    data += 'j0PoVqC988Vyk89I3562951732429679'
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


registered_pages = {
    '/baole-web/common/sumbitClearTime.do': robot_clear_time,
    '/baole-web/common/getToken.do': robot_get_token,
    '/baole-web/common/*': robot_global
}

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
        data = self._sock.recv(65536)
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
                registered_pages[page](self)
                return
        if jump is not None:
            registered_pages[jump](self)
            return
        self.send_answer(404, "NOT FOUND")

    def add_header(self, name, value):
        self._headers_answer += (f'{name}: {value}\r\n').encode('utf8')

    def send_answer(self, data, error = 200, text = ''):
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
        self.send_answer(chunk.encode('utf8'))
        self.send_answer('0\r\n\r\n'.encode('utf8'))


class HTTPServer(BaseServer):
    def __init__(self, port = 80):
        super().__init__()
        self._sock.bind(('', port))
        self._sock.listen(10)

    def data_available(self):
        # there is a new connection
        newsock, address = self._sock.accept()
        return HTTPConnection(newsock, address)


class Multiplexer(object):
    def __init__(self, port = 80):
        self._socklist = []
        self._http_server = HTTPServer(port)
        self._add_socket(self._http_server)

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
