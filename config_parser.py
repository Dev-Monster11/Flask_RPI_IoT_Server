import configparser
import subprocess
import shutil
import json
import re

import sys

import web_data as wb

config_file = '/usr/cvconf/cvconfig.txt'

class Variable:
    def __init__(self, conf, sect, name, fallback = ''):
        self._sect = sect
        self._conf = conf
        self.name = name
        self._value = self._read_value(fallback)

    def _read_value(self, f):
        return self._conf.get(self._sect, self.name, fallback = f)

    def __len__(self):
        return len(self._value)

    def __getitem__(self, item):
         return self._value[item]
    
    def lower(self):
        return self._value.lower()

    def upper(self):
        return self._value.upper()
        
    def count(self, a):
        return self._value.count(a)

    def split(self, a):
        return self._value.split(a)
    
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        #self._value = value
        self._value = self._store_value(value)

    def _store_value(self, value):
        self._conf.set(self._sect, self.name, self._value)
        return value
        
class BooleanVariable(Variable):
    def _read_value(self, f):
        if self._sect not in self._conf:
            return False
        rec = self._conf[self._sect]
        attr = rec.get(self.name, None)
        return attr is not None and attr.lower() == "yes"

    def _store_value(self, value):
        if not isinstance(value, bool):
            raise TypeError(value)
        
        #print ("Value: %s" % (value), "Type:", type(value), file=sys.stderr)
        r = value if value is not None else False
        self._conf.set(self._sect, self.name, "Yes" if r else "No")
        #print ("Set:", self.name, "type", type(r), file=sys.stderr)
        return r
        
    def __len__(self):
        #print ("Var:", self.name, "type", type(self._value), file=sys.stderr)
        return self._value

class ArrayVariable(Variable):
    
    def _read_value(self, f):
        arr = []
        reg_rs = re.compile(self.name)
        section = self._conf[self._sect]
        for rq in section:
            if reg_rs.match(rq):
                item = section.get(rq)
                if len(item) > 0:
                    arr.append(item)
        return arr

    def _store_value(self, value):
        #print ("Name:", self.name, "Value: %s" % (value), "Type:", type(value), file=sys.stderr)
        if not isinstance(value, list):
            raise TypeError(value)
        
        name = self.name.replace("\d+", "")
        for (i, val) in enumerate(value):
            #print ("ArrayStore", name, "=", val)
            self._conf.set(self._sect, "%s%s" % (name, i), val)

        return value

class MultiArrayVariable(Variable):
    
    def _read_value(self, f):
        arr = {}
        rs = re.compile(self.name)
        section = self._conf[self._sect]
        name = ""
        for rq in section:
             m = rs.match(rq)
             if m:
                 i = m.group(1)
                 z = m.group(2)
                 item = section.get(rq)
                 if len(item) > 0:
                     if i in arr:
                         arr[i].update({z:item})
                     else:
                         arr[i] = {z:item}

        return arr

    def _store_value(self, value):
        if not isinstance(value, dict):
            raise TypeError(value)
        
        #print ("Name:", self.name, "Value: %s" % (value), "Type:", type(value), file=sys.stderr)
        m = re.compile("\(\\\\d\+\)")
        base_name = self.name.replace("\.", ".")
        name = ""
        for i, val in value.items():
            for z, par in val.items():
                #print ("Self.name:", name, "I", i, "Z", z, file=sys.stderr)
                name = m.sub(i, base_name,  1)
                name = m.sub(z, name, 1)
                #print ("MultiStore", name, "=", par, file=sys.stderr)
                self._conf.set(self._sect, name, par)

        return value

class VarArrayVariable(Variable):
    def _read_value(self, f):
        arr = {}
        rs = re.compile(self.name)
        section = self._conf[self._sect]
        name = ""
        for rq in section:
             m = rs.match(rq)
             if m:
                 i = m.group(1)
                 z = m.group(2)
                 y = m.group(3)
                 #print ("Get value for: ", rq, file=sys.stderr)
                 item = section.get(rq)
                 #print ("Value is: ", item, file=sys.stderr)
                 if item is not None and len(item) > 0:
                     if i in arr:
                         arr[i].update({"P%s_RS485Record%s" % (z, y) : item})
                     else:
                         arr[i] = {"P%s_RS485Record%s" % (z, y):item}

        #print ("Name:", self.name, "Set: %s" % (arr), file=sys.stderr)
        return arr

    def _store_value(self, value):
        if not isinstance(value, dict):
            raise TypeError(value)
        
        #print ("Name:", self.name, "Value: %s" % (value), "Type:", type(value), file=sys.stderr)
        m = re.compile("\(\\\\d\+\)")
        base_name = self.name.split('_')[0].replace("\*", "*")
        name = ""

        for i, val in value.items():
            for z, par in val.items():
                name = m.sub(i, base_name,  1)
                self._conf.set(self._sect, "%s_%s" %(name, z), par)


        return value

#AlarmAtSiteName = __attribute_exists(alarm_rec, "@SiteName")
#AlarmAtSiteID = __attribute_exists(alarm_rec, "@SiteID")

class ReferenceVariable(Variable):
    def _read_value(self, f):
        if self._sect not in self._conf:
            return False
        
        rec = self._conf[self._sect]
        return self.name in rec

    def _store_value(self, value):
        if not isinstance(value, bool):
            raise TypeError(value)

        r = value if value is not None else False
        if r:
            self._conf[self._sect][self.name] = None
        else:
            self._conf.remove_option(self._sect, self.name)
  
        return r
        
    def __len__(self):
        #print ("Var:", self.name, "type", type(self._value), file=sys.stderr)
        return self._value
    
    def getref(self):
        current_module = sys.modules[__name__]
        var_name = self.name[1:] if f is None or len(f) == 0 else f
        return getattr(current_module, var_name, None)
 
    
#En0WANIP = ""

EmailNotificationEn = False
EmailTo  = ""
EmailCC  = ""
EmailFrom= ""
EmailSubject= ""
EmailMsgHeader= ""
EmailMsgTrailer= ""
EmailFormat=""

smtpRoot= ""
smtpMailhub=""
smtpRewriteDomain = ""
smtpHostname = ""
smtpFromLineOverride = ""
smtpTLSCert = ""
smtpTLSKey = ""
smtpTLS_CA_File = ""
snmpTLS_CA_Dir = ""
smtpAuthMethod = ""

smtpOutgoingServer= ""
smtpAuthUser= ""
smtpAuthPass= ""
smtpUseTLS = False
smtpUseSTARTTLS = False

httpPostNotificationEn = True
httpPostURL = []

