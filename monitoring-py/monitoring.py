#!/usr/bin/python3
from telnetlib import Telnet
from re import findall
from time import sleep, time
from os import environ
from influxdb import InfluxDBClient

ROUTER = environ["ROUTER_IP_ADDRESS"]
USER = environ["ROUTER_LOGIN_USER"]
PASSWORD = environ["ROUTER_LOGIN_PASSWORD"]
PROMPT = environ["ROUTER_PROMPT"]

DB_NAME = environ["INFLUX_DB_NAME"]
DB_CONTAINER = environ["INFLUX_DB_ADDRESS"]
DB_PORT = environ["INFLUX_DB_PORT"]
DB_USER = environ["INFLUX_DB_USER"]
DB_PASSWORD = environ["INFLUX_DB_PASSWORD"]

MONITORING_INTERVAL = int(environ["MONITORING_INTERVAL"])
BANDWIDTH_SAMPLING_INTERVAL = 1 # 1sec -> bps int(environ["BANDWIDTH_SAMPLING_INTERVAL"])

"""
firmware version
RTX1200 Rev.10.01.65 (Tue Oct 13 12:23:48 2015)
"""

class RTXTelnet:
    """
    RTXTelnet: Telnet wrapper for RTX series
    """

    log = ""

    def __init__(self, router, username, password, port=23, prompt="", timeout=5, wait=0.5):
        self.router = router
        self.username = username
        self.password = password
        self.port = port
        self.prompt = "\r\n" + prompt + "> "
        self.timeout = timeout
        self.wait = wait
        self.connect()

    def connect(self):
        """
        connect(self): Connect to RTX via telnet
        """
        # セッション開通
        self.telnet = Telnet(self.router, port=self.port, timeout=self.timeout)
        self.telnet.read_very_eager() # プロンプトを出す
        self.telnet.write(b"\n") # ←ナマステ!(ﾊﾞｼｯ)今日は無名ログインスンナスンナスンナスンナスンナスンナスンナスンナ
        self.telnet.read_very_eager() # プロンプト飛ばす

        # ユーザー名とパスワードでログインする
        while True:
            pro = self.telnet.read_very_eager().decode()
            self.log += pro
            if pro.endswith(self.prompt):
                break
            elif pro.endswith("\r\nUsername: "):
                self.telnet.write(self.username.encode("ascii") + b"\n")
            elif pro.endswith("\r\nPassword: "):
                self.telnet.write(self.password.encode("ascii") + b"\n")
            sleep(self.wait)

        # ASCIIモードを適用
        self.telnet.write(b"console character ascii\n\n")
        sleep(self.wait * 2)
        while True:
            pro = self.telnet.read_very_eager().decode()
            self.log += pro
            if pro.endswith(self.prompt):
                break

    def disconnect(self):
        """
        disconnect(self): Disconnect from RTX
        """
        self.telnet.write(b"exit\n")
        self.log += self.telnet.read_very_eager().decode()
        self.telnet.close()

    def execute(self, cmd):
        """
        execute(self, cmd): Execute command in RTX
        """
        # プロンプトを用意
        while True:
            pro = self.telnet.read_very_eager().decode()
            self.log += pro
            if pro.endswith(self.prompt):
                break
            if not pro:
                self.telnet.write(b"\n")
            sleep(self.wait)

        # 実行
        self.telnet.write(cmd.encode("ascii") + b"\n")
        sleep(self.wait * 2)
        res = ""
        while True:
            res += self.telnet.read_very_eager().decode()
            if res.endswith(self.prompt):
                self.log += res
                res = res.replace(cmd + " \x08 \x08\r\n", "").replace("---more---\r            \r", "").replace(self.prompt, "")
                break
            elif res.endswith("---more---"):
                self.telnet.write(b" ")
            sleep(self.wait)
        return res

def post_influxdb(dbconn, measurement, field, value):
    request = [
        {
            "measurement": measurement,
            "fields": {
                field: value,
            }
        }
    ]
    print(request)
    dbconn.write_points(request)
    return True

def grep(pattern, text):
    return findall(pattern, text)

def lan_interfaces():
    # RTX1200はLAN1 LAN2 LAN3だった
    return ["1", "2", "3"]

def pp_interfaces(config):
    t = []

    for w in grep(r"pp select (\d+)", config):
        t.append(w)

    return sorted(set(t), key=t.index)

def dhcp_scopes(config):
    t = []

    for w in grep(r"dhcp scope (\d+)", config):
        t.append(w)

    return sorted(set(t), key=t.index)

def lan_interface_speed(config, num):
    val = grep(r"speed lan"+num+r" (\d+\w?)", config)

    if (not val) or (val == 0):
        val = unitstr2num("1000m")

    return val

def unitstr2num(text):
    val = int(grep(r"(\d+)", text)[0])
    unit = text[-1:].lower()

    if unit == "k":
        return int(val * 1000)
    elif unit == "m":
        return int(val * 1000 * 1000)
    else:
        return int(val)

