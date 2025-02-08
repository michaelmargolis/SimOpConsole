# dynamics (was shape)

import traceback
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets, uic

ui, base = uic.loadUiType("kinematics/dynamics_gui.ui")

class frame_gui(QtWidgets.QFrame, ui):
    def __init__(self, parent=None):
        super(frame_gui, self).__init__(parent)
        self.setupUi(self)

import logging
log = logging.getLogger(__name__)

class Dynamics(object):
    def __init__(self, frame_rate=0.05):
        self.frame_rate = frame_rate
        self.prev_washout_value = [0,0,0,0,0,0]
        self.use_gui = False

    def init_gui(self, frame):
        # self.ui = Ui_Frame()        
        #self.ui.setupUi(frame)
        self.ui = frame_gui(frame)
        self.use_gui = True
        self.intensity_sliders = [self.ui.sld_x_0, self.ui.sld_y_1,self.ui.sld_z_2,self.ui.sld_roll_3,
                                  self.ui.sld_pitch_4,self.ui.sld_yaw_5,self.ui.sld_master_6]
        self.ui.sld_x_0.valueChanged.connect(lambda: self.move_slider_changed(0))
        self.ui.sld_y_1.valueChanged.connect(lambda: self.move_slider_changed(1))
        self.ui.sld_z_2.valueChanged.connect(lambda: self.move_slider_changed(2))
        self.ui.sld_roll_3.valueChanged.connect(lambda: self.move_slider_changed(3))
        self.ui.sld_pitch_4.valueChanged.connect(lambda: self.move_slider_changed(4))
        self.ui.sld_yaw_5.valueChanged.connect(lambda: self.move_slider_changed(5))
        self.ui.sld_master_6.valueChanged.connect(lambda: self.move_slider_changed(6))
        self.ui.btn_reload_dynam.clicked.connect(self.read_config)
        self.ui.btn_save_dynam.clicked.connect(self.save_config)
        self.ui.btn_default_dynam.clicked.connect(self.default_config)
        

        
    def default_config(self):
        # These default values are overwritten with values in config file
        self.gains = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])  # xyzrpy gains
        self.master_gain = 1.0
        if self.use_gui:
            self.update_sliders()
        #  washout_time is number of seconds to decay below 2%
        self.washout_time = [12, 12, 12, 12, 0, 12]        
        self.washout_factor = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])     

    def move_slider_changed(self, sender_id):
        value = self.intensity_sliders[sender_id].value()
        # print "slider", sender_id, "value is ", value *.01
        if sender_id < 6:
            self.gains[sender_id] = float(value) *.01
        elif sender_id == 6:
           self.master_gain =  float(value) *.01 

    def update_sliders(self):
       if self.use_gui:
            for idx, val in enumerate(self.gains):
                self.intensity_sliders[idx].setValue(int(self.gains[idx]*100))
            self.ui.sld_master_6.setValue(int(self.master_gain *100))

    def begin(self, range, config_fname):
        self.range = range
        self.default_config()
        self.config_fname = config_fname
        self.read_config()

    def set_gain(self, idx, value):
        self.gains[idx] = value
        #  print "in shape", idx, " gain set to ", value

    def get_master_gain(self):
        return self.master_gain # range 0 to 1.0

    def set_intensity(self, value):
        #  expects int value between 0 and 150
        if self.use_gui:
            self.ui.sld_master_6.setValue(value)

    def get_intensity(self):
        return self.master_gain # range 0-1.5 (0 to 150%)
        
    def set_washout(self, idx, value): # sets the washout time
        #  expects washout duration (time to decay below 2%)
        #  zero disables washout
        self.washout_time[idx] = value
        if value == 0:
            self.washout_factor[idx] = 0
        else:
            self.washout_factor[idx] = 1.0 - self.frame_rate / value * 4
            #  print "in shape", idx, " washout time set to ", value, "decay factor=", self.washout_factor[idx]

    def get_washouts(self): # returns the configured washout time 
        #  print "in shape", self.washout_time
        return self.washout_time
    
    def get_washed_telemetry(self, telemetry): # returns washed telemetry
        for idx, f in enumerate(self.washout_factor):
            #  if washout enabled and request is less than prev washed value, decay more
            if f != 0 and abs(telemetry[idx]) < abs(self.prev_washout_value[idx]):
                #  here if washout is enabled
                telemetry[idx] =  self.prev_washout_value[idx] * self.washout_factor[idx]
        self.prev_washout_value = telemetry  
        return telemetry        

    
    def regulate(self, request):
    # returns real values adjusted for intensity and washout
        # print request
    
        r = np.multiply(request, self.gains) * self.master_gain
        np.clip(r, -1, 1, r)  # clip normalized values
        #  print "clipped", r
        """ 
        for idx, f in enumerate(self.washout_factor):
            #  if washout enabled and request is less than prev washed value, decay more
            if f != 0 and abs(request[idx]) < abs(self.prev_washout_value[idx]):
                #  here if washout is enabled
                r[idx] =  self.prev_washout_value[idx] * self.washout_factor[idx]
        self.prev_washout_value = r       
        """ 
        #  convert from normalized to real world values
        r = np.multiply(r, self.range)  
        #print "real",r, self.range
        return r

    def read_config(self):
        # in this version we only read gains
        try:
            with open(self.config_fname) as f:
                lines = f.readlines()
                for line in lines:
                    fields = line.split(',')
                    if fields[0] == 'gains':
                       gains = fields[1:]
                       self.gains = np.array([float(i) for i in fields[1:-1]])
                       self.master_gain = float(fields[7])
            log.info("loaded gains from file %s", self.config_fname)
            self.update_sliders()
        except IOError:
            log.warning("Using defaults gains (unable to open gains config file %s)", self.config_fname)

    def save_config(self):
        try:
            with open(self.config_fname, "w") as outfile:
                outfile.write("# saved values for gain and washout\n")
                #generate an array with strings
                arrstr = np.char.mod('%.2f', self.gains)
                gain_str = ','.join(arrstr) + ',' + str(self.master_gain)
                outfile.write("gains," + gain_str)
        except Exception as e: 
            log.error("error saving gains to %s: %s", self.config_fname, e)