RsyslogNotificationEn = True
RsyslogServer = []

SNMPNotificationEn  = False
snmpManagerIP       = []
snmpNotificationType= []
snmpv12Community    = []
snmpv3TrapEngineID  = []
snmpv3InfEngineID   = []
snmpv3SecurityName  = []
snmpv3AuthProtocol  = []
snmpv3AuthKey       = []
snmpv3SecurityLevel = []
snmpv3PrivProtocol  = []
snmpv3PrivKey       = []

SiteContactEmail = ""
SiteContactEmailDef="OurContact@OurDomain.com"
SiteName = ""
SiteID = ""
SiteRemarks= ""
SiteCoordinates= ""
SiteCoordinatesDef="43.64274, -79.38705"
SiteAddress = ""

HWRev = ""
SWRev = ""
SN = ""

InputsAppEnable = False
InputMasks = ''
InputPollInterval = ''
InputsRawFileSize = ''
InputsScript = ''
InputName = []
InputCondition = []

OutputsAppEnable = False
OutputMasks = ''
OutputPollInterval = ''
OutputsRawFileSize = ''
OutputName = []
OutputDefault = ""

AnalogsAppEnable = False
AnalogMasks = ""
AnalogPollInterval = ""
AnalogsRawFileSize = ""
AnalogsAlarmFileSize = ""
AnalogsScript = ""
AnalogName = []
AnalogCalOffset = ""
AnalogConverter = []
AnalogCondition = []

SerialsAppEnable = False
SerialMasks = "" 
SerialAlarmFileSize = ""
SerialScript = ""
SerialName = []
SerialMode = []
SerialPortSetting = []
SerialSSHPort = []
Serial2IP = []
IP2Serial = []
SerialRawFileSize = []
SerialScript = []
Condition = []

RS485AppEnable = False
RS485PollInterval = ""
RS485AlarmFileSize= ""
RS485Script = ""
P0_DeviceID = []
P1_DeviceID = []
P0_RS485DeviceName = []
P1_RS485DeviceName = []
P0_Protocol = []
P1_Protocol = []
P0_PortSetting = []
P1_PortSetting = []
P0_RS485RawFileSize = []
P1_RS485RawFileSize = []
P0_RS485Condition = {}
P1_RS485Condition = {}
P0_RS485Script = []
P1_RS485Script = []
P0_ReadData = []
P1_ReadData = []
P0_RS485Record = []
P1_RS485Record = []
Var = []
P0_RS485RecordDescription = []
P1_RS485RecordDescription = []

OneWireAppEnable = False
OneWireDeviceID = []
OneWirePollInterval = ""
OneWireAlarmFileSize = ""
OneWireScript = ""
OneWireDeviceName = []
OneWireUoM = []
OneWireRawFileSize = []
OneWireCondition = {}
OneWireScripts = []

NetAppEnable = False
NetApp = []
NetAppScript = ""
#Name = []
#Mode = []
#Interface = []
#Protocol = []
#Port = []
NetAppRawFileSize = []
NetAppScripts = []
NetAppCondition = {}

SNMPTrapAppMode = ""
SNMPTrapAppReceiverPort = ""
SNMPTrapAppRawFileSize = ""
SNMPTrapAppAlarmFileSize = ""
SNMPAppCondition = []

SyslogAppMode = ""
SyslogAppRawFileSize  = ""
SyslogAppAlarmFileSize = ""
SyslogAppLogEnable = ""
SyslogAppCondition = []

FirewallAppEnable = False
FirewallAdminIP = []

Access2FATimer = ""
Access2FAEnable = False
Access2FAGoogleEnable = False
AccessPWComplexityEnable = False
AccessPWLifetimeEnable = False

NTPServer = ""
TimeZone = ""
TimeAuto = ""
DSTAuto = ""
EthernetMasks=""
Eth0WANIP=""
Eth0WANNetMask=""
Eth1LANIP=""
Eth1LANNetMask=""
GatewayIP=""
DNS=""

FilePushOption=""
FilePushInterval=""
FilePushInputs=""
FilePushOutputs=""
FilePushAnalogs=""
FilePush1Wire=""
FilePushRS485=""
FilePushRS232=""
FilePushNet=""
FilePushAlarms=""
DestinationServerIP=""
DestinationServerPath=""
DestinationServerUserID=""
DestinationServerUserPW=""

SNMPAgentEnable=None
SNMPDSysLocation=""
SNMPDSysContact=""
SNMPDSysName=""
SNMPDSysDescription=""
SNMPDSysObjectID=""

SNMPDv12Community=""
SNMPDv3EngineID=""

SNMPDv3SecurityName0=""
SNMPDv3AuthProtocol0=""
SNMPDv3AuthKey0=""
SNMPDv3PrivProtocol0=""
SNMPDv3PrivKey0=""

SNMPDv3SecurityName1=""
SNMPDv3AuthProtocol1=""
SNMPDv3AuthKey1=""
SNMPDv3PrivProtocol1=""
SNMPDv3PrivKey1=""

SNMPDv3SecurityName2=""
SNMPDv3AuthProtocol2=""
SNMPDv3AuthKey2=""
SNMPDv3PrivProtocol2=""
SNMPDv3PrivKey2=""

SysHeartbeatReportInterval=""
Eth0LinkRestartInterval=""
Eth1LinkRestartInterval=""
DataBackupSchedule=""
SoftRestartSchedule=""
SystemRebootSchedule=""
SystemSupervisorScript=""

AlarmAtSiteName = False
AlarmAtSiteID = False
AlarmAtSiteIP = False
AlarmAtSiteCoordinates = False
AlarmAtSiteAddress = False
AlarmAtSiteRemarks = False
AlarmAtAlarmDate = False
AlarmAtAlarmTime = False
AlarmAtAlarmInterface = False
AlarmAtAlarmSource = False
AlarmAtAlarmValue = False
AlarmAtAlarmName = False
AlarmAtAlarmDescription = False

#BaseAlarm = av.AlarmRecord()

def __bool_attribute__(rec, name, expected):
    attr = rec.get(name, None)
    return attr is not None and attr.lower() == expected.lower()

def __attribute_exists(rec, name):
    return name in rec

def __int_attribute__(rec, expected):
    return  int(rec.attrib[name])

def __get_array__(regexp_str, section):
    arr = []
    reg_rs = re.compile(regexp_str)
    for rq in section:
        if reg_rs.match(rq):
            item = section.get(rq)
            if len(item) > 0:
                arr.append(item)

    return arr

