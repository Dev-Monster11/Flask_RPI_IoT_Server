import os
import sys
import subprocess
from datetime import datetime

EXECUTION_TIMEOUT = 10

class AlarmRecord(dict):
    __getattr__= dict.__getitem__
    __setattr__= dict.__setitem__
    __delattr__= dict.__delitem__

#    def __init__(self, config):
#        super().__init__()
#        if config.AlarmAtSiteName:
#            BaseAlarm.update({"SiteName": SiteNameconfig.get('Site', name)})
        
#    def copy(self):
#        y = AlarmRecord()
#
#        for key, value in self.items():
#            y.update({key : value})
#
#        return y

#    def getDict(self):
#        y = {}
#
#        for key, value in self.items():
#            y.update({key : value})
#
#        return y

    def build(self, cf, message):
        if message is None or len(message) == 0:
            return None
        #@SiteName, @SiteID, @SiteIP, @SiteCoordinates, @SiteAddress, @SiteRemarks,
        #@AlarmDate, @AlarmTime, @AlarmDescription
        self["SiteName"] = cf.SiteName.value
        self["SiteID"] = cf.SiteID.value
        self["SiteIP"] = cf.Eth0WANIP.value
        self["SiteCoordinates"] = cf.SiteCoordinates.value
        self["SiteAddress"] = cf.SiteAddress.value
        self["SiteRemarks"] = cf.SiteRemarks.value
        self["AlarmDate"] = datetime.now().strftime("%Y%m%d")
        self["AlarmTime"] = datetime.now().strftime("%H:%M:%S")
        self["AlarmDescription"] = message


