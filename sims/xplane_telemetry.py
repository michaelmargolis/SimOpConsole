import json
import logging
from common.udp_tx_rx import UdpReceive

class XplaneTelemetry:
    def __init__(self, addr, telemetry_keys):
        self.addr = addr  # (ip, port)
        self.send_addr = (addr[0], addr[1] + 1)
        self.telemetry_keys = telemetry_keys
        self.air_factors = None
        self.ground_factors = None
        self.telemetry = UdpReceive(addr[1])
        self.last_xyzrpy = None
        self.last_icao = "Aircraft"
        self.save_as_csv = True

    def update_normalization_factors(self, air_factors, ground_factors):
        if len(air_factors) != len(self.telemetry_keys) or len(ground_factors) != len(self.telemetry_keys):
            raise ValueError("Normalization factor lists must match length of telemetry_keys")
        self.air_factors = air_factors
        self.ground_factors = ground_factors

    def get_telemetry(self):
        msg = None
        while self.telemetry.available() > 0:
            msg = self.telemetry.get()

        if msg:
            try:
                telemetry_data = json.loads(msg[1])
                is_on_ground = telemetry_data.get("on_ground", 0) != 0

                norm_factors = self.ground_factors if is_on_ground else self.air_factors
                if norm_factors is None:
                    raise ValueError("Normalization factors have not been set")

                xyzrpy = [
                    telemetry_data[key] * factor
                    for key, factor in zip(self.telemetry_keys, norm_factors)
                ]

                self.last_xyzrpy = tuple(xyzrpy)
                self.last_icao = telemetry_data.get("icao", "Aircraft")
                return self.last_xyzrpy

            except Exception as e:
                logging.error(f"Telemetry processing error: {e}")

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

