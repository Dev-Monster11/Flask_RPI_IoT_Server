from flask import Flask
from flask import render_template
from flask import send_from_directory
from flask import stream_with_context
from flask.json import JSONEncoder
from flask.json import dumps
from flask import request
from flask import Response
from flask_cors import CORS
from logging.config import dictConfig
from logging.handlers import RotatingFileHandler
from time import gmtime, strftime

import datetime
import logging
import shutil
import psutil
import json
import sys
import os
import traceback

import config_parser as cf
import web_data as wb
import snmp_traps as st

class VariableJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, cf.Variable):
            return obj.value
        return super(JSONEncoder, self).default(obj)

sys_user = b"ubuntu"

data_dir = "/tmp/cvdata/"
alarm_file = "/tmp/cvdata/cvAlarms.txt"
iframe_file = "/usr/cvconf/cvmapiframe.txt"

cfg_file = None #"new.cfg" #debug!!!

snmp_pipe_file = "/tmp/cvnpipes/cvSNMPTrapAppExt"

dir_list = {"/usr/cvconf", "/home/cvbackups", "/home/cvuserapps", "/tmp/cvdata" }

copy_command = "scp"

run_timeout = 60

dictConfig({
    'version': 1,
    'handlers': {
        'file.handler': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/home/pi/flask.log',
            'maxBytes': 1000000,
            'backupCount': 2,
            'level': 'DEBUG',
        },
    },
    'loggers': {
        'werkzeug': {
            'level': 'DEBUG',
            'handlers': ['file.handler'],
        },
        'console': {
            'level': 'DEBUG',
            'handlers': ['file.handler'],
        },
        'application': {
            'level': 'DEBUG',
            'handlers': ['file.handler'],
        },
    },
    'root': {
        'level': 'DEBUG',
        'handlers': ['file.handler']
    }
})

cf.init()

app = Flask(__name__,
            static_url_path='', 
            static_folder='static')

app.json_encoder = VariableJSONEncoder

#app.logger.addHandler(handler)
app.logger.setLevel(logging.DEBUG)
#app.logger.setLevel(logging.INFO)

app.logger.debug(logging.Logger.manager.loggerDict)


cors = CORS(app, resources={r"/*": {"origins": "*"}}, methods=["GET", "POST"])

class WrongJson(Exception):
    """
    do nothing just signal that json is not correct
    """
    pass

@app.errorhandler(ValueError)
def valueerror_exception_handler(error):
    app.logger.warning(traceback.format_exc())
    app.logger.warning(sys.exc_info()[2])

    return 'Bad Request', 400

@app.errorhandler(TypeError)
def typeerror_exception_handler(error):
    app.logger.warning(traceback.format_exc())
    app.logger.warning(sys.exc_info()[2])

    return 'Bad Request', 500

@app.errorhandler(BlockingIOError)
def blockingerror_exception_handler(error):
    app.logger.debug(traceback.format_exc())
    app.logger.debug(sys.exc_info()[2])

    return 'Service Unavailable', 503, {"Retry-After": 15}


@app.errorhandler(WrongJson)
def typeerror_exception_handler(error):
    app.logger.debug(traceback.format_exc())
    app.logger.info(sys.exc_info()[2])

    return 'Forbidden', 403


@app.before_request
def before_request():
    app.logger.debug("%s: [%s]" % (request.endpoint, request.__dict__))
    return None

def validateJson(req, expected_fields = None):
    if not req.is_json:
        raise WrongJson("Not a json")

    if expected_fields is None or len(expected_fields) == 0:
        return

    json = request.get_json(silent=True)
    if json is None or len(json) == 0:
        raise WrongJson("JSON is empty")
    
    for i in expected_fields:
        if i not in json:
            app.logger.error("Field %s is missed in the request" % i)
            raise WrongJson("Field %s is missing" % i)
        

def get_cpu_temp():
    with open("/sys/class/thermal/thermal_zone0/temp") as f:
        return int(f.readline().strip())/1000

@app.route("/dashboard/site_info", methods=['GET'])
def site_info():
    net_apps = '-'

    if cf.NetAppEnable:
        i = len(cf.NetApp)
        i += 1 if len(cf.SNMPTrapAppMode) > 0 and cf.SNMPTrapAppMode.lower() != "none" else 0
        i += 1 if len(cf.SyslogAppMode) > 0 and cf.SyslogAppMode.lower() != "none" else 0
        net_apps = str(i)

    iframe = ""
    try:
        with open(iframe_file) as f:
            iframe = f.read()

    except Exception as e:
        app.logger.warning ("Error at site_info: %s" % e)
    
    return jsonify({ "name" : cf.SiteName,
             "remarks" : cf.SiteRemarks,
             "sw" : cf.SWRev,
             "hw" : cf.HWRev,
             "inputs" : str(cf.InputMasks.count('1')) if cf.InputsAppEnable else "-",
             "outputs" : str(cf.OutputMasks.count('1')) if cf.OutputsAppEnable else "-",
             "analogs" : str(cf.AnalogMasks.count('1')) if cf.AnalogsAppEnable else "-",
             "rs232" : str(cf.SerialMasks.count('1')) if cf.SerialsAppEnable else "-",
             "rs_485" : str(len(cf.P0_DeviceID)+len(cf.P1_DeviceID)) if cf.RS485AppEnable else "-",
             "wire1" : str(len(cf.OneWireDeviceID)) if cf.OneWireAppEnable else "-",
             "network": net_apps,
             "mapiframe" : iframe
    })#)

@app.route("/dashboard/notification", methods=['GET'])
def notification():
    return jsonify({
        "email" : "ON" if cf.EmailNotificationEn else "OFF",
        "snmp" : "ON" if cf.SNMPNotificationEn  else "OFF",
        "post" : "ON" if cf.httpPostNotificationEn else "OFF",
        "syslog" : "ON" if cf.RsyslogNotificationEn else "OFF"
    })

@app.route("/dashboard/resources", methods=['GET'])
def resourses():
    return jsonify({
        "temp"  : get_cpu_temp(),
        "ram"   : int(psutil.virtual_memory().free/(1024*1024)),
        "flash" : int(psutil.disk_usage('/').free/(1024*1024))
    })


@app.route("/dashboard/access", methods=['GET'])
def access():
    r = wb.lastLogin(sys_user)
    if r[0] != 0:
        app.logger.debug("Error:", r[2])
    
    return jsonify({
        "LastLogin": r[1],
        "firewall" : "ON" if cf.FirewallAppEnable else "OFF",
        "2fa"   : "ON" if cf.Access2FAEnable else "OFF",
        "ga2fa" : "ON" if cf.Access2FAGoogleEnable else "OFF"
    })

@app.route("/dashboard/inputs", methods=['GET'])
def inputs():
    (i, pf) = wb.readInput()
    
    return jsonify({
        "inputs" :  i[0] if i is not None and len(i) > 0 else ""
    })

@app.route("/dashboard/outputs", methods=['GET'])
def outputs():
    def out(o, i):
        l = 0 if o is None else len(o)
        if l > i and o[i] == '0':
            return "ON"
        elif l > i and o[i] == '1':
            return 'OFF'
        else:
            return '-'

    (o, pf) = wb.readOutput()

    s= "" if o is None or len(o) == 0 else o[0]

    return jsonify({
        "out0": out(s, 0),
        "out1": out(s, 1),
        "out2": out(s, 2),
        "out3": out(s, 3),
        "out4": out(s, 4),
        "out5": out(s, 5)
    })

@app.route("/dashboard/analogs", methods=['GET'])
def analogs():
    (a, pf) = wb.readAnalog()

    def out(o, i):
        l = 0 if o is None else len(o)
        if l > i :
            return o[i]
        else:
            return '-'

    s= "" if a is None or len(a) == 0 else a[0]
        
    return jsonify({
        "analogs": s
    })

@app.route("/dashboard/1wire", methods=['GET'])
def one_wire():
    def run():
        timer = wb.RunTimer(run_timeout)
        while not timer.isTimeout():
            (s, pf) = wb.readOneWire()
            yield dumps({"wire1": [] if s is None else s})

    return Response(stream_with_context(run()),  mimetype='application/json')

@app.route("/dashboard/rs232", methods=['GET'])
def rs232():
    def run():
        timer = wb.RunTimer(run_timeout)
        while not timer.isTimeout():
            yield dumps({
                "serialmasks" : cf.SerialMasks,
                "serial0" : wb.readRS232(0)[0],
                "serial1" : wb.readRS232(1)[0],
                "serial2" : wb.readRS232(2)[0],
                "serial3" : wb.readRS232(3)[0],
                "serial4" : wb.readRS232(4)[0],
                "serial5" : wb.readRS232(5)[0],
                "serial6" : wb.readRS232(6)[0],
                "serial7" : wb.readRS232(7)[0]
            })

    return Response(stream_with_context(run()),  mimetype='application/json')

@app.route("/dashboard/rs485", methods=['GET'])
def rs485():
    def run():
        timer = wb.RunTimer(run_timeout)
        while not timer.isTimeout():
            (s, pf) = wb.readRS485()
            yield dumps({
                "rs485" : [] if s is None else s
            })
        
    return Response(stream_with_context(run()),  mimetype='application/json')

@app.route("/dashboard/netapp", methods=['GET'])
def netapp():
    net_apps = '-'

    if cf.NetAppEnable:
        i = len(cf.NetApp)
        i += 1 if len(cf.SNMPTrapAppMode) > 0 and cf.SNMPTrapAppMode.lower() != "none" else 0
        i += 1 if len(cf.SyslogAppMode) > 0 and cf.SyslogAppMode.lower() != "none" else 0
        net_apps = str(i)

    return jsonify({
        "netcount" : net_apps,
        "snmpcount": 1 if len(cf.SNMPTrapAppMode) > 0 and cf.SNMPTrapAppMode.lower() != "none" else 0,
        "syslogcount": 1 if len(cf.SyslogAppMode) > 0 and cf.SyslogAppMode.lower() != "none" else 0,
    })

