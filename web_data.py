import datetime as dt
import subprocess
import select
import shutil
import fcntl
import time
import os

from paramiko import SSHClient
from paramiko import client
from scp import SCPClient

import logging

start_cmd = "Start data"
stop_cmd  = "Stop data"

select_timeout = 4.0
application_timeout = 2
readline_timeout = 0.1

serials = [
    "/tmp/cvnpipes/cvRS232Device0RXExt",
    "/tmp/cvnpipes/cvRS232Device1RXExt",
    "/tmp/cvnpipes/cvRS232Device2RXExt",
    "/tmp/cvnpipes/cvRS232Device3RXExt",
    "/tmp/cvnpipes/cvRS232Device4RXExt",
    "/tmp/cvnpipes/cvRS232Device5RXExt",
    "/tmp/cvnpipes/cvRS232Device6RXExt",
    "/tmp/cvnpipes/cvRS232Device7RXExt"]

def fileLockAcquire(fd, blocking=True):
    ops = fcntl.LOCK_EX
    if not blocking:
        ops |= fcntl.LOCK_NB
    fcntl.flock(fd, ops)
    logging.debug("FD %s is locked" % (fd) )

def fileLockRelease(fd):
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except Exception as e:
        logging.warning("fcntl unlock error: %s" % e)

    logging.debug("FD %s is released" % (fd) )


def __closefd(fd):
    if fd is not None:
        try:
            os.close(fd)
        except:
            pass


def __openPipeNonBlock(path, mode = os.O_RDWR):
    logging.debug("Opening [%s] in Non blocking mode" % path)
    fd  = None
    try:
        fd = os.open(path, mode)
        logging.debug("Fd [%s] opened" % fd)
        if fd == -1 or fd is None:
            raise Exception("Cannot open file, fd is -1")
        
        fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
        logging.debug("Fd [%s] is in NON blocking mode" % fd)

    except Exception as e:
        logging.debug("Open [%s] failed: Error %s" % (path, e))
        __closefd(fd)
        raise

    return fd
    
def _execute_cmd(path, cmd):
    fd = None
    try:
        fd  = __openPipeNonBlock(path)

        logging.debug("COMMAND: %s" %cmd)
        os.write(fd,cmd.encode())
    except Exception as e:
        logging.debug("Execute [%s: %s]: Error %s" % (path, cmd, e))
    finally:
        __closefd(fd)


def _start(path):
    _execute_cmd(path, start_cmd)

def _stop(path):
    try:
        _execute_cmd(path, stop_cmd)
    except Exception as e:
        logging.debug("Execute [%s: %s]: Error %s" % (path, cmd, e))
        
def _getData(cmdpath, datapath, start, stop, stop_only, pipe = None, use_flock = True):
    logging.debug("GetData: [%s: %s], start %s, stop %s, only %s, lock %s" %
                  (cmdpath, datapath, start, stop, stop_only, use_flock))
    if stop_only:
        _stop(cmdpath)
        return ([], None)

    dt = []
    done = False
    p = None
    if start:
        _start(cmdpath)
    if pipe is None:
        try:
            p = __openPipeNonBlock(datapath)
            if use_flock:
                fileLockAcquire(p, False)
            pf = os.fdopen(p)      
        except Exception as e:
            logging.warning("Got error with fcntl %s, fd %s" % (e, p))
            __closefd(p)
            return ([], None)
    else:
        pf = pipe
        p = pf.fileno()
    try:
        rl, wl, xl = select.select([pf], [], [], select_timeout)
        if rl is None or len(rl) == 0:
            logging.debug("No data from %s for %s sec" % ( datapath, select_timeout) )
        for i in rl:
            while not done:
                lines = i.readlines()
                if lines is not None and len(lines) > 0:
                    dt.extend(lines)
                else:
                    done = True
                logging.debug("Got data from %s: [%s]" % ( datapath, lines) )

        if wl is not None and len(wl) > 0:
            logging.debug("WRITE GOT: %s" % wl)
        if xl is not None and len(xl) > 0:
            logging.debug("EX GOT: %s" % xl)

    finally:
        if stop:
            _stop(cmdpath)
            if use_flock:
                fileLockRelease(p)
            pf.close()
            __closefd(p)
            pf = None

    return (dt, pf)

