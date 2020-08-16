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
import logging
from congaModules.observer import Signal

class BaseServer(object):
    def __init__(self):
        super().__init__()
        self._data = b""
        self._closed = True # by default can't be closed
        self.closedSignal = Signal("closed", self)
        self._port = None

    def added(self):
        pass

    def set_port(self, port):
        """ Called to set the port. This marks it to be binded or not in added() """
        self._port = port

    def fileno(self):
        return self._sock.fileno()

    def close(self):
        """ Called when the socket is closed and the class will be destroyed """
        if not self._closed:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                self._sock.close()
            except:
                pass
            self._closed = True
            self.closedSignal.emit()

    def data_available(self):
        pass


class BaseTcpServer(BaseServer):
    def __init__(self, sock = None):
        super().__init__()
        if sock is None:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self._sock = sock
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self._closed = False # TCP sockets can be closed

    def added(self):
        if (self._port is not None):
            self._sock.bind(('', self._port))
            self._sock.listen(10)

    def new_data(self):
        """ Called every time new data is added to self._data
            Overwrite to process arriving data. The function must
            remove from self._data the data already processed
            @return False if there wasn't enough data for a full message; wait for more data
                    True  if a full message was read and it should be called again because
                          there can be another message in the buffer """

        # here just remove the read data
        self._data = b""
        return False

    def data_available(self):
        """ Called whenever there is data to be read in the socket.
            Overwrite only to detect when there are new connections """
        try:
            data = self._sock.recv(65536)
        except Error as e:
            self.close()
            print(f"Connection lost {self.fileno()}")
            print(e)
            return
        if len(data) > 0:
            self._data += data
            while True:
                if not self.new_data():
                    break
        else:
            # socket closed
            self.close()


class BaseUdpServer(BaseServer):
    def __init__(self, sock = None):
        super().__init__()
        if sock is None:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        else:
            self._sock = sock
        self._closed = False # TCP sockets can be closed
        self._address = ''

    def set_address(self, addr):
        self._address = addr

    def added(self):
        if self._port is not None:
            self._sock.bind((self._address, self._port))