@app.route("/dashboard/netapp/snmp", methods=['GET'])
def netapp_snmp():
    def run():
        timer = wb.RunTimer(run_timeout)
        f = None
        try:
            while not timer.isTimeout():
                (line, f) = wb.readPipe(snmp_pipe_file, f)
                yield dumps({"snmp" : line})

            (line, f) = wb.readPipe(snmp_pipe_file, f, stop = True)
            return dumps({"snmp" : line})
        except Exception as e:
            wb.readPipe(snmp_pipe_file, f, stop_only = True)
            return dumps({"snmp" : []})
            
    return Response(stream_with_context(run()),  mimetype='application/json')


@app.route("/dashboard/today_alarms", methods=['GET'])
def today_alarms():
    '''
    yyyymmdd, hhmmss, Interface, Source, Value, Name, Description
    '''
    today_total = 0
    today_inputs = 0
    today_analog = 0
    today_rs232 = 0
    today_rs485 = 0
    today_one_wire = 0
    today_net = 0
    try:
        today = datetime.date.today().strftime('%Y%m%d')
        with open(alarm_file) as f:
            for alarmf in f:
                if not alarmf.startswith(today):
                    continue
                alarm = alarmf.strip().split(',')
                today_total += 1
                app.logger.debug (alarm)
                interface = alarm[2].strip().lower()
                app.logger.debug ("Interface [%s]" % interface)
                
                if interface == 'inputs': today_inputs += 1
                elif interface == 'analogs': today_analog += 1
                elif interface == 'rs-232': today_rs232 += 1
                elif interface == 'rs-485': today_rs485 += 1
                elif interface == '1-wire': today_one_wire += 1
                elif interface.startswith('ethernet'): today_net += 1
                else:
                    app.logger.warning ("today_alarms: unknown interface [%s]" % interface)

                app.logger.debug ("total %s, inputs %s, analogs %s, rs232 %s, rs485 %s, wire1 %s, network %s" %
                                  (today_total, today_inputs, today_analog, today_rs232, today_rs485, today_one_wire, today_net))

    except Exception as e:
        app.logger.warning ("Error at today_alarms: %s" % e)
    
    return jsonify({
        "total"  : today_total,
        "inputs" : today_inputs,
        "analogs": today_analog,
        "rs232"  : today_rs232,
        "rs485"  : today_rs485,
        "wire1"  : today_one_wire,
        "network": today_net
    })

@app.route("/dashboard/recent_alarms", methods=['GET'])
def recent_alarms():
    recent_alarms = []
    try:
        with open(alarm_file) as f:
            for alarmf in f:
                recent_alarms.append(alarmf) 
    except Exception as e:
        app.logger.warning ("Error at recent_alarms: %s" % e)
        
    return jsonify({
        "recent" : recent_alarms
    })

@app.route("/dashboard/alarm_distribution", methods=['GET'])
def alarm_distribution():
    cvInputsAlarmInt  = 0 #; Interface = Inputs
    cvAnalogsAlarmInt = 0 #; Interface = Analogs	
    cvRS485AlarmInt = 0 #; Interface = RS-485
    cvRS232AlarmInt = 0 #; Interface = RS-232
    cv1WireAlarmInt = 0 #; Interface = 1-Wire
    cvNetAppAlarmInt = 0 #; Interface = Ethernet 0 or Ethernet 1

    try:
        with open(alarm_file) as f:
            for alarmf in f:
                try:
                    interface = alarmf.split(',')[2].lower()
                    if "inputs" == interface:
                        cvInputsAlarmInt += 1
                    elif "analogs" == interface:
                        cvAnalogsAlarmInt += 1
                    elif "rs-485" == interface:
                        cvRS485AlarmInt += 1
                    elif "rs-232" == interface:
                        cvRS232AlarmInt += 1
                    elif "1-wire" == interface:
                        cv1WireAlarmInt += 1
                    elif interface.startswith("ethernet"):
                        cvNetAppAlarmInt += 1
                        
                except Exception as e:
                    app.logger.warning("Got error in alarm processing %s" % e)

    except Exception as e:
        app.logger.warning ("Error at alarm_distribution: %s" % e)
        
    return jsonify({
        "inputs"  : cvInputsAlarmInt,
        "analogs" : cvAnalogsAlarmInt,
        "rs485"   : cvRS485AlarmInt,
        "rs232"   : cvRS232AlarmInt,
        "wire1"   : cv1WireAlarmInt,
        "network"  : cvNetAppAlarmInt
    })

@app.route("/dashboard/data_distribution", methods=['GET'])
def data_distribution():
    inputs = 0
    outputs = 0
    analogs = 0
    rs485 = 0
    rs232 = 0
    wire1 = 0
    network = 0

    for i in os.listdir(data_dir):
        sz = os.path.getsize(data_dir+i)
        if i == "cvInputsRaw.txt":
            inputs += sz
        elif i == "cvAnalogsRaw.txt":
            analogs += sz
        elif i == "cvOutputsRaw.txt":
            outputs += sz
        elif i == "cvSNMPTrapAppRaw.txt":
            network += sz
        elif i == "cvSyslogAppRaw.txt":
            network += sz
        elif i.startswith("cv1Wire"):
            wire1 += sz
        elif i.startswith("cvRS232Device"):
            rs232 += sz
        elif i.startswith("cvRS485Raw"):
            rs485 += sz
        elif i.startswith("cvNetAppRaw"):
            network += sz

    return jsonify({
        "inputs" : inputs,
        "outputs": outputs,
        "analogs": analogs,
        "rs485"  : rs485,
        "rs232"  : rs232,
        "wire1"  : wire1,
        "network": network
    })

@app.route("/configuration/site_info", methods=['GET'])
def configuration_site_info():
    return jsonify({
        "SiteName" : cf.SiteName,
        "SiteID" : cf.SiteID,
        "SiteCoordinates" : cf.SiteCoordinates,
        "SiteContactEmail" : cf.SiteContactEmail,
        "SiteAddress" : cf.SiteAddress,
        "SiteRemarks" : cf.SiteRemarks
    })

@app.route("/configuration/site_info", methods=['POST'])
def configuration_site_info_post():
    app.logger.debug ("GOT:", request.json)
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.SiteName.value = request.json["SiteName"]
    cf.SiteID.value = request.json["SiteID"]
    cf.SiteCoordinates.value = request.json["SiteCoordinates"]
    cf.SiteContactEmail.value = request.json["SiteContactEmail"]
    cf.SiteAddress.value = request.json["SiteAddress"]
    cf.SiteRemarks.value = request.json["SiteRemarks"]

    cf.save(cfg_file)

    return "OK", 201, {"Content-Type": "application/json"}


@app.route("/configuration/date_time", methods=['GET'])
def configuration_date_time():

    return jsonify({
        "currentdate" : strftime("%Y-%m-%d", gmtime()),
        "currenttime" : strftime("%H:%M:%S", gmtime()),
        "NTPServer"   : cf.NTPServer,
        "TimeZone"    : cf.TimeZone,
        "date"        : strftime("%Y-%m-%d", gmtime()),
        "time"        : strftime("%H:%M:%S", gmtime()),
        "TimeAuto"    : cf.TimeAuto,
        "DSTAuto"     : cf.DSTAuto,
        "synctime"    : strftime("%Y-%m-%d %H:%M:%S", gmtime())
    })

@app.route("/configuration/date_time", methods=['POST'])
def configuration_date_time_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    currentdate = None
    currenttime = None
    if "date" in request.json:
        currentdate = request.json["date"]

    if "time" in request.json:
        currenttime = request.json["time"]

    if currentdate is not None or currenttime is not None:
        wb.setTime(currentdate, currenttime)

    if "NTPServer" in request.json:
        cf.NTPServer.value = request.json["NTPServer"]

    if "TimeZone" in request.json:
        cf.TimeZone.value = request.json["TimeZone"]

    if "TimeAuto" in request.json:
        cf.TimeAuto.value = request.json["TimeAuto"]

    if "DSTAuto" in request.json:
        cf.DSTAuto.value  = request.json["DSTAuto"]

    if "synctime" in request.json and  request.json["synctime"]:
        wb.callApplication("hwclock", ["-r"], path = "")

    cf.save(cfg_file)

    return "OK", 201, {"Content-Type": "application/json"}


@app.route("/configuration/networking", methods=['GET'])
def configuration_networking():

    return jsonify({
        "Eth0WANIP" : cf.Eth0WANIP,
        "Eth0WANNetMask" : cf.Eth0WANNetMask,
        "Eth1LANIP" : cf.Eth1LANIP,
        "Eth1LANNetMask" : cf.Eth1LANNetMask,
        "GatewayIP" : cf.GatewayIP,
        "DNSServer" : cf.DNS
    })

@app.route("/configuration/networking", methods=['POST'])
def configuration_networking_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    app.logger.debug (request.json)
    cf.Eth0WANIP.value = request.json["Eth0WANIP"]
    #cf.store_variable('Networking', "Eth0WANIP", request.json["Eth0WANIP"])
    cf.Eth0WANNetMask.value = request.json["Eth0WANNetMask"]
    cf.Eth1LANIP.value = request.json["Eth1LANIP"]
    cf.Eth1LANNetMask.value = request.json["Eth1LANNetMask"]
    cf.GatewayIP.value = request.json["GatewayIP"]
    cf.DNS.value = request.json["DNSServer"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}


@app.route("/configuration/access_security/firewall", methods=['GET'])
def configuration_access_security_firewall():

    return jsonify({
        "FirewallAppEnable" : cf.FirewallAppEnable,
        "FirewallIP"        : cf.FirewallAdminIP
    })
        
@app.route("/configuration/access_security/firewall", methods=['POST'])
def configuration_access_security_firewall_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.FirewallAppEnable.value = request.json["FirewallAppEnable"]
    cf.FirewallAdminIP.value = request.json["FirewallIP"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}
 
@app.route("/configuration/access_security/password", methods=['GET'])
def configuration_access_security_password():

    return jsonify({
        "AccessPWComplexityEnable" : cf.AccessPWComplexityEnable,
        "AccessPWLifetimeEnable"   : cf.AccessPWLifetimeEnable
    })
 
