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

import struct
import socket

from congaModules.baseServer import BaseUdpServer
from congaModules.multiplexer import multiplexer
from congaModules.observer import Signal


class UPNPServer(BaseUdpServer):
    def __init__(self):
        super().__init__()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._period = 2
        self._before = 0

    def added(self):
        super().added()
        mreq = struct.pack("4sl", socket.inet_aton(self._address), socket.INADDR_ANY)
        self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    def data_available(self):
        data, addr = self._sock.recvfrom(65536)
        print("Recibido UDP")
        data = data.decode('utf-8')
        if data.startswith('M-SEARCH'):
            print(data)
            print("Emitiendo aviso\n\n")
            data  = 'HTTP/1.1 200 OK\r\n'
            data += 'Cache-Control: max-age=1900\r\n'
            data += 'USN: uuid:534b354f-0886-4312-9c39-8336c32357bc::upnp:rootdevice\r\n'
            data += 'Server: Linux/2.6.18_pro500 UPnP/1.0 MiniUPnPd/1.5\r\n'
            data += 'ST:upnp:rootdevice\r\n'
            data += 'Location: http://192.168.0.32/IGD.xml\r\n\r\n'
            self._sock.sendto(data.encode('utf-8'), addr)
        return None

upnp_server = UPNPServer()
upnp_server.set_port(1900)
upnp_server.set_address('239.255.255.250')
