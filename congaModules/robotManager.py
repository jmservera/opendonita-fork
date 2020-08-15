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

import configparser
import json
import os

class RobotManager(object):
    def __init__(self, config_path):
        super().__init__()
        self._robots = {} # contains Robot objects, one per physical robot, identified by the DeviceId
        self._config_path = config_path

    def get_robot(self, deviceId):
        if deviceId not in self._robots:
            self._robots[deviceId] = Robot(deviceId, self._config_path)
        return self._robots[deviceId]

    def get_robot_list(self):
        l = []
        for a in self._robots:
            l.append(a)
        return l


class Robot(object):
    """ Manages each physical robot """
    def __init__(self, identifier, config_path):

        super().__init__()

        self._persistentData = configparser.ConfigParser()
        self._configFile = os.path.join(config_path, f"data_{identifier}.ini")
        if os.path.exists(self._configFile):
            self._persistentData.read(self._configFile)
        if identifier not in self._persistentData:
            self._persistentData[identifier] = {}

        self._identifier = identifier
        self._connection = None
        self._notecmdValues = {}
        self._notecmdKeys = ['workState','workMode','fan','direction','brush','battery','voice','error','standbyMode',
                             'waterTank','clearComponent','waterMark','version','attract','deviceIp','devicePort',
                             'cleanGoon', 'clearArea','clearTime','clearSign','clearModule','isFinish','chargerPos',
                             'map','track','errorCode','doTime',
                             'appKey','deviceType','authCode','funDefine','nonce_str','version','sign']
        self._defPersistent('water', '0')
        self._defPersistent('fan', '2')
        self._defPersistent('mode', '0')
        self._defPersistent('battery_guard_enabled', '1')
        self._defPersistent('battery_guard_level', '80')
        self._defPersistent('battery_guard_times', '3')
        self._resetStatus()

    def _defPersistent(self, key, value):
        if key not in self._persistentData[self._identifier]:
            self._persistentData[self._identifier][key] = value

    def connected(self, connection):
        if self._connection is not None:
            print("Closing old robot connection and opening a new one")
            self._connection.closedSignal.disconnect(self.disconnected)
            self._connection.close()
        self._connection = connection
        connection.closedSignal.connect(self.disconnected)
        connection.statusUpdate.connect(self.statusUpdate)

    def _resetStatus(self):
        for key in self._notecmdKeys:
            self._notecmdValues[key] = ''
        self._current_workState = -1
        self._battery_changes_counter = 0

    def disconnected(self, name, connection):
        self._connection = None
        self._resetStatus()

    def get_status(self):
        return json.dumps(self._notecmdValues)

    def send_command(self, command, params):
        if self._connection is None:
            return 3, '"Not connected"'

        if command == 'setStatus':
            for key in params:
                if key not in self._notecmdKeys:
                    continue
                self._notecmdValues[key] = params[key]
            return 0, self.get_status()

        if command == 'getStatus':
            return 0, self.get_status()

        if command == 'getProperty':
            if 'key' not in params:
                data = {}
                for key in self._persistentData[self._identifier]:
                    data[key] = self._persistentData[self._identifier][key]
                return 0, json.dumps(data)
            if params['key'] not in self._persistentData[self._identifier]:
                return 8, f'"Key {params["key"]} does not exist in persistent data"'
            return 0, json.dumps({params["key"]: self._persistentData[self._identifier][params["key"]]})

        if command == 'setProperty':
            if 'key' not in params:
                return 6, '"Missing parameter (key)"'
            if 'value' not in params:
                return 6, '"Missing parameter (value)"'
            self._persistentData[self._identifier][params['key']] = str(params['value'])
            with open(self._configFile, 'w') as configfile:
                self._persistentData.write(configfile)
            return 0, '"OK"'

        if command == 'resetBattery':
            self._resetBattery()
            return 0, '"OK"'

        return self._connection.send_command(command, params)


    def statusUpdate(self, signame, sender, status):
        """ Called whenever the status changes """
        if 'value' not in status:
            return
        value = status['value']
        if ('noteCmd' in value) or ('transitCmd' in value):
            for key in value:
                if key not in self._notecmdKeys:
                    continue
                self._notecmdValues[key] = value[key]
        if ('workState' in value) and ('battery' in value):
            state = value['workState']
            if (state != "5") and (state != "6"):
                self._battery_changes_counter = 0
            else:
                if (self._current_workState == "6") and (state == "5"):
                    # changed from "charged" to "charging"
                    try:
                        if int(value['battery']) <= self._getPersistentInteger('battery_guard_level', 80):
                            self._battery_changes_counter += 1
                            if self._battery_changes_counter >= self._getPersistentInteger('battery_guard_times', 3):
                                if self._getPersistentBoolean('battery_guard_enabled', True):
                                    self._resetBattery()
                    except:
                        pass
            self._current_workState = state

    def _getPersistentBoolean(self, key, default_value):
        try:
            return self._persistentData[self._identifier].getboolean(key, default_value)
        except:
            return default_value

    def _getPersistentInteger(self, key, default_value):
        try:
            return self._persistentData[self._identifier].getint(key, default_value)
        except:
            return default_value


    def _resetBattery(self):
        print("Reseting the battery")
        self._battery_changes_counter = 0
        self._connection.send_command('fan', {'speed': '0'})
        self._connection.send_command('watertank', {'speed': '0'})
        self._connection.send_command('clean', {})
        self._connection.send_command('waitState', {'state': 'cleaning'})
        self._connection.send_command('wait', {'seconds': '4'})
        self._connection.send_command('stop', {})
        self._connection.send_command('wait', {'seconds': '1'})
        self._connection.send_command('fan', {'speed': self._persistentData[self._identifier]['fan']})
        self._connection.send_command('watertank', {'speed': self._persistentData[self._identifier]['water']})
        self._connection.send_command('waitState', {'state': 'stopped'})
        self._connection.send_command('return', {})
        self._connection.send_command('waitState', {'state': 'home'})
        self._battery_keeper = 1

    def httpDataUpdate(self, data):
        for key in data:
            if key not in self._notecmdKeys:
                continue
            self._notecmdValues[key] = data[key]

configPath = os.path.join(os.getenv("HOME"), ".config", "congaserver")
try:
    os.makedirs(configPath)
except:
    pass
robot_manager = RobotManager(configPath)
