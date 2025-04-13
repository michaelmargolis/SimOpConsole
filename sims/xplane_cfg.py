# xplane_cfg.py
TELEMETRY_EVT_PORT = 10022
TELEMETRY_CMD_PORT = 10023
HEARTBEAT_PORT = 10030
MCAST_GRP = '239.255.1.1'
MCAST_PORT = 49707

norm_factors = [0.8, 0.8, 0.2, -1.5, 1.5, -1.5] # gain factors for transform, set negative to invert
washout_time = [12, 12, 12, 0, 0, 0]  #  washout_time is number of seconds to decay below 2%