def environment_mon():
    status = TN.execute("show environment")

    # uptime
    uptime = grep(r"Elapsed time from boot: (\d+)days (\d+):(\d+):(\d+)", status)[0]
    days = int(uptime[0])
    hours = int(uptime[1])
    minutes = int(uptime[2])
    seconds = int(uptime[3])
    uptime_sec = days * 24 * 60 * 60 + hours * 60 * 60 + minutes * 60 + seconds
    post_influxdb(DB, "uptime", "sec", uptime_sec)

    # cpu
    post_influxdb(DB, "cpu", "5sec", int(grep(r"(\d+)%\(5sec\)", status)[0]))
    post_influxdb(DB, "cpu", "1min", int(grep(r"(\d+)%\(1min\)", status)[0]))
    post_influxdb(DB, "cpu", "5min", int(grep(r"(\d+)%\(5min\)", status)[0]))

    # memory
    post_influxdb(DB, "memory", "now", int(grep(r"Memory: (\d+)%", status)[0]))

    # packet buffer
    post_influxdb(DB, "packet_buffer", "small", int(grep(r"(\d+)%\(small\)", status)[0]))
    post_influxdb(DB, "packet_buffer", "middle", int(grep(r"(\d+)%\(middle\)", status)[0]))
    post_influxdb(DB, "packet_buffer", "large", int(grep(r"(\d+)%\(large\)", status)[0]))
    post_influxdb(DB, "packet_buffer", "huge", int(grep(r"(\d+)%\(huge\)", status)[0]))

    # temperature
    post_influxdb(DB, "temperature", "now", int(grep(r"Inside Temperature\(C.\): (\d+)", status)[0]))

def nat_mon():
    status = TN.execute("show nat descriptor address")
    if grep(r"(\d+) used.", status):
        value = int(grep(r"(\d+) used.", status)[0])
    else:
        value = -1
    post_influxdb(DB, "nat", "entry", value)

def dhcp_mon(config):
    for i in dhcp_scopes(config):
        status = TN.execute("show status dhcp "+i)
        post_influxdb(DB, "dhcp"+i, "leased", int(grep(r"Leased: (\d+)", status)[0]))
        post_influxdb(DB, "dhcp"+i, "usable", int(grep(r"Usable: (\d+)", status)[0]))

def pp_traffic_mon(config, sec):
    for i in pp_interfaces(config):
        start_time = time()
        status1 = TN.execute("show status pp "+i)
        sleep(sec)
        status2 = TN.execute("show status pp "+i)
        running_time = time() - start_time
        if "Connected" in status1:
            rcv1 = int(grep(r"\[(\d+) octets?\]", status1)[0])
            snd1 = int(grep(r"\[(\d+) octets?\]", status1)[1])
            rcv2 = int(grep(r"\[(\d+) octets?\]", status2)[0])
            snd2 = int(grep(r"\[(\d+) octets?\]", status2)[1])

            post_influxdb(DB, "pp"+i, "receive", (rcv2 - rcv1) / running_time)
            post_influxdb(DB, "pp"+i, "transmit", (snd2 - snd1) / running_time)

            rcv_load = int(grep(r"Load:\s+(\d+).(\d+)%", status1)[0][0]) + int(grep(r"Load:\s+(\d+).(\d+)%", status1)[0][1]) / 10
            snd_load = int(grep(r"Load:\s+(\d+).(\d+)%", status1)[1][0]) + int(grep(r"Load:\s+(\d+).(\d+)%", status1)[1][1]) / 10

            post_influxdb(DB, "pp"+i, "receive_load", rcv_load)
            post_influxdb(DB, "pp"+i, "transmit_load", snd_load)

def lan_traffic_mon(config, sec):
    for i in lan_interfaces():
        start_time = time()
        status1 = TN.execute("show status lan"+i)
        sleep(sec)
        status2 = TN.execute("show status lan"+i)
        running_time = time() - start_time

        bandwidth = lan_interface_speed(config, i)

        snd1 = int(grep(r"\((\d+) octets?\)", status1)[0])
        rcv1 = int(grep(r"\((\d+) octets?\)", status1)[1])
        snd2 = int(grep(r"\((\d+) octets?\)", status2)[0])
        rcv2 = int(grep(r"\((\d+) octets?\)", status2)[1])

        post_influxdb(DB, "lan"+i, "receive", (rcv2 - rcv1) / running_time)
        post_influxdb(DB, "lan"+i, "transmit", (snd2 - snd1) / running_time)

        post_influxdb(DB, "lan"+i, "receive_load", ((rcv2 - rcv1) * 8 / running_time) / bandwidth)
        post_influxdb(DB, "lan"+i, "transmit_load", ((snd2 - snd1) * 8 / running_time) / bandwidth)

def main():
    """
    Main
    """
    while True:
        try:
            config = TN.execute("show config")
            environment_mon()
            nat_mon()
            dhcp_mon(config)
            pp_traffic_mon(config, BANDWIDTH_SAMPLING_INTERVAL)
            lan_traffic_mon(config, BANDWIDTH_SAMPLING_INTERVAL)
        except:
            print("failed to post")
        sleep(MONITORING_INTERVAL)

if __name__ == '__main__':
    TN = RTXTelnet(ROUTER, USER, PASSWORD, prompt=PROMPT, timeout=3, wait=0.2)
    DB = InfluxDBClient(DB_CONTAINER, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)
    main()