def _setData(cmdpath, value):
    rl = None
    p = None
    pf = None
    try:
        p = __openPipeNonBlock(cmdpath)
        pf = os.fdopen(p, "w", closefd = False)
        rl, wl, xl = select.select([], [pf], [], select_timeout)
        if wl is None or len(rl) == 0:
            logging.warning("Was not able to write to %s for %s sec" % ( cmdpath, select_timeout) )

        for i in wl:
            logging.debug("Write to %s: [%s]" % (cmdpath, value))
            i.write(value + "\n")
            i.flush()

    except Exception as e:
        logging.warning ("setData error: %s" % e)
        raise

    finally:
        __closefd(p)
        if pf is not None:
            pf.close()
    
    return rl;


def __readlines(pf, hint):
    data = []
    try:
        rl, wl, xl = select.select([pf], [], [], readline_timeout)
        if rl is None or len(rl) == 0:
            logging.debug("Readline: No data for %s sec" % ( readline_timeout) )
        for i in rl:
            lines = i.readlines(hint)
            if lines is not None:
                data.extend(lines)
            logging.debug("Readline: got data: [%s]" % (lines) )

        if wl is not None and len(wl) > 0:
            logging.debug("Readline: WRITE GOT: %s" % wl)
        if xl is not None and len(xl) > 0:
            logging.debug("Readline: EX GOT: %s" % xl)

    except Exception as e:
        logging.warning ("readRS232 error: %s" % e)
        raise
    #finally:
    #    __closefd(fd)

    return data;

def __readline_(fd):
    data = []
    d = ''
    try:
        errs = 0
        while d != b'\n':
            try:
                d =  os.read(fd, 1)
            except Exception as e:
                errs += 1;
                if errs < 10:
                    time.sleep(readline_timeout)
                else:
                    raise e
            d =  os.read(fd, 1)
            if len(d) == 0: # EOF
                break
            if d != b'\n':
                data.append(chr(d[0]))

    except Exception as e:
        logging.warning("Read error: %s" % e)
        #return None

    return ''.join(data)

def readInput(start = True, stop = True, stop_only = False, pipe = None):
    try:
        r = []
        (i, pf) = _getData("/tmp/cvnpipes/cvInputsWebCommand",
                     "/tmp/cvnpipes/cvInputsWebData",
                           start, stop, stop_only, pipe)
        #yyyymmdd, hhmmss, InputState[0..N]
        for l in i:
            if l is not None and len(l) > 0:
                r.append(','.join(l.strip().split(',')[2:]))
        return (r, pf) 
    except Exception as e:
        logging.warning ("readInput error: %s" % e)
        raise
        #return None

def readOutput(start = True, stop = True, stop_only = False, pipe = None):
    try:
        r = []
        (o, pf) = _getData("/tmp/cvnpipes/cvOutputsWebCommand",
                     "/tmp/cvnpipes/cvOutputsWebData",
                           start, stop, stop_only, pipe)
        #yyyymmdd, hhmmss, OutputState[0..N]
        for l in o:
            if l is not None and len(l) > 0:
                r.append(','.join(l.strip().split(',')[2:]))
        return (r, pf)
    except Exception as e:
        logging.warning ("readOutput error: %s" % e)
        raise
        #return None

def setOutput(output):
    try:
        o = _setData("/tmp/cvnpipes/cvOutputsControl",
                     output)
    except Exception as e:
        logging.warning ("setOutput error: %s" % e)
    
