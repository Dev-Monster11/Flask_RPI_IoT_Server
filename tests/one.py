from urllib.request import Request, urlopen
import json

uri_to_test = {
   "/monitor/realtime_data/analogs": {"GET": 200},
    "/monitor/realtime_data/outputs": {"GET": 200},
    "/monitor/realtime_data/1wire": {"GET": 200},
    "/monitor/realtime_data/rs-485": {"GET": 200},
    "/monitor/realtime_data/alarms": {"GET": 200},
    "/control/outputs" : {"GET": 200, "POST": 201},
    }

data_to_send = {
    "/configuration/networking": {"POST": {
        "Eth0WANIP" : "192.168.0.100",
        "Eth0WANNetMask" : "255.255.255.0",
        "Eth1LANIP" : "10.10.10.1",
        "Eth1LANNetMask" : "255.255.255.0",
        "GatewayIP" : "10.10.10.100",
        "DNSServer" : "ggg"
    }},
    "/configuration/site_info": {"POST":{
        "SiteName" : "SiteName",
        "SiteID" :  "SiteID",
        "SiteCoordinates" : "SiteCoordinates",
        "SiteContactEmail" : "SiteContactEmail",
        "SiteAddress" : "SiteAddress",
        "SiteRemarks" : "SiteRemarks"
    }},
    "/configuration/access_security/password":{"POST":{
         "AccessPWComplexityEnable" : True,
        "AccessPWLifetimeEnable"   : True
    }},
    "/configuration/access_security/authentication": {"POST":{
        "Access2FAEnable" : True,
        "Access2FATimer"  : False,
        "Access2FAGoogleEnable" : True
    }},
    "/configuration/snmp_agent/general" :{"POST":{
        "SNMPAgentEnable" : True,
        "SNMPDSysLocation" : "SNMPDSysLocation",
        "SNMPDSysContact" : "SNMPDSysContact",
        "SNMPDSysDescription" : "SNMPDSysDescription",
        "SNMPDSysObjectID" : "SNMPDSysObjectID",
        "SNMPDv12Community" : "SNMPDv12Community",
        "SNMPDv3EngineID" : "SNMPDv3EngineID"
    }},
    "/configuration/alarm_monitoring/snmp_notification": {"POST":{
        "SNMPNotificationEnable": True,
        "snmpManagerIP": ["192.168.1.120"],
        "snmpNotificationType": ["TRAPv3"],
        "snmpv12Community": ["public"],
        "snmpv3AuthKey": ["CVSite_AP"],
        "snmpv3AuthProtocol": ["SHA"],
        "snmpv3InfEngineID": [],
        "snmpv3PrivKey": ["CVSite_AP"],
        "snmpv3PrivProtocol": ["AES"],
        "snmpv3SecurityLevel": ["NoAuthNoPriv"],
        "snmpv3SecurityName": ["CVSite"],
        "snmpv3TrapEngineID": ["800074400a03b827ebefd587"]
    }},
    "/configuration/alarm_monitoring/email_notification": {"POST":{
        "EmailNotificationEnable": True,
        "EmailTo" : "EmailTo",
        "EmailCC" : "EmailCC",
        "EmailFrom" : "EmailFrom",
        "EmailSubject" : "EmailSubject",
        "EmailMsgHeader" : "EmailMsgHeader",
        "EmailMsgTrailer" : "EmailMsgTrailer",
        "EmailFormat": "EmailFormat",
        "smtpRoot"   : "smtpRoot",
        "smtpMailhub": "smtpMailhub",
        "smtpRewriteDomain" : "smtpRewriteDomain",
        "smtpHostname" : "smtpHostname",
        "smtpFromLineOverride": "smtpFromLineOverride",
        "smtpUseTLS" : True,
        "smtpUseSTARTTLS" : False,
        "smtpTLSCert" : "smtpTLSCert",
        "smtpTLSKey" : "smtpTLSKey",
        "smtpTLS_CA_File" : "smtpTLS_CA_File",
        "smtpTLS_CA_Dir" : "snmpTLS_CA_Dir",
        "smtpAuthUser" : "smtpAuthUser",
        "smtpAuthPass" : "smtpAuthPass",
        "smtpAuthMethod" : "smtpAuthMethod"
    }},
    "/configuration/access_security/firewall": {"POST":{
        "FirewallAppEnable":True,
        "FirewallIP":["192.168.0.0/24", "85.253.138.176", "130.75.185.182",
                      "130.75.185.112", "178.233.152.21", "173.34.18.0/24",
                      "82.131.13.0/24", "62.65.199.0/24", "82.131.86.0/24",
                      "120.89.105.0/24","120.89.104.0/24","85.253.139.0/24",
                      "176.219.202.0/24","46.154.239.0/24"]
    }},
    "/configuration/file_push": {"POST":{
        "DestinationServerIP":"",
        "DestinationServerPath":"",
        "DestinationServerUserID":"",
        "DestinationServerUserPW":"",
        "FilePush1Wire":"",
        "FilePushAlarms":"",
        "FilePushAnalogs":"",
        "FilePushInputs":"",
        "FilePushInterval":"",
        "FilePushNet":"","FilePushOption":"",
        "FilePushOutputs":"","FilePushRS232":"","FilePushRS485":""
    }},
    "/configuration/net_app/snmp_alarm_definitions": {"POST":{
        "IndexedCond": ["'INFORM', X, X, 00:10, Alarm, SNMP TestSite alarm", "'CVSite', X, X, 00:10, Alarm, SNMP Inputs alarm"]
    }},
    "/configuration/snmp_agent/user": {"POST":{
        "SNMPDv3AuthKey0":"","SNMPDv3AuthKey1":"","SNMPDv3AuthKey2":"",
        "SNMPDv3AuthProtocol0":"","SNMPDv3AuthProtocol1":"","SNMPDv3AuthProtocol2":"",
        "SNMPDv3PrivKey0":"",
        "SNMPDv3PrivKey1":"","SNMPDv3PrivKey2":"","SNMPDv3PrivProtocol0":"",
        "SNMPDv3PrivProtocol1":"","SNMPDv3PrivProtocol2":"","SNMPDv3SecurityName0":"",
        "SNMPDv3SecurityName1":"","SNMPDv3SecurityName2":""
    }},
    "/configuration/system_supervision": {"POST":{
        "DataBackupSchedule":"","Eth0LinkRestartInterval":"","Eth1LinkRestartInterval":"",
        "SoftRestartSchedule":"","SysHeartbeatReportInterval":"","SystemRebootSchedule":"",
        "SystemSupervisorScript":""
    }},
    "/configuration/alarm_monitoring/variables" :{"POST":{
        "AlarmDate":True,"AlarmDescription":True,"AlarmInterface":True,
        "AlarmName":True,"AlarmSource":True,"AlarmTime":True,
        "AlarmValue":True,"SiteAddress":True,
        "SiteCoordinates":True,"SiteID":True,"SiteIP":True,"SiteName":True,"SiteRemarks":True
    }},
    "/configuration/inputs_app/iso_names": {"POST": {
        "SelectGroup": "4-11",
        "IndexedIn": ["Contact 4", "Contact 5", "Contact 6", "Contact 7", "Contact 8", "Contact 9", "Contact 10", "Contact 11"]
    }},
    "/configuration/inputs_app/alarm_definitions":{"POST": {
        "SelectGroup": "12-19",
        "IndexedIn": ["Contact 120", "Contact 121", "Contact 122", "Contact 123", "Contact 124", "Contact 125", "Contact 126", "Contact 127"]
    }},
    "/configuration/inputs_app/general":{"POST":{
        "InputPollInterval":"1","InputsAppEnable":True,
        "InputsRawFileSize":"16,50, 6","InputsScript":""
    }},
    "/configuration/outputs_app/general":{"POST":{
        "OutputAppEnable":True,"OutputPollInterval":"5","OutputsRawFileSize":""
    }},
    "/configuration/outputs_app/output_names": {"POST":{
        "OutputName":[]
    }},
    "/configuration/outputs_app/output_default": {"POST":{
        "OutputDefault":""
    }},
    "/configuration/analogs_app/general":{"POST":{
        "AnalogPollInterval":"111111","AnalogsAlarmFileSize":"111111",
        "AnalogsAppEnable":True,"AnalogsRawFileSize":"111111",
        "AnalogsScript":"111111"
    }},
    "/configuration/analogs_app/analog_names":{"POST":{
        "AnalogName":['Analog Sensor 0', 'Analog Sensor 1',
                      'Analog Sensor 2', 'Analog Sensor 3', 'Analog Sensor 4', 'Analog Sensor 5']
    }},
    "/configuration/1wire_app/alarm_definitions":{"POST":{
        "Wire1Condition":{"0":{"0":"a, RiseAbove, 25.00|0.2, x, x, 99:59, Alarm, Sensor0 > 25C"},
                          "1":{"0":"b, RiseAbove, 25.00|0.2, x, x, 99:59, Alarm, Sensor1 > 25C"},
                          "2":{"0":"c, RiseAbove, 30.00|0.2, x, x, 99:59, Alarm, Sensor2 > 30C"},
                          "3":{"0":"d, RiseAbove, 30.00|0.2, x, x, 00:10, Alarm, Sensor3 > 30C"},
                          "4":{"0":"e, RiseAbove, 25.00|0.2, x, x, 99:59, Alarm, Sensor4 > 25C"},
                          "5":{"0":"f, RiseAbove, 30.00|0.2, x, x, 99:59, Alarm, Sensor5 > 30C"},
                          "6":{"0":"g, RiseAbove, 25.00|0.2, x, x, 99:59, Alarm, Sensor6 > 25C"},
                          "7":{"0":"h, RiseAbove, 25.00|0.2, x, x, 99:59, Alarm, Sensor7 > 25C"}},
        "Wire1DeviceID": ['28-00000cdf1b80', '28-00000ce0213e', '28-00000cdfb2e6',
                          '28-00000cdfd2f4', '28-00000cdfc8d3', '28-00000cdf797f', '28-00000cdf8808',
                          '28-00000cdfd992'],
        "Wire1DeviceName":['Sensor___0000_________', 'Sensor____1111________',
                           'Sensor_____2222_______', 'Sensor______3333______',
                           'Sensor_______4444_____', 'Sensor________5555____',
                           'Sensor_________6666___', 'Sensor__________7777__'],
        "Wire1RawFileSize":['10, 50, 5', '10, 50, 5', '10, 50, 7', '10, 50, 7',
                            '10, 50, 10', '10, 50, 10', '10, 50, 12', '10, 50, 12'],
        "Wire1Script":"",
        "Wire1Scripts":[],
        "Wire1UoM":['C', 'C', 'C', 'C', 'C', 'C', 'C', 'C']
    }},
    "/configuration/alarm_monitoring/http_notification": {"POST":{
        "httpPostNotificationEnable":True,
        "httpPostURL":["192.168.0.10/process-alarm.php",
                       "192.168.0.13/process-alarm.php",
                       "192.168.0.14/process-alarm.php"]
    }},
    "/configuration/alarm_monitoring/syslog_notification": {"POST":{
        "RsyslogNotificationEnable":True,
        "RsyslogServer":["192.168.0.10","192.168.0.13","192.168.0.14"]
    }},
    "/configuration/inputs_app/noniso_names" : {"POST":{
        "InputName":["Contact 0","Contact 1","Contact 2","Contact 3",
                     "Contact 4","Contact 5","Contact 6","Contact 7",
                     "Contact 8","Contact 9","Contact 10","Contact 11",
                     "Contact 12",
                     "Contact 13","Contact 14","Contact 15","Contact 16",
                     "Contact 17","Contact 18","Contact 19","Contact 20",
                     "Contact 21","Contact 22","Contact 23","Contact 24",
                     "Contact 25","Contact 26","Contact 27","Contact 28","Contact 29","Contact 30",
                     "Contact 31","Contact 32","Contact 33","Contact 34","Contact 35"]
    }},
    "/configuration/analogs_app/analog_offsets": {"POST":{
        "AnalogCalOffset":"-4.1187, -4.005, -4.1366, -7.5419, -3.9397, -3.9137"
    }},
    "/configuration/analogs_app/analog_converters": {"POST":{
        "AnalogConverter":["0, 72V, *, 0, 72, 0, 72, V, 0.068",
                           "1, 72V, *, 0, 72, 0, 72, V, 0.128",
                           "2, 36V, *, 0, 36, 0, 36, V, 0.034",
                           "3, 36V, *, 0, 36, 0, 36, V, 0.039",
                           "4, 18V, *, 0, 18, 0, 18, V, 0",
                           "5, 18V, *, 0, 18, 0, 18, V, 0.05"]
    }},
    "/configuration/1wire_app/general": {"POST":{
        "Wire1AlarmFileSize":"16, 50",
        "Wire1AppEnable":True,
        "Wire1PollInterval":"1",
        "Wire1Script":""
    }},
    "/configuration/rs232_app/general":{"POST":{
        "SerialAlarmFileSize":"16, 50",
        "SerialAppEnable":True,
        "SerialScript":[]
    }},
    "/configuration/rs232_app/device_configuration":{"POST":{
        "IP2Serial":["64000","64001","64002","64003","64004","64005","64006","64007"],
        "Serial2IP":["192.168.0.12:63000","192.168.0.12:63001",
                     "192.168.0.12:63002","192.168.0.12:63003",
                     "192.168.0.12:63004","192.168.0.12:63005",
                     "192.168.0.12:63006","192.168.0.12:63007"],
        "SerialMode":["Both","Both","Both","Both","Both","Both","Both","Both"],
        "SerialName":["Server Console 0","Server Console 1","Server Console 2",
                      "Server Console 3","Server Console 4","Server Console 5",
                      "Server Console 6","Server Console 7"],
        "SerialPortSetting":["115200, 8, N, 1, 0x0a","115200, 8, N, 1, 0x0a",
                             "115200, 8, N, 1, 0x0a","115200, 8, N, 1, 0x0a",
                             "115200, 8, N, 1, 0x0a","115200, 8, N, 1, 0x0a",
                             "115200, 8, N, 1, 0x0a","115200, 8, N, 1, 0x0a"],
        "SerialRawFileSize":["32, 50","32, 50","32, 50","32, 50","32, 50",
                             "32, 50","32, 50","32, 50"],
        "SerialSSHPort":["62000","62001","62002","62003","62004","62005","62006","62007"],
        "SerialScript":[]
    }},
    "/configuration/rs232_app/alarm_definitions":{"POST":{
        "Condition":{"0":{"0":"***, 0, On, 00:10, Alarm, ALARM error",
                          "1":"005, X, X, 00:15, /home/cvuserapps/TestScript.sh, ALARM error","2":"L050, X, X, 00:10, Alarm, ALARM error"},
                     "1":{"0":"===, 0, On, 00:10, Alarm, ALARM error",
                          "1":"010, X, X, 00:15, /home/cvuserapps/TestScript.sh, ALARM error","2":"L050, X, X, 00:10, Alarm, ALARM error"},
                     "2":{"0":"???, 0, On, 00:10, Alarm, ALARM error",
                          "1":"015, X, X, 00:15, /home/cvuserapps/TestScript.sh, ALARM error","2":"L050, X, X, 00:10, Alarm, ALARM error"},
                     "3":{"0":"<<<, 0, On, 00:10, Alarm, ALARM error",
                          "1":"020, X, X, 00:15, /home/cvuserapps/TestScript.sh, ALARM error","2":"L050, X, X, 00:10, Alarm, ALARM error"},
                     "4":{"0":"///, 0, On, 00:10, Alarm, ALARM error",
                          "1":"025, X, X, 00:15, /home/cvuserapps/TestScript.sh, ALARM error","2":"L050, X, X, 00:10, Alarm, ALARM error"},
                     "5":{"0":"---, 1, On, 00:10, Alarm, ALARM error",
                          "1":"030, X, X, 00:15, /home/cvuserapps/TestScript.sh, ALARM error","2":"L050, X, X, 00:10, Alarm, ALARM error"},
                     "6":{"0":"$$$, 0, On, 00:10, Alarm, ALARM error",
                          "1":"035, X, X, 00:15, /home/cvuserapps/TestScript.sh, ALARM error","2":"L050, X, X, 00:10, Alarm, ALARM error"},
                     "7":{"0":"###, 0, On, 00:10, Alarm, ALARM error",
                          "1":"040, X, X, 00:15, /home/cvuserapps/TestScript.sh, ALARM error","2":"L050, X, X, 00:10, Alarm, ALARM error"}},
        "SerialScript":[]
    }},
    "/configuration/rs485_app/general":{"POST":{
        "RS485AlarmFileSize":"8, 50",
        "RS485AppEnable":True,
        "RS485PollInterval":"5",
        "RS485Script":""
    }},
    "/configuration/rs485_app/device_configuration": {"POST":{
        "P0_DeviceID":["13","2"],"P0_PortSetting":["9600, 8, N, 1","9600, 8, N, 1"],
        "P0_Protocol":["Modbus","Modbus"],
        "P0_RS485DeviceName":["P0_0","P0_1"],
        "P0_RS485RawFileSize":["8, 50","8, 50"],
        "P0_RS485Script":[";echo check",";echo check"],
        "P1_DeviceID":["15","1"],
        "P1_PortSetting":["9600, 8, N, 1","9600, 8, N, 1"],
        "P1_Protocol":["Modbus","Modbus"],"P1_RS485DeviceName":["P1_0","P1_1"],
        "P1_RS485RawFileSize":["8, 50","8, 50"],
        "P1_RS485Script":[";echo check",";echo check"],
        "SelectDevice":"","SelectPort":""
    }},
    "/configuration/rs485_app/modbus_mapping":{"POST":{
        "*Var": {'0': {'P0_RS485Record0': 'Reg1/10', 'P1_RS485Record0': 'Reg3/10', 'P1_RS485Record1': 'f32(Reg0, Reg1)'}, 
                 '1': {'P0_RS485Record0': 'Reg1/10 * 1.8 + 32', 'P1_RS485Record0': 'Reg4/10', 'P1_RS485Record1': 'f32(Reg2, Reg3)'}, 
                 '2': {'P1_RS485Record0': 'Reg5/10', 'P1_RS485Record1': 'f32(Reg4, Reg5)'}, '3': {'P1_RS485Record1': 'f32(Reg6, Reg7)'}},
        "P0_RS485Record":["Var0, Celsius, Var1, Fahrenheit","V, V, A, A, W, W, H, Hz"],
        "P0_RS485RecordDescription":["TempSensor","V,A,W,Hz"],
        "P0_ReadData":["03.099:3, 03.105, 03.106:4","04.00:2, 04.06:2, 04.12:2, 04.70:2"],
        "P1_RS485Record":["Var0, C, Var1, g/m3, Var2, C dew point",
                          "Var0, V, Var1, A, Var2, W, Var3, Hz"],
        "P1_RS485RecordDescription":["Mixed Units","V,A,W,Hz"],
        "P1_ReadData":["04.29:6","04.00:2, 04.06:2, 04.12:2, 04.70:2"]
    }},
    "/configuration/rs485_app/alarm_definitions":{"POST":{
        "P0_RS485ConditionX.Y":{"0":{"0":"Var0, RiseAbove, 25, X, X, 00:00, Alarm, Rise above 25C"},
                                "1":{"0":"V, FallBelow, 115 | 1.5, X, X, 00:10, Alarm, 630_Voltage < 115V",
                                     "1":"A, FallBelow, 0.1, X, X, 00:10, /home/cvuserapps/TestScript.sh, 630_Current < 0.1A",
                                     "2":"W, FallBelow, 2, X, X, 00:00, Alarm, 630_Power < 2W"}},
        "P0_RS485Script":[";echo check",";echo check"],
        "P1_RS485ConditionX.Y":{"0":{"0":"Var0, RiseAbove, 25, X, X, 00:00, Alarm, Rise above 25C"},
                                "1":{"0":"Var0, FallBelow, 115 | 1.5, X, X, 00:10, Alarm, 230_Voltage < 115V",
                                     "1":"Var1, FallBelow, 0.1, X, X, 00:10, Alarm, 230_Current < 0.1A",
                                     "2":"Var2, FallBelow, 2, X, X, 00:00, Alarm, 230_Power < 2W"}},
        "P1_RS485Script":[";echo check",";echo check"]
    }},
    "/configuration/net_app/general":{"POST":{
        "NetAppEnable":True,
        "NetAppScript":""
    }},
    "/configuration/net_app/netapp_configuration/0":{"POST":{
        "Interface":["eth0"],
        "Mode":["Both"],
        "Name":["New Eth 0"],
        "NetAppRawFileSize":["8, 50, 5","8, 50, 5","8, 50, 5"],
        "NetAppScript":[],
        "Port":[9999],
        "Protocol":["UDP"],
    }},
    "/configuration/net_app/alarm_definitions":{"POST":{
        "NetAppConditionX.Y":{"1":{"0":"\'ALARM from\', X, X, 00:20, Alarm, NetApp test alarm appern"},

                              "2":{"0":"\'L0.0\', 1, On, 00:05, /home/cvuserapps/TestScript.sh, L010 alarm message"}},
        "NetAppScript":[]
    }},
    "/configuration/net_app/snmptrap_configuration":{"POST":{
        "Interface":"eth0","Port":" 162","Protocol":" udp",
        "SNMPTrapAppAlarmFileSize":"8, 50, 5",
        "SNMPTrapAppMode":"Both","SNMPTrapAppRawFileSize":"8, 50, 5"
    }},
    "/configuration/net_app/syslog_configuration":{"POST":{
        "SyslogAppAlarmFileSize":"8, 50, 15",
        "SyslogAppLogEnable":True,
        "SyslogAppMode":"Both","SyslogAppRawFileSize":"8, 50, 5"
    }},
    "/utilities/engineID":{"POST":{
        "nmpv3InfEngineID":["",""],
        "index": 0
    }},
    "/utilities/map_html":{"POST":{
        "SiteCoordinates": "43.64274, -79.38705",
        "HtmlCode": "This is test html code<bt><br>etc"
    }},
    "/control/outputs": {"POST":{
        "CurrentStates":"111111","SetOutput":[]
    }},
    "/control/restart":{"POST":{
        "NetReset": False,
        "Restart": False,
        "Reboot": False
    }},
    "/utilities/ping": {"POST":{
        "IPAddress" :"8.8.8.8"
    }},
    "/utilities/data_backup": {"POST":{
        "Push": False,
        "Backup": True
    }},
    "/utilities/modbus_discovery": {"POST":{
        "SelectPort": 0,
        "PortSetting": "115200,8,N,1",
        "SelectAction": "search",
        "Timeout": 1 
    }},
    "/utilities/snmptraps" : {"POST": {
        "SelectSNMPManager": "192.168.1.120",
        "TrapMessage": "This is a test trap message"
    }},
    "/utilities/file_transfer" :{"POST": {
        "ServerUserID": "test",
        "ServerUserPW": "test",
        "ServerIP": "192.168.0.13",
        "TransferType": "DeviceToServer",
        "DevicePath": "/tmp/cvdata/cvAlarms.txt",
        "ServerPath": "/tmp/"
    }},
}