# ::IMPLEMENT ME::
def __get_multi_array__(regexp, section):
    arr = {}
    rs = re.compile(regexp)
    
    for rq in section:
        m = rs.match(rq)
        if m:
            i = m.group(1)
            z = m.group(2)
            item = section.get(rq)
            if len(item) > 0:
                if i in arr:
                    arr[i].update({z:item})
                else:
                    arr[i] = {z:item}

    return arr


def __parse_email_rec(config):
    global EmailNotificationEn
    global EmailTo
    global EmailCC
    global EmailFrom
    global EmailSubject
    global EmailMsgHeader
    global EmailMsgTrailer
    global EmailFormat
    global smtpOutgoingServer
    global smtpAuthUser
    global smtpAuthPass
    global smtpUseTLS
    global smtpUseSTARTTLS
    global SiteContactEmail

    global smtpRoot
    global smtpMailhub
    global smtpRewriteDomain
    global smtpHostname
    global smtpFromLineOverride
    global smtpTLSCert
    global smtpTLSKey
    global smtpTLS_CA_File
    global snmpTLS_CA_Dir
    global smtpAuthMethod
    
    if not config.has_section('Email'):
        print ("'Email' section is missed", file=sys.stderr)
        return


    if len(SiteContactEmail) == 0:
        SiteContactEmail = Variable(config, 'Site', 'SiteContactEmail', fallback = '')
        if len(SiteContactEmail) == 0:
            SiteContactEmail.value = SiteContactEmailDef
    
    mail_rec = config['Email']

    EmailNotificationEn = BooleanVariable(config, 'Email', 'EmailNotificationEnable', 'Yes')
    EmailTo  = Variable(config, 'Email', 'EmailTo', '')
    EmailCC   = Variable(config, 'Email', 'EmailCC', '')
    EmailFrom  = Variable(config, 'Email', 'EmailFrom', '')
    EmailSubject  = Variable(config, 'Email', 'EmailSubject', '')
    
    EmailMsgHeader = Variable(config, 'Email', 'EmailMsgHeader', '')
    EmailMsgTrailer = Variable(config, 'Email', 'EmailMsgTrailer', '')

    EmailFormat = Variable(config, 'Email', 'EmailFormat', '')
    
    smtpOutgoingServer = Variable(config, 'Email',  'smtpOutgoingServer', '')
    smtpAuthUser = Variable(config, 'Email', 'smtpAuthUser', '')
    smtpAuthPass = Variable(config, 'Email', 'smtpAuthPass', '')
    smtpUseTLS = BooleanVariable(config, 'Email', 'smtpUseTLS', 'Yes')
    smtpUseSTARTTLS = BooleanVariable(config, 'Email', 'smtpUseSTARTTLS', 'Yes')

    smtpRoot= Variable(config, 'Email', 'smtpRoot', '')
    smtpMailhub= Variable(config, 'Email', 'smtpMailhub', '')
    smtpRewriteDomain = Variable(config, 'Email', 'smtpRewriteDomain', '')
    smtpHostname = Variable(config, 'Email', 'smtpHostname', '')
    smtpFromLineOverride = Variable(config, 'Email', 'smtpFromLineOverride', '')
    smtpTLSCert = Variable(config, 'Email', 'smtpTLSCert', '')
    smtpTLSKey = Variable(config, 'Email', 'smtpTLSKey', '')
    smtpTLS_CA_File = Variable(config, 'Email', 'smtpTLS_CA_File', '')
    snmpTLS_CA_Dir = Variable(config, 'Email', 'snmpTLS_CA_Dir', '')
    smtpAuthMethod = Variable(config, 'Email', 'smtpAuthMethod', '')
    
def __parse_http_rec(config):
    global httpPostNotificationEn
    global httpPostURL

    if not config.has_section('httpPost'):
        print ("'httpPost' section is missed", file=sys.stderr)
        return

    http_rec = config['httpPost']

    httpPostNotificationEn = BooleanVariable(config, 'httpPost', 'httpPostNotificationEnable', 'Yes')

    httpPostURL = ArrayVariable( config, 'httpPost', "httpPostURL\d+")

def __parse_snmpagent_rec(config):
    global SNMPAgentEnable
    global SNMPDSysLocation, SNMPDSysContact
    global SNMPDSysName, SNMPDSysDescription, SNMPDSysObjectID
    global SNMPDv12Community, SNMPDv3EngineID

    global SNMPDv3SecurityName0, SNMPDv3AuthProtocol0, SNMPDv3AuthKey0
    global SNMPDv3PrivProtocol0, SNMPDv3PrivKey0

    global SNMPDv3SecurityName1, SNMPDv3AuthProtocol1, SNMPDv3AuthKey1
    global SNMPDv3PrivProtocol1, SNMPDv3PrivKey1

    global SNMPDv3SecurityName2, SNMPDv3AuthProtocol2, SNMPDv3AuthKey2
    global SNMPDv3PrivProtocol2, SNMPDv3PrivKey2


    SNMPAgentEnable = BooleanVariable(config, 'SNMPAgent', 'SNMPAgentEnable', 'Yes')

    if not config.has_section('SNMPAgent'):
        print ("'SNMPAgent' section is missed", file=sys.stderr)
        return

    
    SNMPDSysLocation = Variable(config, 'SNMPAgent', "SNMPDSysLocation", fallback = '')
    SNMPDSysContact = Variable(config, 'SNMPAgent', "SNMPDSysContact", fallback = '')
    SNMPDSysName = Variable(config, 'SNMPAgent', "SNMPDSysName", fallback = '')
    SNMPDSysDescription = Variable(config, 'SNMPAgent', "SNMPDSysDescription", fallback = '')
    SNMPDSysObjectID = Variable(config, 'SNMPAgent', "SNMPDSysObjectID", fallback = '')
    SNMPDv12Community = Variable(config, 'SNMPAgent', "SNMPDv12Community", fallback = '')
    SNMPDv3EngineID = Variable(config, 'SNMPAgent', "SNMPDv3EngineID", fallback = '')
    SNMPDv3SecurityName0 = Variable(config, 'SNMPAgent', "SNMPDv3SecurityName0", fallback = '')
    SNMPDv3AuthProtocol0 = Variable(config, 'SNMPAgent', "SNMPDv3AuthProtocol0", fallback = '')
    SNMPDv3AuthKey0 = Variable(config, 'SNMPAgent', "SNMPDv3AuthKey0", fallback = '')
    SNMPDv3PrivProtocol0 = Variable(config, 'SNMPAgent', "SNMPDv3PrivProtocol0", fallback = '')
    SNMPDv3PrivKey0 = Variable(config, 'SNMPAgent', "SNMPDv3PrivKey0", fallback = '')

    SNMPDv3SecurityName1 = Variable(config, 'SNMPAgent', "SNMPDv3SecurityName1", fallback = '')
    SNMPDv3AuthProtocol1 = Variable(config, 'SNMPAgent', "SNMPDv3AuthProtocol1", fallback = '')
    SNMPDv3AuthKey1 = Variable(config, 'SNMPAgent', "SNMPDv3AuthKey1", fallback = '')
    SNMPDv3PrivProtocol1 = Variable(config, 'SNMPAgent', "SNMPDv3PrivProtocol1", fallback = '')
    SNMPDv3PrivKey1 = Variable(config, 'SNMPAgent', "SNMPDv3PrivKey1", fallback = '')

    SNMPDv3SecurityName2 = Variable(config, 'SNMPAgent', "SNMPDv3SecurityName2", fallback = '')
    SNMPDv3AuthProtocol2 = Variable(config, 'SNMPAgent', "SNMPDv3AuthProtocol2", fallback = '')
    SNMPDv3AuthKey2 = Variable(config, 'SNMPAgent', "SNMPDv3AuthKey2", fallback = '')
    SNMPDv3PrivProtocol2 = Variable(config, 'SNMPAgent', "SNMPDv3PrivProtocol2", fallback = '')
    SNMPDv3PrivKey2 = Variable(config, 'SNMPAgent', "SNMPDv3PrivKey2", fallback = '')

