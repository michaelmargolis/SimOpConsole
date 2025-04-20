from common.udp_tx_rx import UdpReceive

class XplaneTelemetry:
    def __init__(self, addr, norm_factors):
        self.addr = addr  # (ip, port) tuple
        self.send_addr = (addr[0], addr[1] + 1)
        self.norm_factors = norm_factors
        self.telemetry = UdpReceive(addr[1])
        self.last_xyzrpy = (0, 0, 0, 0, 0, 0)
        self.last_icao = "Aircraft"

    def get_telemetry(self):
        msg = None
        xyzrpy = [0] * 6

        while self.telemetry.available() > 0:
            msg = self.telemetry.get()

        if msg:
            try:
                data = msg[1].split(',')
                if len(data) > 8 and data[0] == 'xplane_telemetry':
                    telemetry = [float(x) for x in data[1:9]]
                    nf = self.norm_factors
                    xyzrpy[0] = telemetry[0] * nf[0]
                    xyzrpy[1] = telemetry[1] * nf[1]
                    xyzrpy[2] = telemetry[2] * nf[2]
                    xyzrpy[3] = telemetry[6] * nf[3]
                    xyzrpy[4] = telemetry[7] * nf[4]
                    xyzrpy[5] = telemetry[5] * nf[5]

                    self.last_xyzrpy = tuple(xyzrpy)

                    if len(data) > 9:
                        self.last_icao = data[9].strip() or "Aircraft"
                    return self.last_xyzrpy
            except Exception as e:
                print(f"Error parsing telemetry: {e}")
        return None

    def get_icao(self):
        return self.last_icao

    def send(self, msg):
        try:
            self.telemetry.send(msg, self.send_addr)
        except Exception as e:
            print(f"Failed to send telemetry command: {e}")

    def close(self):
        self.telemetry.close()