required_headers = [{"Content-Type": "application/json"}, {'Access-Control-Allow-Origin': '*'}]

def _openUrl(url, method, data = None):
    req = Request(url, method = method)
    req.headers.update({"Content-Type": "application/json"})
    if data is not None:
        print ("Sending:", data)
        req.data = bytes(json.dumps(data), encoding="utf-8")

    response = urlopen(req)

    return (response.status, response.read(1024), response.headers)


def check_headers(orig, expected):
    for dheader in expected:
        header = list(dheader)[0]
        if header not in orig:
            print("Missed header:", header)
            return False
        value = dheader[header]
        a = orig[header]
        if a != value:
            print ("Wrong value for ", header, "Expecting:", value, "Got:", a)
            return False

    return True

def main(base_uri, print_detailed = False, requests = ["GET", "POST"]):
    for i in uri_to_test:
        for m in uri_to_test[i]:
            if requests is not None and m not in requests:
                continue
            code = uri_to_test[i][m]
            try:
                data = None
                if i in data_to_send and m in data_to_send[i]:
                    data = data_to_send[i][m]

                (ret, data, headers) = _openUrl(base_uri+i, m, data)
                if ret != code:
                    print (m,"\t", i, "\tFAILED, got", ret, "Expected", code)
                else:
                    if check_headers(headers, required_headers):
                        if print_detailed:
                            print (m,"\t", i, "\tSUCCESS\t", data, "HEADRES:", headers)
                        else:
                            print (m,"\t", i, "\tSUCCESS")
                    else:
                        print (m,"\t", i, "\tFAILED, Wrong headers\t", data, "HEADRES:", headers)

            except Exception as e:
                print (m, "\t", i,"\tFAILED, got exception", e)

if __name__ == "__main__":
    main("http://127.0.0.1:5000", True, ["GET"])
