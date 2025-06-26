# xplane_cfg.py
TELEMETRY_EVT_PORT = 10022
TELEMETRY_CMD_PORT = TELEMETRY_EVT_PORT+1
HEARTBEAT_PORT = 10030
MCAST_GRP = '239.255.1.1'
MCAST_PORT = 49707

norm_factors = [1.2, 1.2, 0.5, -3.0, 2.2, 2] # gain factors for transform, set negative to invert
# washout_time = [12, 12, 12, 0, 0, 0]  #  washout_time is number of seconds to decay below 2%
axis_flip_mask = [1,1,-1,-1,1,1] # negative values flip the axis direction