#!/usr/bin/env python
import os, ConfigParser
import platform

BASE_APP_PATH = '/usr/local/bin/ivigilate/' if platform.system == 'Linux' else ''
LOG_FILE_PATH = '/var/log/ivigilate.log'
HCICONFIG_FILE_PATH = '/usr/sbin/hciconfig'
HCITOOL_FILE_PATH = '/usr/bin/hcitool'


__cfg = None
__cpuinfo = None


def get_cpuinfo():
    hardware = ''
    revision = ''
    cpuserial = '0000000000000000'
    try:
        f = open('/proc/cpuinfo', 'r')
        for line in f:
            if line[0:8] == 'Hardware':
                hardware = line[11:len(line) - 1]
            elif line[0:8] == 'Revision':
                revision = line[11:len(line) - 1]
            if line[0:6] == 'Serial':
                cpuserial = line[10:len(line) - 1]
        f.close()
    except:
        pass

    return (hardware, revision, cpuserial)

def get_detector_uid():
    # not using the 'hardware' info as it references the CPU family which doesn't really mean much...
    return 'FFFFFFFFFFFF' + get('DEVICE', 'revision') + get('DEVICE', 'serial')


def init():
    global __cpuinfo
    __cpuinfo = get_cpuinfo()

    global __cfg
    __cfg = ConfigParser.SafeConfigParser()
    __cfg.readfp(open(BASE_APP_PATH + 'defaults.conf'))  # Load defaults
    __cfg.read(BASE_APP_PATH + 'ivigilate.conf')


def set(section, var, value):
    global __cfg
    if not __cfg:
        init()

    return __cfg.set(section, var, value)


def get(section, var):
    global __cfg
    if not __cfg:
        init()

    if (section == 'DEVICE'):
        if (var == 'hardware'):
            return __cpuinfo[0]
        elif (var == 'revision'):
            return __cpuinfo[1]
        elif (var == 'serial'):
            return __cpuinfo[2]
        elif (var == 'uname'):
            return str(os.uname())

    return __cfg.get(section, var)


def getint(section, var):
    global __cfg
    if not __cfg:
        init()

    if __cfg.has_option(section, var):
        return __cfg.getint(section, var)
    else:
        return 0


def save():
    global __cfg
    if not __cfg:
        init()

    with open(BASE_APP_PATH + 'ivigilate.conf', 'wb') as file:
        __cfg.write(file)