def __parse_supervisor_rec(config):
    global SysHeartbeatReportInterval, Eth0LinkRestartInterval, Eth1LinkRestartInterval
    global DataBackupSchedule, SoftRestartSchedule, SystemRebootSchedule, SystemSupervisorScript

    if not config.has_section('Supervisor'):
        print ("'Supervisor' section is missed", file=sys.stderr)
        return

    SysHeartbeatReportInterval = Variable(config, 'Supervisor', "SysHeartbeatReportInterval", fallback = '')
    Eth0LinkRestartInterval = Variable(config, 'Supervisor', "Eth0LinkRestartInterval", fallback = '')
    Eth1LinkRestartInterval = Variable(config, 'Supervisor', "Eth1LinkRestartInterval", fallback = '')
    DataBackupSchedule = Variable(config, 'Supervisor', "DataBackupSchedule", fallback = '')
    SoftRestartSchedule = Variable(config, 'Supervisor', "SoftRestartSchedule", fallback = '')
    SystemRebootSchedule = Variable(config, 'Supervisor', "SystemRebootSchedule", fallback = '')
    SystemSupervisorScript = Variable(config, 'Supervisor', "SystemSupervisorScript", fallback = '')
            
def __parse_sysaccess_rec(config):
    global Access2FAEnable, Access2FAGoogleEnable, Access2FATimer
    global AccessPWComplexityEnable, AccessPWLifetimeEnable
    
    if not config.has_section('SysAccess'):
        print ("'SysAccess' section is missed", file=sys.stderr)
        return

    sysaccess_rec = config['SysAccess']

    Access2FATimer = Variable(config, 'SysAccess', "Access2FATimer", fallback = '')
    Access2FAEnable = BooleanVariable(config, 'SysAccess', 'Access2FAEnable', 'Yes')
    Access2FAGoogleEnable = BooleanVariable(config, 'SysAccess', 'Access2FAGoogleEnable', 'Yes')
    AccessPWComplexityEnable= BooleanVariable(config, 'SysAccess', 'AccessPWComplexityEnable', 'Yes')
    AccessPWLifetimeEnable  = BooleanVariable(config, 'SysAccess', 'AccessPWLifetimeEnable', 'Yes')
    
def __parse_snmp_rec(config):
    global SNMPNotificationEn
    global snmpManagerIP
    global snmpNotificationType
    global snmpv12Community
    global snmpv3TrapEngineID
    global snmpv3InfEngineID
    global snmpv3SecurityName
    global snmpv3AuthProtocol
    global snmpv3AuthKey
    global snmpv3SecurityLevel
    global snmpv3PrivProtocol
    global snmpv3PrivKey
    #global En0WANIP
    
    if not config.has_section('SNMP'):
        print ("'SNMP' section is missed", file=sys.stderr)
        return

    #if En0WANIP is None or len(En0WANIP) == 0:
    #    if not config.has_section('Networking'):
    #        print ("'Networking' section is missed", file=sys.stderr)
    #        return
    #
    #    En0WANIP = Variable(config, 'Networking', "En0WANIP", fallback = '')
    
    snmp_rec = config['SNMP']

    SNMPNotificationEn = BooleanVariable(config, 'SNMP', 'SNMPNotificationEnable', 'Yes')

    snmpManagerIP = ArrayVariable(config, 'SNMP', "snmpManagerIP\d+")
    snmpNotificationType = ArrayVariable(config, 'SNMP',"snmpNotificationType\d+")
    snmpv12Community    = ArrayVariable(config, 'SNMP',"snmpv12Community\d+")
    snmpv3TrapEngineID  = ArrayVariable(config, 'SNMP',"snmpv3TrapEngineID\d+")
    snmpv3InfEngineID   = ArrayVariable(config, 'SNMP',"snmpv3InfEngineID\d+")
    snmpv3SecurityName  = ArrayVariable(config, 'SNMP',"snmpv3SecurityName\d+")
    snmpv3AuthProtocol  = ArrayVariable(config, 'SNMP',"snmpv3AuthProtocol\d+")
    snmpv3AuthKey       = ArrayVariable(config, 'SNMP',"snmpv3AuthKey\d+")
    snmpv3SecurityLevel = ArrayVariable(config, 'SNMP',"snmpv3SecurityLevel\d+")
    snmpv3PrivProtocol  = ArrayVariable(config, 'SNMP',"snmpv3PrivProtocol\d+")
    snmpv3PrivKey       = ArrayVariable(config, 'SNMP',"snmpv3PrivKey\d+")

def __parse_firewall_rec(config):
    global FirewallAppEnable, FirewallAdminIP
    
    if not config.has_section('Firewall'):
        print ("'Firewall' section is missed", file=sys.stderr)
        return

    firewall_rec = config['Firewall']

    FirewallAppEnable = BooleanVariable(config, 'Firewall', 'FirewallAppEnable', 'Yes')
    FirewallAdminIP   = ArrayVariable(config, 'Firewall', "FirewallAdminIP\d+")

            