def send_snmp_trap(alarm,
                   snmpManager,
                   snmpNotificationType,
                   snmpCommunity,
                   snmpv3TrapEngineID,
                   snmpv3InfEngineID,
                   snmpv3SecurityName,
                   snmpv3AuthProtocol,
                   snmpv3AuthKey,
                   snmpv3SecurityLevel,
                   snmpv3PrivProtocol,
                   snmpv3PrivKey,
                   En0WANIP):
    
    def build_snmp_args(alarm,args):
        if 'SiteName' in alarm:
            args.extend((".1.3.6.1.4.1.29760.10.19.1", "s", alarm['SiteName']))
        if 'SiteID' in alarm:
            args.extend((".1.3.6.1.4.1.29760.10.19.2", "s", alarm['SiteID']))
        if 'SiteIP' in alarm:
            args.extend((".1.3.6.1.4.1.29760.10.19.3", "s", alarm['SiteIP']))
        if 'SiteCoordinates' in alarm:
            args.extend((".1.3.6.1.4.1.29760.10.19.4", "s", alarm['SiteCoordinates']))
        if 'SiteAddress' in alarm:
            args.extend((".1.3.6.1.4.1.29760.10.19.5", "s", alarm['SiteAddress']))
        if 'SiteRemarks' in alarm:
            args.extend((".1.3.6.1.4.1.29760.10.19.6", "s", alarm['SiteRemarks']))
        if 'AlarmDate' in alarm:
            args.extend((".1.3.6.1.4.1.29760.10.19.7", "s", alarm['AlarmDate']))
        if 'AlarmTime' in alarm:
            args.extend((".1.3.6.1.4.1.29760.10.19.8", "s", alarm['AlarmTime']))
        if 'AlarmInterface' in alarm:
            args.extend((".1.3.6.1.4.1.29760.10.19.9", "s", alarm['AlarmInterface']))
        if 'AlarmSource' in alarm:
            args.extend((".1.3.6.1.4.1.29760.10.19.10", "s", alarm['AlarmSource']))
        if 'AlarmValue' in alarm:
            args.extend((".1.3.6.1.4.1.29760.10.19.11", "s", alarm['AlarmValue']))
        if 'AlarmName' in alarm:
            args.extend((".1.3.6.1.4.1.29760.10.19.12", "s", alarm['AlarmName']))
        if 'AlarmDescription' in alarm:
            args.extend((".1.3.6.1.4.1.29760.10.19.13", "s", alarm['AlarmDescription']))

    if snmpNotificationType.lower()  == "trapv1":
        OID = ".1.3.6.1.4.1.29760.10"
        TrapType = "6"
        TrapId   = "19"
        cmd = ["snmptrap",
               "-v1",
               "-c", snmpCommunity,
               snmpManager,
               OID,
               En0WANIP,
               TrapType,
               TrapId,
               ""]

        build_snmp_args(alarm, cmd)
    elif snmpNotificationType.lower() == "trapv2c":
        OID = ".1.3.6.1.4.1.29760.10.19"
        cmd = ["snmptrap",
               "-v2c",
               "-c", snmpCommunity,
               snmpManager,
               "",
               OID]
        build_snmp_args(alarm, cmd)
    elif snmpNotificationType.lower() == "trapv3":
        OID = ".1.3.6.1.4.1.29760.10"
        cmd = ["snmptrap",
               "-v3",
               "-e", snmpv3TrapEngineID,
               "-l", snmpv3SecurityLevel,
               "-u", snmpv3SecurityName]
        if snmpv3AuthKey is not None and len(snmpv3AuthKey) > 0:
            cmd.extend(("-a", "SHA","-A", snmpv3AuthKey))
        if snmpv3PrivKey is not None and len(snmpv3PrivKey) > 0:
            cmd.extend(("-x", "AES", "-X", snmpv3PrivKey))

        cmd.extend((snmpManager,
                    "",
                    OID))

        build_snmp_args(alarm, cmd)
    elif snmpNotificationType.lower() == "informv2c":
        OID =  ".1.3.6.1.4.1.29760.10.19"
        cmd = ["snmpinform",
               "-v2c",
               "-t", "20",
               "-c",
               snmpCommunity,
               snmpManager,
               "",
               OID]
        build_snmp_args(alarm, cmd)
    elif snmpNotificationType.lower() == "informv3":
        OID = ".1.3.6.1.4.1.29760.10"

        cmd = ["snmpinform",
               "-v3",
               "-t", "20",
               "-e", snmpv3TrapEngineID,
               "-l", snmpv3SecurityLevel,
               "-u", snmpv3SecurityName]
        if snmpv3AuthKey is not None and len(snmpv3AuthKey) > 0:
            cmd.extend(("-a", "SHA","-A", snmpv3AuthKey))
        if snmpv3PrivKey is not None and len(snmpv3PrivKey) > 0:
            cmd.extend(("-x", "AES", "-X", snmpv3PrivKey))

        cmd.extend((snmpManager,
                    "",
                    OID))

        build_snmp_args(alarm, cmd)
    else:
        print ("Wrong snmpNotificationType:", snmpNotificationType, file=sys.stderr)
        return

    print("SNMP ", cmd, file=sys.stderr)
    try:
        subprocess.run(cmd, timeout=EXECUTION_TIMEOUT)
    except Exception as e:
        print("Failed to send snmp message", e, file=sys.stderr)

def process_snmp(alarm, i,
                 snmpManager, snmpNotificationType,
                 snmpv12Community,   snmpv3TrapEngineID,
                 snmpv3InfEngineID,  snmpv3SecurityName,
                 snmpv3AuthProtocol, snmpv3AuthKey,
                 snmpv3SecurityLevel,snmpv3PrivProtocol,
                 snmpv3PrivKey, En0WANIP):

    print("SNMP types:", snmpNotificationType, file=sys.stderr)
    
    print(snmpNotificationType[i], file=sys.stderr)
    send_snmp_trap(alarm,
                   snmpManager,
                   snmpNotificationType[i] if len(snmpNotificationType) > i else "",
                   snmpv12Community[i]     if len(snmpv12Community) > i else "",
                   snmpv3TrapEngineID[i]   if len(snmpv3TrapEngineID) > i else "",
                   snmpv3InfEngineID[i]    if len(snmpv3InfEngineID) > i else "",
                   snmpv3SecurityName[i]   if len(snmpv3SecurityName) > i else "",
                   snmpv3AuthProtocol[i]   if len(snmpv3AuthProtocol) > i else "",
                   snmpv3AuthKey[i]        if len(snmpv3AuthKey) > i else "",
                   snmpv3SecurityLevel[i]  if len(snmpv3SecurityLevel) > i else "",
                   snmpv3PrivProtocol[i]   if len(snmpv3PrivProtocol) > i else "",
                   snmpv3PrivKey[i]        if len(snmpv3PrivKey) > i else "",
                   En0WANIP)
