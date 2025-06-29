from common.udp_tx_rx import UdpReceive
import json
import logging

class XplaneTelemetry:
    def __init__(self, addr, norm_factors):
        self.addr = addr  # (ip, port) tuple
        self.send_addr = (addr[0], addr[1] + 1)
        self.norm_factors = norm_factors
        self.telemetry = UdpReceive(addr[1])
        self.last_xyzrpy = None
        self.last_icao = "Aircraft"
        self.save_as_csv = True

    def get_telemetry(self):
        msg = None
        xyzrpy = [0] * 6

        while self.telemetry.available() > 0:
            msg = self.telemetry.get()

        if msg:
            try:
                telemetry_data = json.loads(msg[1])
                # print(telemetry_data
                nf = self.norm_factors
                if telemetry_data["on_ground"] != 0:
                    yaw_factor = nf[5]*.05
                else:
                    yaw_factor = nf[5]                     
                #     nf[5] = nf[5]*.1 # reduce yaw factor when on the ground  
                xyzrpy = [
                    telemetry_data["g_axil"] * nf[0],   # X translation
                    telemetry_data["g_side"] * nf[1],   # Y translation
                    telemetry_data["g_nrml"] * nf[2],   # Z translation
                    # telemetry_data["Prad"] * nf[3],   # Roll rate (angular velocity)
                    telemetry_data["phi"] * nf[3],      # Rollangle   
                    # telemetry_data["Qrad"] * nf[4],   # Pitch rate (angular velocity)
                    telemetry_data["theta"] * nf[4],    # pitch angle 
                    telemetry_data["Rrad"] * yaw_factor      # Yaw rate (angular velocity)
                ]
                self.last_xyzrpy = tuple(xyzrpy)
                self.last_icao = telemetry_data.get("icao", "Aircraft")
                return self.last_xyzrpy        
            except Exception as e: 
                logging.error(f"telemetry format error {e}")
                # raise JSONDecodeError(e)
                
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