def __parse_syslog_rec(config):
    global RsyslogNotificationEn
    global RsyslogServer

    if not config.has_section('Rsyslog'):
        print ("'Rsyslog' section is missed", file=sys.stderr)
        return

    syslog_rec = config['Rsyslog']

    RsyslogNotificationEn= BooleanVariable(config, 'Rsyslog', 'RsyslogNotificationEnable', 'Yes')
    RsyslogServer = ArrayVariable(config, 'Rsyslog', "RsyslogServer\d+")


def __parse_rs485_rec(config):
    global RS485AppEnable
    global P0_DeviceID, P1_DeviceID
    global RS485PollInterval, RS485AlarmFileSize, RS485Script
    global P0_RS485DeviceName, P1_RS485DeviceName
    global P0_Protocol, P1_Protocol
    global P0_PortSetting, P1_PortSetting
    global P0_RS485RawFileSize, P1_RS485RawFileSize
    global P0_RS485Script, P1_RS485Script
    global P0_ReadData, P1_ReadData
    global P0_RS485Record, P1_RS485Record
    global Var
    global P0_RS485RecordDescription, P1_RS485RecordDescription
    global P0_RS485Condition, P1_RS485Condition
    
    if not config.has_section('RS485'):
        print ("'RS485' section is missed", file=sys.stderr)
        return

    rs_rec = config['RS485']

    RS485AppEnable = BooleanVariable(config, 'RS485', 'RS485AppEnable', 'Yes')
    RS485PollInterval =  Variable(config, 'RS485', 'RS485PollInterval', fallback = '')
    RS485AlarmFileSize = Variable(config, 'RS485', 'RS485AlarmFileSize', fallback = '')
    RS485Script = Variable(config, 'RS485', 'RS485Script', fallback = '')

    P0_RS485DeviceName = ArrayVariable(config, "RS485", "P0_RS485DeviceName\d+")
    P1_RS485DeviceName = ArrayVariable(config, "RS485","P1_RS485DeviceName\d+")
    P0_Protocol = ArrayVariable(config, "RS485","P0_Protocol\d+")
    P1_Protocol = ArrayVariable(config, "RS485","P1_Protocol\d+")
    P0_PortSetting = ArrayVariable(config, "RS485","P0_PortSetting\d+")
    P1_PortSetting = ArrayVariable(config, "RS485","P1_PortSetting\d+")
    P0_RS485RawFileSize = ArrayVariable(config, "RS485","P0_RS485RawFileSize\d+")
    P1_RS485RawFileSize = ArrayVariable(config, "RS485","P1_RS485RawFileSize\d+")
    P0_RS485Script = ArrayVariable(config, "RS485","P0_RS485Script\d+")
    P1_RS485Script = ArrayVariable(config, "RS485","P1_RS485Script\d+")

    P0_DeviceID = ArrayVariable(config, "RS485","P0_DeviceID\d+")
    P1_DeviceID = ArrayVariable(config, "RS485","P1_DeviceID\d+")
    P0_ReadData = ArrayVariable(config, "RS485","P0_ReadData\d+")
    P1_ReadData = ArrayVariable(config, "RS485","P1_ReadData\d+")
    P0_RS485Record = ArrayVariable(config, "RS485","P0_RS485Record\d+")
    P1_RS485Record = ArrayVariable(config, "RS485","P1_RS485Record\d+")
    Var = VarArrayVariable(config, "RS485","\*Var(\d+)_P(\d+)_RS485Record(\d+)")

    P0_RS485RecordDescription = ArrayVariable(config, "RS485","P0_RS485RecordDescription\d+")
    P1_RS485RecordDescription = ArrayVariable(config, "RS485","P1_RS485RecordDescription\d+")

    P0_RS485Condition = MultiArrayVariable(config, "RS485", "P0_RS485Condition(\d+)\.(\d+)")
    P1_RS485Condition = MultiArrayVariable(config, "RS485", "P1_RS485Condition(\d+)\.(\d+)")

def __parse_onewire_rec(config):
    global OneWireAppEnable
    global OneWireDeviceID
    global OneWirePollInterval, OneWireAlarmFileSize, OneWireScript
    global OneWireDeviceName
    global OneWireUoM
    global OneWireRawFileSize
    global OneWireCondition
    global OneWireScript
    global OneWireScripts

    if not config.has_section('1Wire'):
        print ("'1Wire' section is missed", file=sys.stderr)
        return

    one_rec = config['1Wire']

    OneWireAppEnable = BooleanVariable(config, '1Wire', '1WireAppEnable', 'Yes')
    OneWirePollInterval = Variable(config, '1Wire', '1WirePollInterval', fallback = '')
    OneWireAlarmFileSize = Variable(config, '1Wire', '1WireAlarmFileSize', fallback = '')
    OneWireScript = Variable(config, '1Wire', '1WireScript', fallback = '')
    OneWireDeviceName = ArrayVariable(config, "1Wire","1WireDeviceName\d+")
    OneWireUoM = ArrayVariable(config, "1Wire","1WireUoM\d+")
    OneWireRawFileSize= ArrayVariable(config, "1Wire","1WireRawFileSize\d+")
    OneWireCondition = MultiArrayVariable(config, "1Wire", "1WireCondition(\d+)\.(\d+)")
    OneWireScripts = ArrayVariable(config, "1Wire","1WireScript\d+")

    OneWireDeviceID = ArrayVariable(config, "1Wire","1WireDeviceID\d+")