def readAnalog(start = True, stop = True, stop_only = False, pipe = None):
    try:
        r = []
        (a, pf) =  _getData("/tmp/cvnpipes/cvAnalogsWebCommand",
                      "/tmp/cvnpipes/cvAnalogsWebData",
                            start, stop, stop_only, pipe)
        #yyyymmdd, hhmmss, Analog0, UoM0, Analog1, UoM1, .., AnalogZ, UoMZ
        for l in a:
            if l is not None and len(l) > 0:
                r.append(','.join(l.strip().split(',')[2:]))
        return (r, pf)
    except Exception as e:
        logging.warning ("readAnalog error: %s" % e)
        raise
        #return None
    
def readOneWire(start = True, stop = True, stop_only = False, pipe = None):
    try:
        r = []
        (w, pf) = _getData("/tmp/cvnpipes/cv1WireWebCommand",
                     "/tmp/cvnpipes/cv1WireWebData",
                           start, stop, stop_only, pipe)
        #yyyymmdd, hhmmss, 1WireDeviceName, Variable, UoM
        for l in w:
            if l is not None and len(l) > 0:
                r.append(','.join(l.strip().split(',')[2:]))
        return (r, pf)
    except Exception as e:
        logging.warning ("readOneWire error: %s" % e)
        raise
        #return None

def readRS485(start = True, stop = True, stop_only = False, pipe = None):
    try:
        r = []
        (w, pf) = _getData("/tmp/cvnpipes/cvRS485WebCommand",
                     "/tmp/cvnpipes/cvRS485WebData",
                           start, stop, stop_only, pipe)
        #yyyymmdd, hhmmss, 1WireDeviceName, Variable, UoM
        for l in w:
            if l is not None and len(l) > 0:
                r.append(','.join(l.strip().split(',')[2:]))
        return (r, pf)
    except Exception as e:
        logging.warning ("readRS485 error: %s" % e)
        raise
        #return None

def readRS232(line):
    if line > len(serials):
        return (None, None)

    ret = []
    pf = None
    fd = None
    try:
        fd = __openPipeNonBlock(serials[line])
        pf = os.fdopen(fd)

        ret = __readlines(pf, 5)
    except Exception as e:
        logging.warning ("readRS232 error: %s" % e)
        raise
    finally:
        __closefd(fd)

    return (ret, None)

def readAlarms(alarm_file, pos = None, timeout = 0.1, count = 5, max_iterations = 10):
    ret = []
    current = pos
    try:
        with open(alarm_file) as f:
            if pos is None:
                f.seek(0,2) #seek to the file end
            else:
                f.seek(pos, 0)
            i = 0
            while i < max_iterations:
                current = f.tell()
                line = f.readline()
                i += 1
                if not line:
                    f.seek(current)
                    logging.debug("No data from %s for %s sec" % (alarm_file, timeout))
                    time.sleep(timeout)
                else:
                    ret.append(line)
    except Exception as e:
        logging.warning ("readAlarms error: %s" % e)
        
    return (ret, current)

def callApplication(appname, args = [], sudo = True, path = "/usr/cvapps/", timeout = None):
    if timeout is None:
        timeout = application_timeout

    cmd = []
    if sudo:
        cmd.append("sudo")
        
    cmd.append(path+appname)

    cmd.extend(args)
    
    r = subprocess.run(cmd, capture_output=True, timeout = timeout)
    return (r.returncode, r.stdout, r.stderr)
    
def lastLogin(username):
    cmd = ["lastlog", "-u"]
  
    cmd.append(username)
    
    r = subprocess.run(cmd, capture_output=True)
    msg = r.stdout.split(b'\n')[1].split()[2:] if r.returncode == 0 else []
    
    return (r.returncode, b" ".join(msg), r.stderr)

def readPipe(pipename, pf = None, stop = False, stop_only = False):
    if stop_only:
        if pf is not None:
            __closefd(pf.fileno())
        return (None, None)
    
    if len(pipename) == 0:
        return (None, None)

    ret = []

    try:
        if pf is None:
            fd = __openPipeNonBlock(pipename)
            pf = os.fdopen(fd)
            
        rl = __readlines(pf, 5)
        ret.append(rl)
    except Exception as e:
        logging.warning ("readPipe error: %s" % e)
    finally:
        if stop and pf is not None:
            __closefd(pf.fileno())
            pf = None

    return (ret, pf)

