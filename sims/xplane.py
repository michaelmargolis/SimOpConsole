# sim class for X-Plane using XPPython3 Mdx_telemetry and Mdx_controls plugins

import os, sys
import logging
import traceback
import time
from collections import namedtuple
from math import pi, degrees, radians, sqrt

from .xplane_itf import Telemetry
from . import xplane_cfg as config

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.udp_tx_rx import UdpReceive

log = logging.getLogger(__name__)

class Sim():
    """ this class is imported by the motion platform SimInterface """
    def __init__(self, sleep_func, frame, report_state_cb):
        self.frame = frame
        self.report_state_cb = report_state_cb
        self.name = "X-Plane"
        self.prev_yaw = None
        self.x_plane = X_Plane(sleep_func, self.report_state_cb)
        self.norm_factors = self.x_plane.norm_factors
        self.washout_callback = None
    
    def ui_action(self, action):
        if action[-3:] == 'sit':
           print("do situation", action)
           self.x_plane.telemetry.situation(action)      

        elif action[-3:] == 'rep':
            print("do replay", action)
            self.x_plane.telemetry.replay(action)                 
    
    def set_state_callback(self, callback):
        self.report_state_cb = callback
        
    def set_default_address(self, ip_address):
            pass # code may be added here if needed  

    def load(self, loader):
        log.info("Attempting to start sim by executing " + loader)
        os.startfile(loader)
    
    def connect(self, server_addr = None):
        self.x_plane.telemetry.service(self.washout_callback)   

    def is_Connected(self):
        return True  # xplane autoconnects if needed so return True in any state
        
    def get_connection_state(self):
        return self.x_plane.telemetry.get_connection_state()
        
    def run(self):
        self.x_plane.telemetry.run()

    def pause(self):
        self.x_plane.telemetry.pause()
        
    def reset(self):
        self.x_plane.telemetry.reset()
        
    def read(self):
        return self.x_plane.telemetry.service(self.washout_callback)
    
    def set_scenario(self, scenario):
        self.x_plane.telemetry.set_situation(scenario)
        
    def get_washout_config(self):
        return config.washout_time       
        
    def set_washout_callback(self, callback):
        self.washout_callback = callback 

    def fin(self):
        self.xplane.telemetry.fin()

class X_Plane():
    
    def __init__(self, sleep_func,  report_state_cb, interval_ms = 25):
        self.sleep_func = sleep_func
        self.report_state_cb = report_state_cb
        self.interval_ms = interval_ms
        self.is_connected = False  
        self.norm_factors = config.norm_factors # edit xplane_cfg.py to change
        self.selected_flight_situation = None # the file name of the currently selected flight mode
        self.telemetry = Telemetry(self.norm_factors, self.sleep_func, self.report_state_cb) # itf to X-Plane using UDP msgs to XPPython3 gateway        

    def __del__(self):
        pass 

    def run(self):       
        self.telemetry.run()
            
    def pause(self):        
        self.telemetry.pause()
    
    def reset(self):
       self.telemetry.reset()

        
if __name__ == "__main__":
    from time import sleep
    from common.plot_itf import PlotItf
    from washout.washout import motionCueing
    RUNTIME_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(os.path.dirname(RUNTIME_DIR))

    xplane = X_Plane(sleep)
    mca = motionCueing()

       
    plot = 'xform'
    if plot == 'xform':
        nbr_plots = 6
        traces_per_plot = 2
        titles = ('x (surge)', 'y (sway)', 'z (heave)', 'roll', 'pitch', 'yaw')
        legends = ('from xplane', 'washed')
    else:
        nbr_plots =3
        traces_per_plot = 4
        titles = ('axil', 'side', 'normal')
        legends = ('prop', 'aero', 'gear', 'g')

    main_title = "Translations and Rotations from XPlane"  
    plotter = PlotItf(nbr_plots, traces_per_plot, main_title, titles,  legends=legends,  minmax=(-1,1), grouping= 'traces') 
    err = xplane.connect()
    if err:
        print(err)
    else:
        while(1): 
            transform = xplane.telemetry.read(None)      #fixme washout is not implimented!!      
            washed = mca.wash(transform)
            if plot == 'xform':                 
                data = [transform, washed]
            else:    
               data = xplane._get_xlate()
            print("<",data,">")   
            plotter.plot( data)
            sleep(.05)
            
            