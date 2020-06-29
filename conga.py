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

import sys
import struct

if len(sys.argv) < 2:
    print("Uso: conga.py FICHERO.PCAP")
    sys.exit(-1)

class IP(object):
    def __init__(self, data, tiempo):
        self._data = data
        self.tiempo = tiempo
        self.src = struct.unpack(">L", data[12:16])[0]
        self.dst = struct.unpack(">L", data[16:20])[0]
        self.longitud = struct.unpack(">H", data[2:4])[0]
        self.protocol = data[9]
        ihl = 4 * (data[0] & 0x0F)
        self.payload = data[ihl:ihl+self.longitud]

class TCP(object):
    def __init__(self, ip):
        self.ip = ip
        self.tiempo = ip.tiempo
        payload = ip.payload
        self.src_port = struct.unpack(">H", payload[0:2])[0]
        self.dst_port = struct.unpack(">H", payload[2:4])[0]
        self.src = ip.src
        self.dst = ip.dst
        offset = (payload[12] // 4) & 0x3C
        self.payload = payload[offset:]
        self.longitud = len(self.payload)


class PCAP(object):
    def __init__(self, fichero):
        self._data = open(fichero, "br").read()
        self._pos = 24 # jump over pcap header

    def _read_pkt(self):
        if self._pos >= len(self._data):
            return None, 0
        header = struct.unpack("=LLLL", self._data[self._pos: self._pos + 16])
        tiempo = header[0] + (header[1] / 1000000)
        data = self._data[self._pos+16:self._pos+16+header[2]]
        self._pos += 16 + header[3]
        return data, tiempo

    def next_pkt(self):
        while True:
            data, tiempo = self._read_pkt()
            if data is None:
                return None
            ptype = struct.unpack(">H", data[12:14])[0]
            if ptype == 2048: # IPv4
                packet = IP(data[14:], tiempo)
                if packet.protocol == 6: # TCP
                    return TCP(packet)

class SEQUENCE(object):
    def __init__(self, way, port = None):
        self._data = b""
        self._way = way
        self._timedif = 0
        self.port = port

    def set_timedif(self, diferencia):
        self._timedif = diferencia

    def add_data(self, packet):
        self._data += packet.payload
        if len(self._data) < 4:
            return
        size = struct.unpack("<L",self._data[:4])[0]
        if len(self._data) >= size:
            block = self._data[:size]
            self._data = self._data[size:]
            self._print_block(block, packet.tiempo)

    def _print_block(self, block, tiempo):
        print(tiempo - self._timedif)
        print(f"{self._way} ", end="")
        if self.port is not None:
            print(f"({self.port}) ", end="")
        data = struct.unpack("BBBBBBBBBBBBBBBBBBBB", block[:20])
        for n in data:
            d = hex(n)[2:]
            if n < 10:
                d = "0"+d
            print(d + " ", end="")
        print()
        if len(block) > 20:
            print("    "+ block[20:].decode('utf-8').replace('\n','\n    '))
        print()

pcap = PCAP(sys.argv[1])
if len(sys.argv) > 2:
    modo = sys.argv[2]
else:
    modo = "0"
if modo == "0":
    aspiradora = struct.unpack(">L",bytearray([192,168,18,14]))[0]
    tablet = struct.unpack(">L",bytearray([192,168,18,11]))[0]
    servidor = struct.unpack(">L",bytearray([47,91,67,181]))[0]
elif modo == "1":
    aspiradora = struct.unpack(">L",bytearray([192,168,18,14]))[0]
    tablet = struct.unpack(">L",bytearray([192,168,18,11]))[0]
    servidor = struct.unpack(">L",bytearray([192,168,0,21]))[0]
elif modo == "2":
    aspiradora = struct.unpack(">L",bytearray([192,168,0,21]))[0]
    tablet = struct.unpack(">L",bytearray([192,168,18,11]))[0]
    servidor = struct.unpack(">L",bytearray([192,168,0,21]))[0]

tablet_servidor = False

data_aspiradora_servidor = SEQUENCE("a->s")
data_servidor_aspiradora = SEQUENCE("s->a")
data_tablet_aspiradora = {}
data_aspiradora_tablet = {}

def tomar_contenido(paquete):
    return paquete.payload.decode('latin1').replace('\r', '\\r').replace('\n','\\n\n    ')

primero = True
time_first = 0
while True:
    paquete = pcap.next_pkt()
    if paquete is None:
        break
    if primero:
        data_aspiradora_servidor.set_timedif(paquete.tiempo)
        data_servidor_aspiradora.set_timedif(paquete.tiempo)
        time_first = paquete.tiempo
        primero = False

    if (paquete.src == tablet and paquete.dst == servidor) or (paquete.dst == tablet and paquete.src == servidor):
        if not tablet_servidor:
            print("Tablet y servidor")
            tablet_servidor = True
        continue
    if (paquete.src == aspiradora and paquete.dst == servidor):
        tablet_servidor = False
        if paquete.dst_port == 80:
            if paquete.longitud != 0:
                print("HTTP aspiradora a servidor:")
                contenido = tomar_contenido(paquete)
                print(f"    {contenido}")
            continue
        if paquete.dst_port == 20008:
            data_aspiradora_servidor.add_data(paquete)
    if (paquete.dst == aspiradora and paquete.src == servidor):
        if paquete.src_port == 80:
            if paquete.longitud != 0:
                print("HTTP servidor a aspiradora:")
                contenido = tomar_contenido(paquete)
                print(f"    {contenido}")
            continue
        if paquete.src_port == 20008:
            data_servidor_aspiradora.add_data(paquete)
    if (paquete.dst == aspiradora and paquete.src == tablet):
        if paquete.src_port not in data_tablet_aspiradora:
            data_tablet_aspiradora[paquete.src_port] = SEQUENCE("t->a", paquete.src_port)
            data_tablet_aspiradora[paquete.src_port].set_timedif(time_first)
        data_tablet_aspiradora[paquete.src_port].add_data(paquete)
    if (paquete.src == aspiradora and paquete.dst == tablet):
        if paquete.dst_port not in data_aspiradora_tablet:
            data_aspiradora_tablet[paquete.dst_port] = SEQUENCE("a->t", paquete.dst_port)
            data_aspiradora_tablet[paquete.dst_port].set_timedif(time_first)
        data_aspiradora_tablet[paquete.dst_port].add_data(paquete)
