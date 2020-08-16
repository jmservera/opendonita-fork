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


class UPNPAnouncer(BaseUdpServer):
    def __init__(self):
        super().__init__()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        multiplexer.timer.connect(self.timeout)
        self._period = 2
        self._before = 0

    def timeout(self, signame, caller, now):
        if (now - self._before) >= self._period:
            self._before = now
            self._send_announcement()

    def _send_announcement(self):
        print("Sending announcement")
        address = "239.255.255.250"
        port = 1900

        data  = 'M-SEARCH * HTTP/1.1\r\n'
        data += 'MX: 5\r\n'
        data += 'ST: upnp:rootdevice\r\n'
        data += 'MAN: "ssdp:discover"\r\n'
        data += 'User-Agent: UPnP/1.0 DLNADOC/1.50 Platinum/1.0.5.13\r\n'
        data += 'Connection: close\r\n'
        data += 'Host: 239.255.255.250:1900\r\n\r\n'
        self._sock.sendto(data.encode('utf-8'), (address, port))


    def data_available(self):
        data, addr = self._sock.recvfrom(65536)
        print("Recibido UDP 2")
        data = data.decode('utf-8')
        print(data)
        print("Fin UDP2")
        return None

upnp_anouncer = UPNPAnouncer()