def __parse_netapp_rec(config):
    global NetAppEnable
    global NetApp, NetAppScript
    #global Name, Mode,
    global NetAppRawFileSize
    global NetAppScripts, NetAppCondition
    global SNMPAppCondition
    global SNMPTrapAppMode, SNMPTrapAppReceiverPort, SNMPTrapAppRawFileSize, SNMPTrapAppAlarmFileSize
    global SyslogAppMode, SyslogAppRawFileSize, SyslogAppAlarmFileSize, SyslogAppLogEnable
    global SyslogAppCondition
    #global Interface, Protocol, Port
    
    if not config.has_section('NetApp'):
        print ("'NetApp' section is missed", file=sys.stderr)
        return

    one_rec = config['NetApp']

    NetAppEnable = BooleanVariable(config, 'NetApp', 'NetAppEnable', 'Yes')
    NetAppScript = Variable(config, 'NetApp', 'NetAppScript', fallback = '')

    #Name = ArrayVariable(config, "NetApp","Name\d+")
    #Mode  = ArrayVariable(config, "NetApp","Mode\d+")
    #Interface = ArrayVariable(config, "NetApp","Interface\d+")
    #Protocol = ArrayVariable(config, "NetApp","Protocol\d+")
    #Port = ArrayVariable(config, "NetApp","Port\d+")
    NetAppRawFileSize = ArrayVariable(config, "NetApp","NetAppRawFileSize\d+")
    NetAppScripts = ArrayVariable(config, "NetApp","NetAppScript\d+")
    NetApp = ArrayVariable(config, "NetApp","NetApp\d+")
    NetAppCondition = MultiArrayVariable(config, "NetApp", "NetAppCondition(\d+).(\d+)")
    
    SNMPTrapAppMode = Variable(config, 'NetApp', 'SNMPTrapAppMode', fallback = '')
    SNMPTrapAppReceiverPort = Variable(config, 'NetApp', 'SNMPTrapAppReceiverPort', fallback = '')
    SNMPTrapAppRawFileSize = Variable(config, 'NetApp', 'SNMPTrapAppRawFileSize', fallback = '')
    SNMPTrapAppAlarmFileSize = Variable(config, 'NetApp', 'SNMPTrapAppAlarmFileSize', fallback = '')
    SNMPAppCondition = ArrayVariable(config, "NetApp","SNMPAppCondition\d+")
    SyslogAppMode = Variable(config, 'NetApp', 'SyslogAppMode', fallback = '')
    SyslogAppRawFileSize = Variable(config, 'NetApp', 'SyslogAppRawFileSize', fallback = '')
    SyslogAppAlarmFileSize = Variable(config, 'NetApp', 'SyslogAppAlarmFileSize', fallback = '')
    SyslogAppLogEnable = BooleanVariable(config, 'NetApp', 'SyslogAppLogEnable', 'Yes')
    SyslogAppCondition = ArrayVariable(config, "NetApp","SyslogAppCondition\d+")

    
def __parse_device_rec(config):
    global HWRev
    global SWRev
    global SN

    if not config.has_section('Device'):
        print ("'Device' section is missed", file=sys.stderr)
        return
    
    HWRev = Variable(config, 'Device', 'HWRev', fallback = '')
    SWRev = Variable(config, 'Device', 'SWRev', fallback = '')
    SN = Variable(config, 'Device', 'SN', fallback = '')

def __parse_inputs_rec(config):
    global InputsAppEnable
    global InputMasks
    global InputPollInterval, InputsRawFileSize, InputsScript
    global InputName
    global InputCondition

    if not config.has_section('Inputs'):
        print ("'Inputs' section is missed", file=sys.stderr)
        return
    
    InputsAppEnable = BooleanVariable(config, 'Inputs', 'InputsAppEnable', 'Yes')
    InputMasks = Variable(config, 'Inputs', 'InputMasks', fallback = '')
    InputPollInterval = Variable(config, 'Inputs', 'InputPollInterval', fallback = '')
    InputsRawFileSize = Variable(config, 'Inputs', 'InputsRawFileSize', fallback = '')
    InputsScript = Variable(config, 'Inputs', 'InputsScript', fallback = '')
    InputName = ArrayVariable(config, "Inputs","InputName\d+")
    InputCondition = ArrayVariable(config, "Inputs","InputCondition\d+")
    
def __parse_outputs_rec(config):
    global OutputsAppEnable
    global OutputMasks
    global OutputPollInterval, OutputsRawFileSize, OutputName
    global OutputDefault

    if not config.has_section('Outputs'):
        print ("'Outputs' section is missed", file=sys.stderr)
        return

    OutputsAppEnable = BooleanVariable(config, 'Outputs', 'OutputAppEnable', 'Yes')
    OutputMasks = Variable(config, 'Outputs', 'OutputMasks', fallback = '')
    OutputPollInterval = Variable(config, 'Outputs', 'OutputPollInterval', fallback = '')
    OutputsRawFileSize = Variable(config, 'Outputs', 'OutputsRawFileSize', fallback = '')
    OutputName = ArrayVariable(config, 'Outputs', "OutputName\d+")
    OutputDefault = Variable(config, 'Outputs', 'OutputDefault', fallback = '')

def __parse_analogs_rec(config):
    global AnalogsAppEnable
    global AnalogMasks
    global AnalogPollInterval, AnalogsRawFileSize, AnalogsAlarmFileSize, AnalogsScript
    global AnalogName
    global AnalogCalOffset
    global AnalogConverter
    global AnalogCondition
    
    if not config.has_section('Analogs'):
        print ("'Analogs' section is missed", file=sys.stderr)
        return

    AnalogsAppEnable = BooleanVariable(config, 'Analogs', 'AnalogsAppEnable', 'Yes')
    AnalogMasks = Variable(config, 'Analogs', 'AnalogMasks', fallback = '')
    AnalogPollInterval  = Variable(config, 'Analogs', 'AnalogPollInterval', fallback = '')
    AnalogsRawFileSize  = Variable(config, 'Analogs', 'AnalogsRawFileSize', fallback = '')
    AnalogsAlarmFileSize= Variable(config, 'Analogs', 'AnalogsAlarmFileSize', fallback = '')
    AnalogsScript = Variable(config, 'Analogs', 'AnalogsScript', fallback = '')
    AnalogName = ArrayVariable(config, "Analogs","AnalogName\d+")
    AnalogConverter = ArrayVariable(config, "Analogs","AnalogConverter\d+")
    AnalogCondition = ArrayVariable(config, "Analogs","AnalogCondition\d+")
    AnalogCalOffset = Variable(config, 'Analogs', 'AnalogCalOffset', fallback = '')


def __parse_rs232_rec(config):
    global SerialsAppEnable, SerialAlarmFileSize, SerialScript
    global SerialMasks 
    global SerialName, SerialMode, SerialPortSetting, SerialSSHPort, Serial2IP
    global IP2Serial, SerialRawFileSize, SerialScript
    global Condition
    
    if not config.has_section('RS232'):
        print ("'RS232' section is missed", file=sys.stderr)
        return

    SerialsAppEnable = BooleanVariable(config, 'RS232', 'SerialAppEnable', 'Yes')
    SerialAlarmFileSize = Variable(config, 'RS232', 'SerialAlarmFileSize', fallback = '')
    SerialScript = Variable(config, 'RS232', 'SerialScript', fallback = '')
    SerialMasks = Variable(config, 'RS232', 'SerialMasks', fallback = '')
    SerialName = ArrayVariable(config, "RS232","SerialName\d+")
    SerialMode = ArrayVariable(config, "RS232","SerialMode\d+")
    SerialPortSetting = ArrayVariable(config, "RS232","SerialPortSetting\d+")
    SerialSSHPort = ArrayVariable(config, "RS232","SerialSSHPort\d+")
    Serial2IP = ArrayVariable(config, "RS232","Serial2IP\d+")
    IP2Serial = ArrayVariable(config, "RS232","IP2Serial\d+")
    SerialRawFileSize = ArrayVariable(config, "RS232","SerialRawFileSize\d+")
    SerialScript = ArrayVariable(config, "RS232","SerialScript\d+")
    Condition = MultiArrayVariable(config, "RS232", "Condition(\d+)\.(\d+)")