def setTime(new_date, new_time, local_time = True, use_sudo = True):
    cmd = []
    if use_sudo:
        cmd.append('sudo')
    cmd.extend(["hwclock",  "--set"])
    date_time = "--date=\""
    if new_date is not None:
        date_time += new_date
        if new_time is not None:
            date_time += " "

    date_time += new_time if new_time is not None else ""
    date_time += "\""
    
    cmd.append(date_time)
    if local_time:
        cmd.append("--localtime")

    r = subprocess.run(cmd, capture_output=True, timeout = application_timeout)
    return r.returncode


def saveFile(filename, strings):

    with open(filename, "w") as f:
        for i in strings:
            f.write(i)


def netReset():
    try:
        callApplication("ifconfig", ["eth0", "down"], sudo = True, path = "")
        callApplication("ifconfig", ["eth0", "up"], sudo = True, path = "")
    except Exception as e:
        logging.warning ("netReset error: %s" % e)

    try:
        callApplication("ifconfig", ["eth1", "down"], sudo = True, path = "")
        callApplication("ifconfig", ["eth1", "up"], sudo = True, path = "")
    except Exception as e:
        logging.warning ("netReset eth1 error: %s" % e)

def restart():
    callApplication("systemctl", ["restart", "cvapps.target"], sudo = True, path = "")
    callApplication("systemctl", ["restart", "snmpd"], sudo = True, path = "")
    callApplication("cv_processor_accessstartup.sh", ["restart"],sudo = True)
    callApplication("systemctl", ["restart", "cv_processor_alarm"], sudo = True, path = "")

def systemReboot():
    callApplication("reboot", [], sudo = True, path = "")

def calibrate(anx, vin, nreadings, rinterval, nsamples, npoints, sinterval):
    params = [anx, vin]

    if nreadings is not None:
        params.append(nreadings)
        params.append(rinterval)
        params.append(nsamples)
        params.append(npoints)
        params.append(sinterval)

    callApplication("cv_calibrate_an", params, sudo = True)

def runBackup(folder = "/tmp/cvdata", backups_folder = "/home/cvbackups"):
    base_name = "cvData.tgz"
    remove_ind = 2

    to_remove = "%s/%s.%s" % (backups_folder, base_name, remove_ind)
    try:
        os.remove(to_remove)
    except Exception as e:
        logging.warning ("Got error: %s" % e)
        
    i = remove_ind - 1
    while i >= 0:
        orig = "%s/%s.%s" % (backups_folder, base_name, i) if i >0 else "%s/%s" % (backups_folder, base_name)
        new =  "%s/%s.%s" % (backups_folder, base_name, i+1)
        i -= 1
        try:
            shutil.move(orig, new)
        except Exception as e:
            logging.warning ("runBackup error: %s" % e)


    name = "%s/%s" % (backups_folder, base_name)
    callApplication("tar", ["cfz", name, folder], sudo = False, path = "")

def getMac(interface):
    try:
        mac = open('/sys/class/net/'+interface+'/address').readline()
    except:
        mac = "00:00:00:00:00:00"

    return mac[0:17]

def runSafeCopy(src, dest, server, user, passwd):
    ret = ("OK", "Successful")
    try:
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(client.WarningPolicy)
        ssh.load_system_host_keys()
        #os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
        ssh.connect(server, username=user, password=passwd)
        scp = SCPClient(ssh.get_transport())
        scp.put(src, dest)

        scp.close()
        ssh.close()
    except Exception as e:
        ret = ("%s" %e, "Unsuccessful")
        
    return ret


class RunTimer(object):
    def __init__(self, timeout):
        self.start = dt.datetime.now()
        self.timeout = timeout

    def isTimeout(self):
        return (dt.datetime.now() - self.start).total_seconds() > self.timeout