@app.route("/configuration/access_security/password", methods=['POST'])
def configuration_access_security_password_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.AccessPWComplexityEnable.value = request.json[ "AccessPWComplexityEnable"]
    cf.AccessPWLifetimeEnable.value = request.json["AccessPWLifetimeEnable"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/access_security/authentication", methods=['GET'])
def configuration_access_security_authentication():

    return jsonify({
        "Access2FAEnable" : cf.Access2FAEnable,
        "Access2FATimer"  : cf.Access2FATimer,
        "Access2FAGoogleEnable" : cf.Access2FAGoogleEnable
    })

@app.route("/configuration/access_security/authentication", methods=['POST'])
def configuration_access_security_authentication_post():
    if not request.is_json:
        return "Unsupported Media Type", 415
    
    cf.Access2FAEnable.value = request.json["Access2FAEnable"]
    cf.Access2FATimer.value = request.json["Access2FATimer"]
    cf.Access2FAGoogleEnable.value = request.json["Access2FAGoogleEnable"]
    cf.save(cfg_file)

    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/file_push", methods=['GET'])
def configuration_file_push():
    return jsonify({
        "FilePushOption" : cf.FilePushOption,
        "FilePushInterval" : cf.FilePushInterval,
        "FilePushInputs"   : cf.FilePushInputs,
        "FilePushOutputs"  : cf.FilePushOutputs,
        "FilePushAnalogs"  : cf.FilePushAnalogs,
        "FilePush1Wire"    : cf.FilePush1Wire,
        "FilePushRS485"    : cf.FilePushRS485,
        "FilePushRS232"    : cf.FilePushRS232,
        "FilePushNet"      : cf.FilePushNet,
        "FilePushAlarms"   : cf.FilePushAlarms,
        "DestinationServerIP" : cf.DestinationServerIP,
        "DestinationServerPath" : cf.DestinationServerPath,
        "DestinationServerUserID" : cf.DestinationServerUserID,
        "DestinationServerUserPW" : cf.DestinationServerUserPW
    })

@app.route("/configuration/file_push", methods=['POST'])
def configuration_file_push_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.FilePushOption.value   = request.json[  "FilePushOption"]
    cf.FilePushInterval.value = request.json["FilePushInterval"]
    cf.FilePushInputs.value   = request.json[  "FilePushInputs"]
    cf.FilePushOutputs.value  = request.json[ "FilePushOutputs"]
    cf.FilePushAnalogs.value  = request.json[ "FilePushAnalogs"]
    cf.FilePush1Wire.value    = request.json[   "FilePush1Wire"]
    cf.FilePushRS485.value    = request.json[   "FilePushRS485"]
    cf.FilePushRS232.value    = request.json[   "FilePushRS232"]
    cf.FilePushNet.value      = request.json[     "FilePushNet"]
    cf.FilePushAlarms.value   = request.json[  "FilePushAlarms"]
    cf.DestinationServerIP.value     = request.json[    "DestinationServerIP"]
    cf.DestinationServerPath.value   = request.json[  "DestinationServerPath"]
    cf.DestinationServerUserID.value = request.json["DestinationServerUserID"]
    cf.DestinationServerUserPW.value = request.json["DestinationServerUserPW"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

        
@app.route("/configuration/snmp_agent/general", methods=['GET'])
def configuration_snmp_agent_general():
    return jsonify({
        "SNMPAgentEnable" : cf.SNMPAgentEnable,
        "SNMPDSysLocation" : cf.SNMPDSysLocation,
        "SNMPDSysContact" : cf.SNMPDSysContact,
        "SNMPDSysDescription" : cf.SNMPDSysDescription,
        "SNMPDSysObjectID" : cf.SNMPDSysObjectID,
        "SNMPDv12Community" : cf.SNMPDv12Community,
        "SNMPDv3EngineID" : cf.SNMPDv3EngineID
    })

@app.route("/configuration/snmp_agent/general", methods=['POST'])
def configuration_snmp_agent_general_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.SNMPAgentEnable.value = request.json["SNMPAgentEnable"]
    cf.SNMPDSysLocation.value = request.json["SNMPDSysLocation"]
    cf.SNMPDSysContact.value = request.json["SNMPDSysContact"]
    cf.SNMPDSysDescription.value = request.json["SNMPDSysDescription"]
    cf.SNMPDSysObjectID.value = request.json[ "SNMPDSysObjectID"]
    cf.SNMPDv12Community.value = request.json[ "SNMPDv12Community"]
    cf.SNMPDv3EngineID.value = request.json[ "SNMPDv3EngineID"]

    cf.save(cfg_file)
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/snmp_agent/user", methods=['GET'])
def configuration_snmp_agent_user():
    return jsonify({
        "SNMPDv3SecurityName0" : cf.SNMPDv3SecurityName0,
        "SNMPDv3AuthProtocol0" : cf.SNMPDv3AuthProtocol0,
        "SNMPDv3AuthKey0" : cf.SNMPDv3AuthKey0,
        "SNMPDv3PrivProtocol0" : cf.SNMPDv3PrivProtocol0,
        "SNMPDv3PrivKey0": cf.SNMPDv3PrivKey0,
        "SNMPDv3SecurityName1" : cf.SNMPDv3SecurityName1,
        "SNMPDv3AuthProtocol1" : cf.SNMPDv3AuthProtocol1,
        "SNMPDv3AuthKey1" : cf.SNMPDv3AuthKey1,
        "SNMPDv3PrivProtocol1" : cf.SNMPDv3PrivProtocol1,
        "SNMPDv3PrivKey1" : cf.SNMPDv3PrivKey1,
        "SNMPDv3SecurityName2" : cf.SNMPDv3SecurityName2,
        "SNMPDv3AuthProtocol2" : cf.SNMPDv3AuthProtocol2,
        "SNMPDv3AuthKey2" : cf.SNMPDv3AuthKey2,
        "SNMPDv3PrivProtocol2" : cf.SNMPDv3PrivProtocol2,
        "SNMPDv3PrivKey2" : cf.SNMPDv3PrivKey2
    })

@app.route("/configuration/snmp_agent/user", methods=['POST'])
def configuration_snmp_agent_user_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.SNMPDv3SecurityName0.value  = request.json["SNMPDv3SecurityName0"]
    cf.SNMPDv3AuthProtocol0.value  = request.json["SNMPDv3AuthProtocol0"]
    cf.SNMPDv3AuthKey0.value  = request.json["SNMPDv3AuthKey0"]
    cf.SNMPDv3PrivProtocol0.value  = request.json["SNMPDv3PrivProtocol0"]
    cf.SNMPDv3PrivKey0.value  = request.json["SNMPDv3PrivKey0"]
    cf.SNMPDv3SecurityName1.value = request.json["SNMPDv3SecurityName1"]
    cf.SNMPDv3AuthProtocol1.value = request.json["SNMPDv3AuthProtocol1"]
    cf.SNMPDv3AuthKey1.value = request.json["SNMPDv3AuthKey1"]
    cf.SNMPDv3PrivProtocol1.value = request.json["SNMPDv3PrivProtocol1"]
    cf.SNMPDv3PrivKey1.value = request.json["SNMPDv3PrivKey1"]
    cf.SNMPDv3SecurityName2.value = request.json["SNMPDv3SecurityName2"]
    cf.SNMPDv3AuthProtocol2.value = request.json["SNMPDv3AuthProtocol2"]
    cf.SNMPDv3AuthKey2.value = request.json["SNMPDv3AuthKey2"]
    cf.SNMPDv3PrivProtocol2.value = request.json["SNMPDv3PrivProtocol2"]
    cf.SNMPDv3PrivKey2.value = request.json["SNMPDv3PrivKey2"]
        
    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

        
@app.route("/configuration/system_supervision", methods=['GET'])
def configuration_system_supervision():
    return jsonify({
        "SysHeartbeatReportInterval": cf.SysHeartbeatReportInterval,
        "Eth0LinkRestartInterval" : cf.Eth0LinkRestartInterval,
        "Eth1LinkRestartInterval" : cf.Eth1LinkRestartInterval,
        "DataBackupSchedule" : cf.DataBackupSchedule,
        "SoftRestartSchedule" : cf.SoftRestartSchedule,
        "SystemRebootSchedule": cf.SystemRebootSchedule,
        "SystemSupervisorScript": cf.SystemSupervisorScript
    })

@app.route("/configuration/system_supervision", methods=['POST'])
def configuration_system_supervision_post():
    if not request.is_json:
        return "Unsupported Media Type", 415
    
    cf.SysHeartbeatReportInterval.value  = request.json["SysHeartbeatReportInterval"]
    cf.Eth0LinkRestartInterval.value = request.json["Eth0LinkRestartInterval"]
    cf.Eth1LinkRestartInterval.value = request.json["Eth1LinkRestartInterval"]
    cf.DataBackupSchedule.value = request.json["DataBackupSchedule"]
    cf.SoftRestartSchedule.value = request.json["SoftRestartSchedule"]
    cf.SystemRebootSchedule.value = request.json["SystemRebootSchedule"]
    cf.SystemSupervisorScript.value = request.json["SystemSupervisorScript"]
    
    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

        
@app.route("/configuration/alarm_monitoring/variables", methods=['GET'])
def configuration_alarm_monitoring_variables():
    return jsonify({
        "SiteName" : cf.AlarmAtSiteName,
        "SiteID": cf.AlarmAtSiteID,
        "SiteIP": cf.AlarmAtSiteIP,
        "SiteCoordinates": cf.AlarmAtSiteCoordinates,
        "SiteAddress": cf.AlarmAtSiteAddress,
        "SiteRemarks": cf.AlarmAtSiteRemarks,
        "AlarmDate":   cf.AlarmAtAlarmDate,
        "AlarmTime":   cf.AlarmAtAlarmTime,
        "AlarmInterface": cf.AlarmAtAlarmInterface,
        "AlarmSource": cf.AlarmAtAlarmSource,
        "AlarmValue" : cf.AlarmAtAlarmValue,
        "AlarmName"  : cf.AlarmAtAlarmName,
        "AlarmDescription": cf.AlarmAtAlarmDescription
    })

@app.route("/configuration/alarm_monitoring/variables", methods=['POST'])
def configuration_alarm_monitoring_variables_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.AlarmAtSiteName.value = request.json["SiteName"]
    cf.AlarmAtSiteID.value = request.json["SiteID"]
    cf.AlarmAtSiteIP.value = request.json["SiteIP"]
    cf.AlarmAtSiteCoordinates.value = request.json["SiteCoordinates"]
    cf.AlarmAtSiteAddress.value = request.json["SiteAddress"]
    cf.AlarmAtSiteRemarks.value = request.json["SiteRemarks"]
    cf.AlarmAtAlarmDate.value = request.json["AlarmDate"]
    cf.AlarmAtAlarmTime.value = request.json["AlarmTime"]
    cf.AlarmAtAlarmInterface.value = request.json["AlarmInterface"]
    cf.AlarmAtAlarmSource.value = request.json["AlarmSource"]
    cf.AlarmAtAlarmValue.value = request.json["AlarmValue"]
    cf.AlarmAtAlarmName.value = request.json["AlarmName"]
    cf.AlarmAtAlarmDescription.value = request.json["AlarmDescription"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/alarm_monitoring/email_notification", methods=['GET'])
def configuration_alarm_monitoring_email_notification():
    return jsonify({
        "EmailNotificationEnable": cf.EmailNotificationEn,
        "EmailTo" : cf.EmailTo,
        "EmailCC" : cf.EmailCC,
        "EmailFrom" : cf.EmailFrom,
        "EmailSubject" : cf.EmailSubject,
        "EmailMsgHeader" : cf.EmailMsgHeader,
        "EmailMsgTrailer" : cf.EmailMsgTrailer,
        "EmailFormat": cf.EmailFormat,
        "smtpRoot"   : cf.smtpRoot,
        "smtpMailhub": cf.smtpMailhub,
        "smtpRewriteDomain" : cf.smtpRewriteDomain,
        "smtpHostname" : cf.smtpHostname,
        "smtpFromLineOverride": cf.smtpFromLineOverride,
        "smtpUseTLS" : cf.smtpUseTLS,
        "smtpUseSTARTTLS" : cf.smtpUseSTARTTLS,
        "smtpTLSCert" : cf.smtpTLSCert,
        "smtpTLSKey" : cf.smtpTLSKey,
        "smtpTLS_CA_File" : cf.smtpTLS_CA_File,
        "smtpTLS_CA_Dir" : cf.snmpTLS_CA_Dir,
        "smtpAuthUser" : cf.smtpAuthUser,
        "smtpAuthPass" : cf.smtpAuthPass,
        "smtpAuthMethod" : cf.smtpAuthMethod
    })

@app.route("/configuration/alarm_monitoring/email_notification", methods=['POST'])
def configuration_alarm_monitoring_email_notification_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.EmailNotificationEn.value = request.json["EmailNotificationEnable"]
    cf.EmailTo.value = request.json["EmailTo"]
    cf.EmailCC.value = request.json["EmailCC"]
    cf.EmailFrom.value = request.json["EmailFrom"]
    cf.EmailSubject.value = request.json["EmailSubject"]
    cf.EmailMsgHeader.value = request.json["EmailMsgHeader"]
    cf.EmailMsgTrailer.value = request.json["EmailMsgTrailer"]
    cf.EmailFormat.value = request.json["EmailFormat"]
    cf.smtpRoot.value = request.json["smtpRoot"  ]
    cf.smtpMailhub.value = request.json["smtpMailhub"]
    cf.smtpRewriteDomain.value = request.json["smtpRewriteDomain"]
    cf.smtpHostname.value = request.json["smtpHostname"]
    cf.smtpFromLineOverride.value = request.json["smtpFromLineOverride"]
    cf.smtpUseTLS.value = request.json["smtpUseTLS"]
    cf.smtpUseSTARTTLS.value = request.json["smtpUseSTARTTLS"]
    cf.smtpTLSCert.value = request.json["smtpTLSCert"]
    cf.smtpTLSKey.value = request.json["smtpTLSKey"]
    cf.smtpTLS_CA_File.value = request.json["smtpTLS_CA_File"]
    cf.snmpTLS_CA_Dir.value = request.json["smtpTLS_CA_Dir"]
    cf.smtpAuthUser.value = request.json["smtpAuthUser"]
    cf.smtpAuthPass.value = request.json["smtpAuthPass"]
    cf.smtpAuthMethod.value = request.json["smtpAuthMethod"]

    cf.save(cfg_file)
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/alarm_monitoring/http_notification", methods=['GET'])
def configuration_alarm_monitoring_http_notification():
    return jsonify({
        "httpPostNotificationEnable" : cf.httpPostNotificationEn,
        "httpPostURL": cf.httpPostURL
    })

@app.route("/configuration/alarm_monitoring/http_notification", methods=['POST'])
def configuration_alarm_monitoring_http_notification_post():
    if not request.is_json:
        return "Unsupported Media Type", 415
    
    cf.httpPostNotificationEn.value = request.json["httpPostNotificationEnable"]
    cf.httpPostURL.value = request.json["httpPostURL"]

    cf.save(cfg_file)
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/alarm_monitoring/snmp_notification", methods=['GET'])
def configuration_alarm_monitoring_snmp_notification():
    return jsonify({
        "SNMPNotificationEnable": cf.SNMPNotificationEn,
        "snmpManagerIP": cf.snmpManagerIP,
        "snmpNotificationType": cf.snmpNotificationType,
        "snmpv12Community" : cf.snmpv12Community,
        "snmpv3TrapEngineID" : cf.snmpv3TrapEngineID,
        "snmpv3InfEngineID": cf.snmpv3InfEngineID,
        "snmpv3SecurityLevel": cf.snmpv3SecurityLevel,
        "snmpv3SecurityName": cf.snmpv3SecurityName,
        "snmpv3AuthProtocol": cf.snmpv3AuthProtocol,
        "snmpv3AuthKey": cf.snmpv3AuthKey,
        "snmpv3PrivProtocol": cf.snmpv3PrivProtocol,
        "snmpv3PrivKey": cf.snmpv3PrivKey
    })

@app.route("/configuration/alarm_monitoring/snmp_notification", methods=['POST'])
def configuration_alarm_monitoring_snmp_notification_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.SNMPNotificationEn.value = request.json["SNMPNotificationEnable"]
    cf.snmpManagerIP.value      = request.json["snmpManagerIP"]
    cf.snmpNotificationType.value = request.json["snmpNotificationType"]
    cf.snmpv12Community.value     = request.json["snmpv12Community"]
    cf.snmpv3TrapEngineID.value   = request.json["snmpv3TrapEngineID"]
    cf.snmpv3InfEngineID.value    = request.json["snmpv3InfEngineID"]
    cf.snmpv3SecurityLevel.value  = request.json["snmpv3SecurityLevel"]
    cf.snmpv3SecurityName.value = request.json["snmpv3SecurityName"]
    cf.snmpv3AuthProtocol.value = request.json["snmpv3AuthProtocol"]
    cf.snmpv3AuthKey.value      = request.json["snmpv3AuthKey"]
    cf.snmpv3PrivProtocol.value = request.json["snmpv3PrivProtocol"]
    cf.snmpv3PrivKey.value      = request.json["snmpv3PrivKey"]

    cf.save(cfg_file)
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/alarm_monitoring/syslog_notification", methods=['GET'])
def configuration_alarm_monitoring_syslog_notification():
    return jsonify({
        "RsyslogNotificationEnable": cf.RsyslogNotificationEn,
        "RsyslogServer": cf.RsyslogServer
    })

@app.route("/configuration/alarm_monitoring/syslog_notification", methods=['POST'])
def configuration_alarm_monitoring_syslog_notification_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.RsyslogNotificationEn.value = request.json["RsyslogNotificationEnable"]
    cf.RsyslogServer.value = request.json["RsyslogServer"]

    cf.save(cfg_file)
    return "OK", 201, {"Content-Type": "application/json"}


@app.route("/configuration/inputs_app/general", methods=['GET'])
def configuration_inputs_app_general():
    return jsonify({
        "InputsAppEnable": cf.InputsAppEnable,
        "InputPollInterval": cf.InputPollInterval,
        "InputsRawFileSize": cf.InputsRawFileSize,
        "InputsScript": cf.InputsScript
    })

@app.route("/configuration/inputs_app/general", methods=['POST'])
def configuration_inputs_app_general_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    #print ("Set InputsAppEnable", request.json["InputsAppEnable"], file=sys.stderr)
    
    cf.InputsAppEnable.value = request.json["InputsAppEnable"]
    cf.InputPollInterval.value = request.json["InputPollInterval"]
    cf.InputsRawFileSize.value = request.json["InputsRawFileSize"]
    cf.InputsScript.value = request.json["InputsScript"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/inputs_app/noniso_names", methods=['GET'])
def configuration_inputs_app_noniso_names():
    return jsonify({
        "InputName" : cf.InputName[0:4]
    })

@app.route("/configuration/inputs_app/noniso_names", methods=['POST'])
def configuration_inputs_app_noniso_names_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    arr = cf.InputName.value
    new_values = request.json["InputName"][0:4]
    arr[0:4] = new_values
    cf.InputName.value = arr
    
    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/inputs_app/iso_names", methods=['GET'])
def configuration_inputs_app_iso_names():
    r = []
    for i in [(4,11), (12,19), (20,27), (28,35)]:
        try:
            a = {
                "SelectGroup": "%s-%s" % (i[0], i[1]),
                "IndexedIn": cf.InputName[i[0]:i[1]+1]
            }
            r.append(a)
        except Exception as e:
            app.logger.debug ("Got error in seting iso_names (%s), skiping..." % e)
            
    return jsonify({
        "Groups": r
    })

@app.route("/configuration/inputs_app/iso_names", methods=['POST'])
def configuration_inputs_app_iso_names_post():
    validateJson(request, ["SelectGroup", "IndexedIn"])

    group =[int(i) for i in request.json["SelectGroup"].split('-')]
    if len(group) != 2:
        app.logger.warning("Bad SelectGroup %s" % request.json["SelectGroup"])
        return "Expectation Failed", 417, {"Content-Type": "application/json"}
    
    arr = cf.InputName.value
    if len(request.json["IndexedIn"]) != (group[1]-group[0]+1):
        app.logger.warning("Bad IndexedIn %s, expecting %s records" %
                           (request.json["IndexedIn"], (group[1]-group[0]+1)))
        return "Expectation Failed", 417, {"Content-Type": "application/json"}
        
    arr[group[0]:group[1]] = request.json["IndexedIn"]

    cf.InputName.value = arr
    cf.save(cfg_file)
                           
    return "OK", 201, {"Content-Type": "application/json"}
 
@app.route("/configuration/inputs_app/alarm_definitions", methods=['GET'])
def configuration_inputs_app_alarm_definitions():
    def scriptNameOrEmpty(cond):
        values = ["none", "alarm", "script"]
        r = []
        for i in cond:
            try:
                if i.split(',')[6].strip().lower() not in values:
                    r.append(i.split(',')[6].strip())
                else:
                    r.append("")
            except Exception as e:
                r.append("")
                app.logger.warning ("scriptNameOrEmpty: wrong value [%s], error %s" % (i, e))

        return r
        
    r = []
    for i in [(0,9), (10,19), (20,29), (30,39), (40,49), (50,59), (60,69), (70,79)]:
        try:
            a = {
                "SelectGroup": "%s-%s" % (i[0], i[1]),
                "IndexedCond": cf.InputCondition[i[0]:i[1]+1],
                "IndexedScript": scriptNameOrEmpty(cf.InputCondition[i[0]:i[1]+1])
            }
            r.append(a)
        except Exception as e:
            app.logger.debug ("Got error in seting alarm_definitions (%s), skiping..." % e)

    return jsonify({
        "Groups": r
    })

@app.route("/configuration/inputs_app/alarm_definitions", methods=['POST'])
def configuration_inputs_app_alarm_definitions_post():
    validateJson(request, ["SelectGroup", "IndexedCond", "IndexedScript"])

    group =[int(i) for i in request.json["SelectGroup"].split('-')]
    if len(group) != 2:
        app.logger.warning("Bad SelectGroup %s" % request.json["SelectGroup"])
        return "Expectation Failed", 417, {"Content-Type": "application/json"}
    
    arr = cf.InputCondition.value
    if len(request.json["IndexedCond"]) != (group[1]-group[0]+1):
        app.logger.warning("Bad IndexedCond %s, expecting %s records" %
                           (request.json["IndexedCond"], (group[1]-group[0]+1)))
        return "Expectation Failed", 417, {"Content-Type": "application/json"}
        
    arr[group[0]:group[1]] = request.json["IndexedCond"]

    cf.InputCondition.value = arr
    cf.save(cfg_file)
                           
    return "OK", 201, {"Content-Type": "application/json"}


@app.route("/configuration/inputs_app/parser", methods=['GET'])
def configuration_inputs_app_parser():
    (code, stdout, stderr) = wb.callApplication("config_inputs")
    if code != 0:
        app.logger.warning("config_inputs failed, code %s, error %s, output %s" %
                           (code, stderr, stdout))
        return "Forbidden", 403, {"Content-Type": "application/json"}
    
    return jsonify({
        "InputsParser" : stdout.splitlines()
    })

@app.route("/configuration/outputs_app/general", methods=['GET'])
def configuration_outputs_app_general():
    return jsonify({
        "OutputAppEnable": cf.OutputsAppEnable,
        "OutputPollInterval": cf.OutputPollInterval,
        "OutputsRawFileSize": cf.OutputsRawFileSize,
    })

@app.route("/configuration/outputs_app/general", methods=['POST'])
def configuration_outputs_app_general_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.OutputsAppEnable.value = request.json["OutputAppEnable"]
    cf.OutputPollInterval.value = request.json["OutputPollInterval"]
    cf.OutputsRawFileSize.value = request.json["OutputsRawFileSize"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/outputs_app/output_names", methods=['GET'])
def configuration_outputs_app_output_names():
    return jsonify({
        "OutputName" : cf.OutputName
    })

@app.route("/configuration/outputs_app/output_names", methods=['POST'])
def configuration_outputs_app_output_names_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.OutputName.value = request.json["OutputName"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/outputs_app/output_default", methods=['GET'])
def configuration_outputs_app_output_default():
    return jsonify({
        "OutputDefault" : cf.OutputDefault
    })

@app.route("/configuration/outputs_app/output_default", methods=['POST'])
def configuration_outputs_app_output_default_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.OutputDefault.value = request.json["OutputDefault"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/outputs_app/parser", methods=['GET'])
def configuration_outputs_app_parser():
    (code, stdout, stderr) = wb.callApplication("config_outputs")
    if code != 0:
        app.logger.warning("config_outputs failed, code %s, error %s, output %s" %
                           (code, stderr, stdout))
        return "Forbidden", 403, {"Content-Type": "application/json"}
        
    return jsonify({
        "OutputsParser" :stdout.splitlines()
    })

@app.route("/configuration/analogs_app/general", methods=['GET'])
def configuration_analogs_app_general():
    return jsonify({
        "AnalogsAppEnable" :  cf.AnalogsAppEnable,
        "AnalogPollInterval": cf.AnalogPollInterval,
        "AnalogsRawFileSize": cf.AnalogsRawFileSize,
        "AnalogsAlarmFileSize": cf.AnalogsAlarmFileSize,
        "AnalogsScript": cf.AnalogsScript
     })

@app.route("/configuration/analogs_app/general", methods=['POST'])
def configuration_analogs_app_general_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    #print ("Set cf.AnalogsAppEnable.value to %s" % request.json["AnalogsAppEnable"],
    #       type(request.json["AnalogsAppEnable"]),
    #       file=sys.stderr)
    cf.AnalogsAppEnable.value = request.json["AnalogsAppEnable"]
    cf.AnalogPollInterval.value = request.json["AnalogPollInterval"]
    cf.AnalogsRawFileSize.value = request.json["AnalogsRawFileSize"]
    cf.AnalogsAlarmFileSize.value = request.json["AnalogsAlarmFileSize"]
    cf.AnalogsScript.value = request.json["AnalogsScript"]
    
    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/analogs_app/analog_names", methods=['GET'])
def configuration_analogs_app_analog_names():
    return jsonify({
        "AnalogName": cf.AnalogName
     })

@app.route("/configuration/analogs_app/analog_names", methods=['POST'])
def configuration_analogs_app_analog_names_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.AnalogName.value = request.json["AnalogName"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}


@app.route("/configuration/analogs_app/analog_offsets", methods=['GET'])
def configuration_analogs_app_analog_offsets():
    return jsonify({
        "AnalogCalOffset": cf.AnalogCalOffset
     })

@app.route("/configuration/analogs_app/analog_offsets", methods=['POST'])
def configuration_analogs_app_analog_offsets_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.AnalogCalOffset.value = request.json["AnalogCalOffset"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/analogs_app/analog_converters", methods=['GET'])
def configuration_analogs_app_analog_converters():
    return jsonify({
        "AnalogConverter": cf.AnalogConverter
     })

@app.route("/configuration/analogs_app/analog_converters", methods=['POST'])
def configuration_analogs_app_analog_converters_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.AnalogConverter.value = request.json["AnalogConverter"]

    cf.save(cfg_file)

    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/analogs_app/alarm_definitions", methods=['GET'])
def configuration_analogs_app_alarm_definitions():
    def scriptNameOrEmpty(cond):
        values = ["none", "alarm", "script"]
        r = []
        for i in cond:
            try:
                if i.split(',')[6].strip().lower() not in values:
                    r.append(i.split(',')[6].strip())
                else:
                    r.append("")
            except Exception as e:
                r.append("")
                app.logger.warning ("scriptNameOrEmpty: bad value [%s], error %s" % (i, e))

        return r
    
    r = []
    for i in [(0,5), (6,11), (12,17), (18,23)]:
        try:
            a = {
                "SelectGroup": "%s-%s" % (i[0], i[1]),
                "IndexedCond": cf.AnalogCondition[i[0]:i[1]+1],
                "IndexedScript": scriptNameOrEmpty(cf.InputCondition[i[0]:i[1]+1])
            }
            r.append(a)
        except Exception as e:
            app.logger.debug ("Got error in seting alarm_definitions (%s), skiping..." % e)

    return jsonify({
        "Groups": r
    })


@app.route("/configuration/analogs_app/alarm_definitions", methods=['POST'])
def configuration_analogs_app_alarm_definitions_post():
    validateJson(request, ["SelectGroup", "IndexedCond", "IndexedScript"])

    group =[int(i) for i in request.json["SelectGroup"].split('-')]
    if len(group) != 2:
        app.logger.warning("Bad SelectGroup %s" % request.json["SelectGroup"])
        return "Expectation Failed", 417, {"Content-Type": "application/json"}
    
    arr = cf.AnalogCondition.value
    if len(request.json["IndexedCond"]) != (group[1]-group[0]+1):
        app.logger.warning("Bad IndexedCond %s, expecting %s records" %
                           (request.json["IndexedCond"], (group[1]-group[0]+1)))
        return "Expectation Failed", 417, {"Content-Type": "application/json"}
        
    arr[group[0]:group[1]] = request.json["IndexedCond"]

    cf.AnalogCondition.value = arr
    cf.save(cfg_file)
                           
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/analogs_app/parser", methods=['GET'])
def configuration_analogs_app_parser():
    (code, stdout, stderr) = wb.callApplication("config_analogs")
    if code != 0:
        app.logger.warning("config_analogs failed, code %s, error %s, output %s" %
                           (code, stderr, stdout))
        return "Forbidden", 403, {"Content-Type": "application/json"}
    
    return jsonify({
        "AnalogsParser" : stdout.splitlines()
    })


@app.route("/configuration/1wire_app/general", methods=['GET'])
def configuration_1wire_app_general():
    return jsonify({
        "Wire1AppEnable" :  cf.OneWireAppEnable,
        "Wire1PollInterval" : cf.OneWirePollInterval,
        "Wire1AlarmFileSize": cf.OneWireAlarmFileSize,
        "Wire1Script": cf.OneWireScript
      })

@app.route("/configuration/1wire_app/general", methods=['POST'])
def configuration_1wire_app_general_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.OneWireAppEnable.value = request.json["Wire1AppEnable"]
    cf.OneWirePollInterval.value = request.json["Wire1PollInterval"]
    cf.OneWireAlarmFileSize.value = request.json["Wire1AlarmFileSize"]
    cf.OneWireScript.value = request.json["Wire1Script"]

    cf.save(cfg_file)

    return "OK", 201, {"Content-Type": "application/json"}


@app.route("/configuration/1wire_app/alarm_definitions", methods=['GET'])
def configuration_1wire_app_alarm_definitions():

    return jsonify({
        "Wire1DeviceName" :  cf.OneWireDeviceName,
        "Wire1DeviceID" : cf.OneWireDeviceID,
        "Wire1UoM" : cf.OneWireUoM,
        "Wire1RawFileSize" : cf.OneWireRawFileSize,
        "Wire1Scripts" :  cf.OneWireScripts,
        "Wire1Condition" : cf.OneWireCondition,
        "Wire1Script" : cf.OneWireScript,
    })

@app.route("/configuration/1wire_app/alarm_definitions", methods=['POST'])
def configuration_1wire_app_alarm_definitions_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    app.logger.info("GOT JSON for _alarm_definitions_post ")
    cf.OneWireDeviceName.value = request.json["Wire1DeviceName"]
    cf.OneWireDeviceID.value = request.json["Wire1DeviceID"]
    cf.OneWireUoM.value = request.json["Wire1UoM"]
    cf.OneWireRawFileSize.value = request.json["Wire1RawFileSize"]
    cf.OneWireScripts.value = request.json["Wire1Scripts"]
    cf.OneWireCondition.value = request.json["Wire1Condition"]
    cf.OneWireScript.value = request.json["Wire1Script"]

    app.logger.warning("cf.OneWireScripts:%s" % cf.OneWireScripts.value)
    app.logger.warning("COND: %s" % cf.OneWireCondition.value)
    app.logger.warning("RECV: %s" % request.json["Wire1Condition"])
    
    cf.save(cfg_file)

    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/1wire_app/parser", methods=['GET'])
def configuration_1wire_app_parser():
    (code, stdout, stderr) = wb.callApplication("config_1wire")
    if code != 0:
        app.logger.warning("config_1wires failed, code %s, error %s, output %s"
                           % (code, stderr, stdout))
        return "Forbidden", 403, {"Content-Type": "application/json"}
    
    return jsonify({
        "Wire1Parser": stdout.splitlines()
    })

@app.route("/configuration/rs232_app/general", methods=['GET'])
def configuration_rs232_app_general():
    return jsonify({
        "SerialAppEnable" : cf.SerialsAppEnable,
        "SerialAlarmFileSize": cf.SerialAlarmFileSize,
        "SerialScript": cf.SerialScript
    })

@app.route("/configuration/rs232_app/general", methods=['POST'])
def configuration_rs232_app_general_post():
    if not request.is_json:
        return "Unsupported Media Type", 415
    
    cf.SerialsAppEnable.value = request.json["SerialAppEnable"]
    cf.SerialAlarmFileSize.value = request.json["SerialAlarmFileSize"]
    cf.SerialScript.value = request.json["SerialScript"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/rs232_app/device_configuration", methods=['GET'])
def configuration_rs232_app_device_configuration():
    return jsonify({
        #"SelectPort":
        "SerialName" : cf.SerialName,
        "SerialMode" : cf.SerialMode,
        "SerialPortSetting" : cf.SerialPortSetting,
        "SerialSSHPort" : cf.SerialSSHPort,
        "Serial2IP" : cf.Serial2IP,
        "IP2Serial" : cf.IP2Serial,
        "SerialRawFileSize" : cf.SerialRawFileSize,
        "SerialScript" : cf.SerialScript
    })

@app.route("/configuration/rs232_app/device_configuration", methods=['POST'])
def configuration_rs232_app_device_configuration_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.SerialName.value = request.json["SerialName"]
    cf.SerialMode.value = request.json["SerialMode"]
    cf.SerialPortSetting.value = request.json["SerialPortSetting"]
    cf.SerialSSHPort.value = request.json["SerialSSHPort"]
    cf.Serial2IP.value = request.json["Serial2IP"]
    cf.IP2Serial.value = request.json["IP2Serial"]
    cf.SerialRawFileSize.value = request.json["SerialRawFileSize"]
    cf.SerialScript.value = request.json["SerialScript"]
        
    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}


@app.route("/configuration/rs232_app/alarm_definitions", methods=['GET'])
def configuration_rs232_app_alarm_definition():
    return jsonify({
        #"SelectPort":
        "Condition" : cf.Condition,
        "SerialScript" : cf.SerialScript
    })

@app.route("/configuration/rs232_app/alarm_definitions", methods=['POST'])
def configuration_rs232_app_alarm_definition_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.Condition.value = request.json["Condition"]
    cf.SerialScript.value = request.json["SerialScript"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/rs232_app/parser", methods=['GET'])
def configuration_rs232_app_parser():
    (code, stdout, stderr) = wb.callApplication("config_rs232")
    if code != 0:
        app.logger.warning("config_rs232 failed, code %s, error %s, output %s" %
                           (code, stderr, stdout))
        return "Forbidden", 403, {"Content-Type": "application/json"}

    return jsonify({
        "RS232Parser": stdout.splitlines()

    })

@app.route("/configuration/rs485_app/general", methods=['GET'])
def configuration_rs485_app_general():
    return jsonify({
        "RS485AppEnable" : cf.RS485AppEnable,
        "RS485PollInterval" : cf.RS485PollInterval,
        "RS485AlarmFileSize" : cf.RS485AlarmFileSize,
        "RS485Script" : cf.RS485Script
      })

@app.route("/configuration/rs485_app/general", methods=['POST'])
def configuration_rs485_app_general_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.RS485AppEnable.value = request.json["RS485AppEnable"]
    cf.RS485PollInterval.value = request.json["RS485PollInterval"]
    cf.RS485AlarmFileSize.value = request.json["RS485AlarmFileSize"]
    cf.RS485Script.value = request.json["RS485Script"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/rs485_app/device_configuration", methods=['GET'])
def configuration_rs485_app_device_configuration():
    return jsonify({
        "SelectDevice": "",
        "SelectPort":  "",
        "P0_RS485DeviceName" : cf.P0_RS485DeviceName,
        "P1_RS485DeviceName" : cf.P1_RS485DeviceName,
        "P0_Protocol" : cf.P0_Protocol,
        "P1_Protocol" : cf.P1_Protocol,
        "P0_DeviceID" : cf.P0_DeviceID,
        "P1_DeviceID" : cf.P1_DeviceID,
        "P0_PortSetting" : cf.P0_PortSetting,
        "P1_PortSetting" : cf.P1_PortSetting,
        "P0_RS485RawFileSize" : cf.P0_RS485RawFileSize,
        "P1_RS485RawFileSize" : cf.P1_RS485RawFileSize,
        "P0_RS485Script" : cf.P0_RS485Script,
        "P1_RS485Script" : cf.P1_RS485Script
      })

@app.route("/configuration/rs485_app/device_configuration", methods=['POST'])
def configuration_rs485_app_device_configuration_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    #"SelectDevice": "",
    #"SelectPort":  "",
    cf.P0_RS485DeviceName.value = request.json["P0_RS485DeviceName"]
    cf.P1_RS485DeviceName.value = request.json["P1_RS485DeviceName"]
    cf.P0_Protocol.value = request.json["P0_Protocol"]
    cf.P1_Protocol.value = request.json["P1_Protocol"]
    cf.P0_DeviceID.value = request.json["P0_DeviceID"]
    cf.P1_DeviceID.value = request.json["P1_DeviceID"]
    cf.P0_PortSetting.value = request.json["P0_PortSetting"]
    cf.P1_PortSetting.value = request.json["P1_PortSetting"]
    cf.P0_RS485RawFileSize.value = request.json["P0_RS485RawFileSize"]
    cf.P1_RS485RawFileSize.value = request.json["P1_RS485RawFileSize"]
    cf.P0_RS485Script.value = request.json["P0_RS485Script"]
    cf.P1_RS485Script.value = request.json["P1_RS485Script"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}


@app.route("/configuration/rs485_app/modbus_mapping", methods=['GET'])
def configuration_rs485_app_modbus_mapping():
    return jsonify({
        "P0_ReadData" : cf.P0_ReadData,
        "P1_ReadData" : cf.P1_ReadData,
        "P0_RS485Record" : cf.P0_RS485Record,
        "P1_RS485Record" : cf.P1_RS485Record,
        "*Var" : cf.Var,
        "P0_RS485RecordDescription" : cf.P0_RS485RecordDescription,
        "P1_RS485RecordDescription" : cf.P1_RS485RecordDescription
      })

@app.route("/configuration/rs485_app/modbus_mapping", methods=['POST'])
def configuration_rs485_app_modbus_mapping_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.P0_ReadData.value = request.json["P0_ReadData"]
    cf.P1_ReadData.value = request.json["P1_ReadData"]
    cf.P0_RS485Record.value = request.json["P0_RS485Record"]
    cf.P1_RS485Record.value = request.json["P1_RS485Record"]
    cf.Var.value = request.json["*Var"]
    cf.P0_RS485RecordDescription.value = request.json["P0_RS485RecordDescription"]
    cf.P1_RS485RecordDescription.value = request.json["P1_RS485RecordDescription"]
    
    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/rs485_app/alarm_definitions", methods=['GET'])
def configuration_rs485_app_alarm_definitions():
    return jsonify({
        "P0_RS485ConditionX.Y" : cf.P0_RS485Condition,
        "P1_RS485ConditionX.Y" : cf.P1_RS485Condition,
        "P0_RS485Script": cf.P0_RS485Script,
        "P1_RS485Script": cf.P1_RS485Script
      })

@app.route("/configuration/rs485_app/alarm_definitions", methods=['POST'])
def configuration_rs485_app_alarm_definitions_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.P0_RS485Condition.value = request.json["P0_RS485ConditionX.Y"]
    cf.P1_RS485Condition.value = request.json["P1_RS485ConditionX.Y"]
    cf.P0_RS485Script.value = request.json["P0_RS485Script"]
    cf.P1_RS485Script.value = request.json["P1_RS485Script"]

    cf.save(cfg_file)

    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/rs485_app/parser", methods=['GET'])
def configuration_rs485_app_parser():
    (code, stdout, stderr) = wb.callApplication("config_rs485")
    if code != 0:
        app.logger.warning("config_rs485 failed, code %s, error %s, output %s" %
                           (code, stderr, stdout))
        return "Forbidden", 403, {"Content-Type": "application/json"}

    return jsonify({
        "RS485Parser" :  stdout.splitlines()
      })


@app.route("/configuration/net_app/general", methods=['GET'])
def configuration_net_app_general():
    return jsonify({
        "NetAppEnable" : cf.NetAppEnable,
        "NetAppScript" : cf.NetAppScript
      })

@app.route("/configuration/net_app/general", methods=['POST'])
def configuration_net_app_general_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.NetAppEnable.value = request.json["NetAppEnable"]
    cf.NetAppScript.value = request.json["NetAppScript"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}


@app.route("/configuration/net_app/netapp_configuration", methods=['GET'])
def configuration_net_app_netapp_configuration():
    def array_split(array):
        ret = []
        for i in array:
            t = i.split(',')
            ret.append(t)
            
        return ret

    def build_array(indx, arr):
        ret = []
        for i in arr:
            ret.append(i[indx])
        return ret

    arr = array_split(cf.NetApp.value)

    return jsonify({
        "SelectNetApp" : "",
        "Name" : build_array(0, arr),
        "Mode" : build_array(1, arr),
        "Interface" : build_array(2, arr),
        "Protocol" : build_array(3, arr),
        "Port": build_array(4, arr),
        "NetAppRawFileSize": cf.NetAppRawFileSize,
        "NetAppScript" : cf.NetAppScripts
      })

@app.route("/configuration/net_app/netapp_configuration/<ind>", methods=['POST'])
def configuration_net_app_netapp_configuration_post(ind):
    if not request.is_json:
        return "Unsupported Media Type", 415

    indx = int(ind)
    if indx < 0 or indx > (len(cf.NetApp)+1):
        return 'Bad Request', 400
    
    record = "%s, %s, %s, %s, %s" % (
        request.json["Name"],
        request.json["Mode"],
        request.json["Interface"],
        request.json["Protocol"],
        request.json["Port"])

    arr = cf.NetApp.value
    arr[indx] = record

    cf.NetApp.value = arr
    if "NetAppRawFileSize" in request.json:
        cf.NetAppRawFileSize.value = request.json["NetAppRawFileSize"]
        
    if "NetAppScript" in request.json:
        cf.NetAppScripts.value = request.json["NetAppScript"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/net_app/alarm_definitions", methods=['GET'])
def configuration_net_app_alarm_definitions():
    return jsonify({
        "NetAppConditionX.Y" : cf.NetAppCondition,
        "NetAppScript" : cf.NetAppScripts,
      })

@app.route("/configuration/net_app/alarm_definitions", methods=['POST'])
def configuration_net_app_alarm_definitions_post():
    if not request.is_json:
        return "Unsupported Media Type", 415
    
    cf.NetAppCondition.value = request.json["NetAppConditionX.Y"]
    cf.NetAppScripts.value = request.json["NetAppScript"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/net_app/snmptrap_configuration", methods=['GET'])
def configuration_net_app_snmptrap_configuration():
    try:
        (interface, proto, port) =  cf.SNMPTrapAppReceiverPort.split(',')
    except Exception as e:
        app.logger.warning("Cannot parse SNMPTrapAppReceiverPort [%s], error %s" %
                           (cf.SNMPTrapAppReceiverPort, e))
        (interface, proto, port) = ("", "", "")

    return jsonify({
        "SNMPTrapAppMode" : cf.SNMPTrapAppMode,
        "Interface" : interface,
        "Protocol" : proto,
        "Port" : port,
        "SNMPTrapAppRawFileSize" : cf.SNMPTrapAppRawFileSize,
        "SNMPTrapAppAlarmFileSize": cf.SNMPTrapAppAlarmFileSize
      })

@app.route("/configuration/net_app/snmptrap_configuration", methods=['POST'])
def configuration_net_app_snmptrap_configuration_post():
    if not request.is_json:
        return "Unsupported Media Type", 415
    
    iport = "%s,%s,%s" % (request.json["Interface"],
                          request.json["Protocol"],
                          request.json["Port"])
    cf.SNMPTrapAppReceiverPort.value = iport
    cf.SNMPTrapAppMode.value = request.json["SNMPTrapAppMode"]
    cf.SNMPTrapAppRawFileSize.value = request.json["SNMPTrapAppRawFileSize"]
    cf.SNMPTrapAppAlarmFileSize.value = request.json["SNMPTrapAppAlarmFileSize"]

    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}


@app.route("/configuration/net_app/snmp_alarm_definitions", methods=['GET'])
def configuration_net_app_snmp_alarm_definitions():

    return jsonify({
        "IndexedCond" : cf.SNMPAppCondition,
        #"IndexedScript": cf.IndexedScript 
      })

@app.route("/configuration/net_app/snmp_alarm_definitions", methods=['POST'])
def configuration_net_app_snmp_alarm_definitions_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.SNMPAppCondition.value = request.json["IndexedCond"]
    
    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/net_app/syslog_configuration", methods=['GET'])
def configuration_net_app_syslog_configuration():

    return jsonify({
        "SyslogAppMode" : cf.SyslogAppMode,
        "SyslogAppRawFileSize" : cf.SyslogAppRawFileSize,
        "SyslogAppAlarmFileSize": cf.SyslogAppAlarmFileSize,
        "SyslogAppLogEnable" : cf.SyslogAppLogEnable
      })

@app.route("/configuration/net_app/syslog_configuration", methods=['POST'])
def configuration_net_app_syslog_configuration_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.SyslogAppMode.value = request.json["SyslogAppMode"]
    cf.SyslogAppRawFileSize.value = request.json["SyslogAppRawFileSize"]
    cf.SyslogAppAlarmFileSize.value = request.json["SyslogAppAlarmFileSize"]

    #print("Got %s" % request.json["SyslogAppLogEnable"], file=sys.stderr)
    cf.SyslogAppLogEnable.value = request.json["SyslogAppLogEnable"]
    
    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/net_app/syslog_alarm_definitions", methods=['GET'])
def configuration_net_app_syslog_alarm_definitions():

    return jsonify({
        "IndexedCond" : cf.SyslogAppCondition,
        "IndexedScript": ""
      })

@app.route("/configuration/net_app/syslog_alarm_definitions", methods=['POST'])
def configuration_net_app_syslog_alarm_definitions_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.SyslogAppCondition.value = request.json["IndexedCond"]
    
    cf.save(cfg_file)
    
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/configuration/net_app/parser", methods=['GET'])
def configuration_net_app_parser():
    (code, stdout, stderr) = wb.callApplication("config_network")
    if code != 0:
        app.logger.debug (stderr)
        app.logger.warning("config_network failed, code %s, error %s, output %s" %
                           (code, stderr, stdout))
        return "Forbidden", 403, {"Content-Type": "application/json"}

    return jsonify({
        "NetAppParser":  stdout.splitlines()
      })

@app.route("/monitor/realtime_data/<device>", methods=['GET'])
def monitor_realtime_data(device):
    def run(device):
        timer = wb.RunTimer(run_timeout)
        start = True
        stop = False
        stop_only = False
        
        def do(pf):
            if device.lower() == "inputs":
                return wb.readInput(start, stop, stop_only, pf)
            elif device.lower() == "outputs":
                return wb.readOutput(start, stop, stop_only, pf)
            elif device.lower() == "analogs":
                return wb.readAnalog(start, stop, stop_only, pf)
            elif device.lower() == "1wire":
                return wb.readOneWire(start, stop, stop_only, pf)
            elif device.lower() == "rs-485":
                return wb.readRS485(start, stop, stop_only, pf)
            elif device.lower() == "rs-232_0":
                return wb.readRS232(0)
            elif device.lower() == "rs-232_1":
                return wb.readRS232(1)
            elif device.lower() == "rs-232_2":
                return wb.readRS232(2)
            elif device.lower() == "rs-232_3":
                return wb.readRS232(3)
            elif device.lower() == "rs-232_4":
                return wb.readRS232(4)
            elif device.lower() == "rs-232_5":
                return wb.readRS232(5)
            elif device.lower() == "rs-232_6":
                return wb.readRS232(6)
            elif device.lower() == "rs-232_7":
                return wb.readRS232(7)
            elif device.lower() == "alarms":
                return wb.readAlarms(alarm_file, pf)
            else:
                raise ValueError(devices)
            

        try:
            pf = None
            (data, pf) = do(pf)
            yield dumps({"RealtimeData": data})
            start = False
            while not timer.isTimeout():
                (data, pf) = do(pf)
                yield dumps({"RealtimeData": data})

            stop = True
            (data, pf) = do(pf)
            return dumps({"RealtimeData": data})
        
        except ValueError:
            raise
        except BlockingIOError:
            return dumps({"RealtimeData": []})
        
        except:
            stop_only = True
            do(None)
            raise
            
    devices = ["inputs", "outputs", "analogs", "1wire", "rs-485",
               "rs-232_0", "rs-232_1", "rs-232_2", "rs-232_3",
               "rs-232_4", "rs-232_5", "rs-232_6", "rs-232_7", "alarms"]
    if device.lower() not in devices:
        return "Bad request", 400

    return Response(stream_with_context(run(device)),  mimetype='application/json')


@app.route("/control/outputs", methods=['GET'])
def control_outputs():

    (output, pf) = wb.readOutput()
    
    return jsonify({
        "CurrentStates" : output,
        "SetOutput": []
      })

@app.route("/control/outputs", methods=['POST'])
def control_outputs_post():
    validateJson(request, ["SetOutput"])

    (o, pf) = wb.readOutput()
    if o is None or len(o) == 0:
        return "Expectation Failed", 417, {"Content-Type": "application/json"}

    app.logger.info("Current output is [%s]" % o)

    output = list(o[0])
    while len(output) < 6:
        output.append("0")

    #"CurrentStates" : output,
    set_output = request.json["SetOutput"]
    if set_output is None or len(set_output) == 0 or len(set_output) > 6:
        app.logger.warning("Wrong SetOutput value [%s]" % set_output)
        return "Forbidden", 403, {"Content-Type": "application/json"}

    need_set = False
    for (i,s) in enumerate(set_output):
        if s.lower() == "off":
            output[i] = "1"
            need_set = True
        elif s.lower() == "on":
            output[i] = "0"
            need_set = True

    if need_set:
        app.logger.info("Set output to [%s]" % output)
        wb.setOutput("".join(output))

    return "OK", 201, {"Content-Type": "application/json"}



@app.route("/control/restart", methods=['POST'])
def control_restart_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    if "NetReset" in request.json and request.json["NetReset"]:
        wb.netReset()

    if "Restart" in request.json and request.json["Restart"]:
        wb.netReset()
    
    if "Reboot" in request.json and request.json["Reboot"]:
        wb.systemReboot()

    if "PowerCycle" in request.json and request.json["PowerCycle"]:
        return jsonify({#::FIXME::
        }, 501

    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/utilities/analog_calibration", methods=['POST'])
def control_analog_calibration_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    #SelectCalibration
    wb.calibrate(request.json["ANx"],
                 request.json["Vin"],
                 request.json["NReadings"],
                 request.json["RInterval"],
                 request.json["NSamples"],
                 request.json["NPoints"],
                 request.json["SInterval"],
                 request.json["CalValue"])

    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/utilities/1wire_discovery", methods=['GET'])
def utilities_1wire_discovery():
    (code, stdout, stderr) = wb.callApplication("cv_discover_1wire")
    if code != 0:
        app.logger.warning("cv_discover_1wire failed, code %s, error %s, output %s" %
                           (code, stderr, stdout))
        return "Forbidden", 403, {"Content-Type": "application/json"}

    return jsonify({
        "Wire1List":  stdout.splitlines()
      })


@app.route("/utilities/modbus_discovery", methods=['POST'])
def utilities_modbus_discovery_post():
    validateJson(request, ["SelectPort", "PortSetting", "SelectAction", "Timeout" ])

    port = request.json["SelectPort"]

    (baud, data, parity, stop) = request.json["PortSetting"].split(',')
    action = request.json["SelectAction"]
    timeout = request.json["Timeout"]

    argc = ["-b", str(baud), "-p", str(parity), "-d", str(data),
            "-s", str(stop), "-t", str(timeout), "P%s" % port]
    
    if action.lower() == "read":
        read = request.json["Read"]
        argc.append("read")
        argc.extend(read.split(' '))
    elif action.lower() == "write":
        write = request.json["Read"]
        argc.append("write")
        argc.extend(write.split(' '))
    elif action.lower() == "search":
        argc.append("search")
    else:
        raise ValueError(action)
    
    (code, out, err) = wb.callApplication("cv_discover_rs485", argc)
    if code == 0:
        return jsonify({"ActionResult": out.splitlines()}, 201, {"Content-Type": "application/json"}
    else:
        return jsonify({"ActionResult": err}, 400, {"Content-Type": "application/json"}

@app.route("/utilities/data_backup", methods=['POST'])
def utilities_data_backup_post():
    validateJson(request, ["Push","Backup"] )

    if request.json["Push"]:
        app.logger.info("Not implemented yet")
        return jsonify({}, 501
    elif request.json["Backup"]:
        wb.runBackup()
        return "OK", 201, {"Content-Type": "application/json"}
    else:
        return "Bad request", 400, {"Content-Type": "application/json"}

@app.route("/utilities/sw_upgrade", methods=['POST'])
def utilities_sw_upgrade_post():
    return jsonify({
        # ::FIXME:: Backup utility???
      }, 501

@app.route("/utilities/file_transfer", methods=['GET'])
def utilities_file_transfer():
    output = []
    for d in dir_list:
        (code, stdout, stderr) = wb.callApplication("ls", ["-l", d], sudo = False, path = "")
        if code != 0:
            app.logger.warning("list dir failed, code %s, error %s, output %s" %
                               (code, stderr, stdout))
        else:
            arr = stdout.decode('utf-8').splitlines()
            arr[0] = d
            output.extend(arr)
            
    return jsonify({
        "FileListing" : output,
    })

@app.route("/utilities/file_transfer", methods=['POST'])
def utilities_file_transfer_post():
    validateJson(request,
                 ["ServerUserID", "ServerUserPW", "ServerIP", "TransferType",
                  "DevicePath", "ServerPath"])
    transfer = request.json["TransferType"].lower()
    if transfer == "none":
        return "OK", 201, {"Content-Type": "application/json"}
    elif transfer.startswith("device"):
        (output, code ) = wb.runSafeCopy(request.json["DevicePath"],
                                          request.json["ServerPath"],
                                          request.json["ServerIP"],
                                          request.json["ServerUserID"],
                                          request.json["ServerUserPW"])
    elif transfer.startswith("server"):
        (output, code ) = wb.runSafeCopy(request.json["ServerPath"],
                                          request.json["DevicePath"],
                                          request.json["ServerIP"],
                                          request.json["ServerUserID"],
                                          request.json["ServerUserPW"])
    else:
        return "Expectation Failed", 417, {"Content-Type": "application/json"}

    return jsonify({
        "TransferActivity": output.splitlines(),
        "TransferStatus" : code
    }, 201

@app.route("/utilities/map_html", methods=['POST'])
def utilities_map_html_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    cf.SiteCoordinates.value = request.json["SiteCoordinates"]

    wb.saveFile(iframe_file, request.json["HtmlCode"])
    
    cf.save(cfg_file)
    return "OK", 201, {"Content-Type": "application/json"}

@app.route("/utilities/snmptraps", methods=['GET'])
def utilities_snmptraps():
    return jsonify({                  
        "ListSNMP": cf.snmpManagerIP
    })

@app.route("/utilities/snmptraps", methods=['POST'])
def utilities_snmptraps_post():
    validateJson(request, ["SelectSNMPManager", "TrapMessage"])

    snmp_manager = request.json["SelectSNMPManager"]
    if snmp_manager not in cf.snmpManagerIP.value:
        return "Expectation Failed", 417, {"Content-Type": "application/json"}

    pos = 0
    try:
        pos = cf.snmpManagerIP.value.index(snmp_manager)
    except Exception as e:
        app.logger.warning("snmp_manager (%s) lookup failed, error %s" %
                           (snmp_manager, e))
        return "Expectation Failed", 417, {"Content-Type": "application/json"}
    
    arec = st.AlarmRecord()
    arec.build(cf, request.json["TrapMessage"])
    
    st.process_snmp(arec, pos,
                    snmp_manager, cf.snmpNotificationType,
                    cf.snmpv12Community,   cf.snmpv3TrapEngineID,
                    cf.snmpv3InfEngineID,  cf.snmpv3SecurityName,
                    cf.snmpv3AuthProtocol, cf.snmpv3AuthKey,
                    cf.snmpv3SecurityLevel,cf.snmpv3PrivProtocol,
                    cf.snmpv3PrivKey, cf.Eth0WANIP)

    return "OK", 201, {"Content-Type": "application/json"}

                           
@app.route("/utilities/engineID", methods=['GET'])
def utilities_engineid():
    return jsonify({
        "snmpv3InfEngineID": cf.snmpv3InfEngineID
      })

@app.route("/utilities/engineID", methods=['POST'])
def utilities_engineid_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    indx = request.json["index"]
    if indx != 0 and indx != 1:
        app.logger.info("Wrong index %s" % indx)
        return 'Bad Request', 400
    
    prefix = "80007440"
    o = "03"
    mac = wb.getMac("eth%s" % indx)

    arr = cf.snmpv3InfEngineID.value
    if len(arr) == 0:
        arr = ["", ""]
    elif len(arr) == 1:
        arr.append("")
    
    arr[indx] = prefix + o + mac.replace(":", "")

    cf.snmpv3InfEngineID.value = arr
    
    cf.save(cfg_file)
    
    return jsonify({"snmpv3InfEngineID": cf.snmpv3InfEngineID}, 201, {"Content-Type": "application/json"}

@app.route("/utilities/ping", methods=['POST'])
def utilities_ping_post():
    if not request.is_json:
        return "Unsupported Media Type", 415

    args = ["-c", "3",  request.json["IPAddress"]]
    try:
        (code, out, err) = wb.callApplication("/bin/ping", args, sudo = False, path = "", timeout = 5)

        return jsonify({
            "out" : out.decode('utf-8').splitlines(),
            "err" : err.decode('utf-8')
        }, 201
    except Exception as e:
        app.logger.warning("Ping error %s" % e)
        return jsonify({
            "out" : "",
            "err" : str(e)
        }, 400 

@app.route("/reports/charts_analogs", methods=['POST'])
def reports_charts_analogs_post():
    return jsonify({
        # ::FIXME:: Backup utility???
      }, 501

@app.route("/reports/charts_1wire", methods=['POST'])
def reports_charts_1wire_post():
    return jsonify({
        # ::FIXME:: Backup utility???
      }, 501

@app.route("/reports/charts_rs485", methods=['POST'])
def reports_charts_rs485_post():
    return jsonify({
        # ::FIXME:: Backup utility???
      }, 501


#@app.route("/<string:name>")
#def redir(name):
#    print(app.root_path + '/static/html/' + name)
#
#    if name.endswith(".htm"):
#        return send_from_directory(app.root_path + '/static/html/', name)
#
#    return send_from_directory(app.root_path + "/static/", name)