def __parse_site_rec(config):
    global SiteContactEmail
    global SiteName
    global SiteID
    global SiteAddress
    global SiteRemarks
    global SiteCoordinates

    if not config.has_section('Site'):
        print ("'Site' section is missed", file=sys.stderr)
        return

    SiteContactEmail = Variable(config, 'Site', 'SiteContactEmail', fallback = '')
    SiteName    = Variable(config, 'Site', 'SiteName', fallback = '')
    SiteRemarks = Variable(config, 'Site', 'SiteRemarks', fallback = '')
    SiteID      = Variable(config, 'Site', 'SiteID', fallback = '')
    SiteAddress = Variable(config, 'Site', 'SiteAddress', fallback = '')
    SiteCoordinates = Variable(config, 'Site', 'SiteCoordinates', fallback = SiteCoordinatesDef)

def __parse_networking_rec(config):
    #global En0WANIP
    global NTPServer
    global TimeZone
    global TimeAuto
    global DSTAuto
    global EthernetMasks, Eth0WANIP, Eth0WANNetMask, Eth1LANIP, Eth1LANNetMask
    global GatewayIP, DNS

    if not config.has_section('Networking'):
        print ("'Networking' section is missed", file=sys.stderr)
        return

    NTPServer= Variable(config, 'Networking', "NTPServer", fallback='')
    TimeZone = Variable(config, 'Networking', "TimeZone", fallback='')
    TimeAuto = Variable(config, 'Networking', "TimeAuto", fallback='')
    DSTAuto  = Variable(config, 'Networking', "DSTAuto", fallback='')

    EthernetMasks= Variable(config, 'Networking', "EthernetMasks", fallback='')
    Eth0WANIP = Variable(config, 'Networking', "En0WANIP", fallback='')
    Eth0WANNetMask = Variable(config, 'Networking', "En0WANNetMask", fallback='')
    Eth1LANIP  = Variable(config, 'Networking', "En1LANIP", fallback='')
    Eth1LANNetMask = Variable(config, 'Networking', "En1LANNetMask", fallback='')
    GatewayIP = Variable(config, 'Networking', "GatewayIP", fallback='')
    DNS  = Variable(config, 'Networking', "DNSServer", fallback='')

def __parse_filepush_rec(config):
    global FilePushOption, FilePushInterval, FilePushInputs
    global FilePushOutputs, FilePushAnalogs, FilePush1Wire
    global FilePushRS485, FilePushRS232, FilePushNet, FilePushAlarms

    global DestinationServerIP, DestinationServerPath
    global DestinationServerUserID, DestinationServerUserPW

    if not config.has_section('FilePush'):
        print ("'FilePush' section is missed", file=sys.stderr)
        return

    FilePushOption = Variable(config, 'FilePush', "FilePushOption", fallback='')
    FilePushInterval = Variable(config, 'FilePush', "FilePushInterval", fallback='')
    FilePushInputs   = Variable(config, 'FilePush', "FilePushInputs", fallback='')
    FilePushOutputs = Variable(config, 'FilePush', "FilePushOutputs", fallback='')
    FilePushAnalogs = Variable(config, 'FilePush', "FilePushAnalogs", fallback='')
    FilePush1Wire = Variable(config, 'FilePush', "FilePush1Wire", fallback='')
    FilePushRS485 = Variable(config, 'FilePush', "FilePushRS485", fallback='')
    FilePushRS232 = Variable(config, 'FilePush', "FilePushRS232", fallback='')
    FilePushNet = Variable(config, 'FilePush', "FilePushNet", fallback='')
    FilePushAlarms = Variable(config, 'FilePush', "FilePushAlarms", fallback='')
    DestinationServerIP = Variable(config, 'FilePush', "DestinationServerIP", fallback='')
    DestinationServerPath = Variable(config, 'FilePush', "DestinationServerPath", fallback='')
    DestinationServerUserID = Variable(config, 'FilePush', "DestinationServerUserID", fallback='')
    DestinationServerUserPW = Variable(config, 'FilePush', "DestinationServerUserPW", fallback='')
    
def __parse_alarm_rec(config):
    global AlarmAtSiteName, AlarmAtSiteID, AlarmAtSiteIP
    global AlarmAtSiteCoordinates, AlarmAtSiteAddress, AlarmAtSiteRemarks
    global AlarmAtAlarmDate, AlarmAtAlarmTime, AlarmAtAlarmInterface
    global AlarmAtAlarmSource, AlarmAtAlarmValue, AlarmAtAlarmName
    global AlarmAtAlarmDescription

    if not config.has_section('AlarmVariables'):
        print ("'AlarmVariables' section is missed", file=sys.stderr)
        return

    #alarm_rec = config['AlarmVariables']

    #__attribute_exists(alarm_rec, "@SiteName")
    AlarmAtSiteName = ReferenceVariable(config, 'AlarmVariables', "@SiteName")
    #__attribute_exists(alarm_rec, "@SiteID")
    AlarmAtSiteID = ReferenceVariable(config, 'AlarmVariables', "@SiteID")
    #__attribute_exists(alarm_rec, "@SiteIP")
    AlarmAtSiteIP = ReferenceVariable(config, 'AlarmVariables', "@SiteIP", fallback="En0WANIP")
    #__attribute_exists(alarm_rec, "@SiteCoordinates")
    AlarmAtSiteCoordinates = ReferenceVariable(config, 'AlarmVariables', "@SiteCoordinates")
    #__attribute_exists(alarm_rec, "@SiteAddress")
    AlarmAtSiteAddress = ReferenceVariable(config, 'AlarmVariables', "@SiteAddress")
    #__attribute_exists(alarm_rec, "@SiteRemarks")
    AlarmAtSiteRemarks = ReferenceVariable(config, 'AlarmVariables', "@SiteRemarks")
    #__attribute_exists(alarm_rec, "@AlarmDate")
    AlarmAtAlarmDate = ReferenceVariable(config, 'AlarmVariables', "@AlarmDate")
    #__attribute_exists(alarm_rec, "@AlarmTime")
    AlarmAtAlarmTime = ReferenceVariable(config, 'AlarmVariables', "@AlarmTime")
    #__attribute_exists(alarm_rec, "@AlarmInterface")
    AlarmAtAlarmInterface = ReferenceVariable(config, 'AlarmVariables', "@AlarmInterface")
    #__attribute_exists(alarm_rec, "@AlarmSource")
    AlarmAtAlarmSource = ReferenceVariable(config, 'AlarmVariables', "@AlarmSource")
    #__attribute_exists(alarm_rec, "@AlarmValue")
    AlarmAtAlarmValue = ReferenceVariable(config, 'AlarmVariables', "@AlarmValue")
    #__attribute_exists(alarm_rec, "@AlarmName")
    AlarmAtAlarmName = ReferenceVariable(config, 'AlarmVariables', "@AlarmName")
    # __attribute_exists(alarm_rec, "@AlarmDescription")
    AlarmAtAlarmDescription = ReferenceVariable(config, 'AlarmVariables', "@AlarmDescription")

def __run_cmd(cmd_as_string):
    prepared = cmd_as_string.split()
    subprocess.run(prepared)

def __is_ip_valid(ip):
    def isIPv4(s):
        try: return str(int(s)) == s and 0 <= int(s) <= 255
        except: return False
    if ip is None or len(ip) < 7:
        return False
    if ip.count('-') == 1:
        return __is_ip_valid(ip.split('-')[0]) and __is_ip_valid(ip.split('-')[1])
    if ip.count('/') == 1:
        return __is_ip_valid(ip.split('/')[0]) and isIPv4(ip.split('/')[1])
    if ip.count(".") == 3 and all(isIPv4(i) for i in ip.split(".")):
        return True
    return False


def create_ssmtp_conf():
    text = ""
    if len(smtpRoot) > 0:
        text += "root={}\n".format(smtpRoot)
    if len(smtpMailhub) > 0:
        text += "Mailhub={}\n".format(smtpMailhub)
    if len(smtpRewriteDomain) > 0:
        text += "RewriteDomain={}\n".format(smtpRewriteDomain)
    if len(smtpHostname) > 0:
        text += "Hostname={}\n".format(smtpHostname)
    if len(smtpFromLineOverride) > 0:
        text += "FromLineOverride={}\n".format(smtpFromLineOverride)
    if smtpUseTLS:
        text += "UseTLS=yes\n"
    if smtpUseSTARTTLS:
        text += "UseSTARTTLS=yes\n"
    if len(smtpTLSCert) > 0:
        text += "TLSCert={}\n".format(smtpTLSCert)
    if len(smtpTLSKey) > 0:
        text += "TLSKey={}\n".format(smtpTLSKey)
    if len(smtpTLS_CA_File) > 0:
        text += "TLS_CA_File={}\n".format(smtpTLS_CA_File)
    if len(snmpTLS_CA_Dir) > 0:
        text += "TLS_CA_Dir={}\n".format(snmpTLS_CA_Dir)
    if len(smtpAuthUser) > 0:
        text += "AuthUser={}\n".format(smtpAuthUser)
    if len(smtpAuthPass) > 0:
        text += "AuthPass={}\n".format(smtpAuthPass)
    if len(smtpAuthMethod) > 0:
        text += "AuthMethod={}\n".format(smtpAuthMethod)

    try:
        f = open("/usr/cvconf/ssmtp.conf", "w")
        f.write(text)
        f.close()
    except Exception as e:
        print("Failed to store ssmtp.conf", file=sys.stderr)

    #copy
    try:
        shutil.copy("/usr/cvconf/ssmtp.conf", '/etc/ssmtp/ssmtp.conf')
    except Exception as e:
        print("Failed to copy ssmtp.conf", file=sys.stderr)


#def getAlarmRecord():
#    return BaseAlarm.copy()

class CfgParser(configparser.ConfigParser):
    def read(self, filenames, encoding=None):
        self._data_reading = True
        super().read(filenames, encoding)
        self._data_reading = False

    def set_special_names(self, names):
        #self.special_names = names
        self.previous_var_name = ""
    
    def _write_section(self, fp, section_name, section_items, delimiter):
        fp.write("<{}>\n".format(section_name))
        for key, value in section_items:
            if key.startswith('*'):
                key = key.split('_')[0]
                #print ("New var name is [%s]" % key, file=sys.stderr)
            if value is not None: 
                value = delimiter + str(value).replace('\n', '\n\t')
            else:
                value = ""
            fp.write("{}{}\n".format(key, value))
        fp.write("\n")

    def optionxform(self, optionstr):
        #print ("optionxform: ", optionstr, file=sys.stderr)
        if hasattr(self, '_data_reading') and self._data_reading and optionstr.startswith('*'): # and self.previous_var_name is self.special_names:
            #print ("New var name is [%s_%s]" %(optionstr, self.previous_var_name), file=sys.stderr)
            return  "%s_%s" %(optionstr, self.previous_var_name)
        else:
            self.previous_var_name = optionstr
            return optionstr
    
__parser = None

def init():
    global __parser
    
    __parser = CfgParser(strict = False,
                         allow_no_value = True,
                         comment_prefixes = ('#', ';'))
    __parser.SECTCRE = re.compile(r"\< *(?P<header>[^]]+?) *\>")
    __parser.set_special_names(["P*_RS485Record*"])
    
    __parser.read(config_file)
    
    __parse_site_rec(__parser)
    __parse_device_rec(__parser)
    __parse_inputs_rec(__parser)
    __parse_outputs_rec(__parser)
    __parse_analogs_rec(__parser)
    __parse_rs232_rec(__parser)
    __parse_rs485_rec(__parser)
    __parse_onewire_rec(__parser)
    __parse_netapp_rec(__parser)
    __parse_alarm_rec(__parser)
    __parse_networking_rec(__parser)
    __parse_filepush_rec(__parser)
    __parse_email_rec(__parser)
    __parse_http_rec(__parser)
    __parse_syslog_rec(__parser)
    __parse_firewall_rec(__parser)
    __parse_sysaccess_rec(__parser)
    __parse_snmp_rec(__parser)
    __parse_snmpagent_rec(__parser)
    __parse_supervisor_rec(__parser)

        
def save(filename):
    if __parser is None:
        print("Call init for parser first", file=sys.stderr)
        return

    if filename is None:
        filename = config_file
        shutil.move(filename, filename + ".bak")
    
    fp = open(filename, "w")
    try:
        wb.fileLockAcquire(fp.fileno(), True)
        __parser.write(fp, "=")
    finally:
        wb.fileLockRelease(fp.fileno())
        fp.close()

#def store_variable(section, name, value):
#    __parser.set(section, name, value)

def store_array(section, name, value):
    for (i, v) in enumerate(value):
        store_variable(section, "%s%s" % (name, i), v)
