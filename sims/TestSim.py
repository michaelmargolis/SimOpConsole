# Test Sim 

import sys
import os
import time

from multiprocessing import Process, Queue
import traceback

from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtWidgets import QMessageBox

DATA_PERIOD = 50  # ms between updates

slider_increments = (5)*6  # todo for slow moves

import logging
log = logging.getLogger(__name__)

global_queue = Queue()

class Sim():
    def __init__(self, sleep_func, frame, report_state_cb):
        self.frame = frame
        self.report_state_cb = report_state_cb
        self.is_connected = False
        self.name = "Test Sim"
        global global_queue
        self.data_Q = global_queue
        self.sim = None
        self.washout_callback = None

    def __del__(self):
        if self.sim:
            self.sim = None
            print("exiting TestSIm")
    
    def set_norm_factors(self, norm_factors):
        # values for each element that when multiplied will normalize data to a range of +- 1 
        self.norm_factors = norm_factors
    
    def set_state_callback(self, callback):
        self.state_callback = callback

    def load(self, loader):
        self.sim = TestSim()
        self.sim.init_ui(self.frame) 
        self.connect()

    def connect(self, server_addr=None):
        self.is_connected = True
        self.report_state_cb('Test sim is ready')

    def is_connected(self):
        return self.is_connected         

    def run(self):
        print("run")  

    def pause(self):
        print("pause")  
        
    def read(self):
        while self.data_Q.qsize() > 1:
            ignored = self.data_Q.get()
            if ignored == 'exit':
                sys.exit()
        if self.data_Q.qsize() > 0:
            transform = self.data_Q.get()
            if transform == 'exit':
                sys.exit()
            if transform is not None:
                return transform 
    def get_washout_config(self):
        return [0,0,0,0,0,0]
        
    def set_washout_callback(self, callback):
        pass

class Dof_Oscilate():
    # oscilates platform in a given DoF
    def __init__(self, frame_rate, rate_function):
        self.frame_rate = frame_rate
        self.rate_function = rate_function
        self.current_dof = -1 
        self.current_level = 0
        self.do_all_dof = False
        self.state = 0 # 0=0ff, 1=going up, 2=going down,3=returning to center 
    
    def set_dof(self, dof):
        if dof == 6: 
            # here if sequencing through all 6 dof
            self.do_all_dof = True
            dof = 0 # start with x
        self.current_dof = dof
        self.state = 1
        print("dof set to ", dof)
        self.start_time = time.time()
        
    def oscilate(self):
        # rate is time in secs for move from -1 to 1
        dur = (self.rate_function() * 0.0005) + .5
        # print("rate fun=", self.rate_function())
        step =  self.frame_rate / dur
        if self.state == 1:
            self.current_level += step
            if self.current_level > 1:
                self.state = 2
        elif self.state == 2:
            self.current_level -= step
            if self.current_level < -1:
                self.state = 3
        elif self.state == 3:
            self.current_level += step
            if self.current_level >= 0:
                self.state = 0
                print("dur was", time.time() - self.start_time)
                if self.do_all_dof:
                    if self.current_dof < 5:
                        self.current_dof  += 1
                        self.state = 1
                    else:
                        self.do_all_dof = False
             
           
        transform = [0,0,0,0,0,0]    
        if self.current_dof  >= 0 and  self.current_dof < 6:     
            transform[self.current_dof] = self.current_level
            return transform
        elif self.current_dof  > 5:
            print("todo sequential tranforms")
        return [0,0,0,0,0,0]    
            
 
class TestSim(object):
    def __init__(self, frame_rate=0.05):
        self.frame_rate = frame_rate
     
        global global_queue
        self.data_Q = global_queue
        self.timer_data_update = None
        self.is_ready = False # True when platform config is loaded
        self.time_interval = DATA_PERIOD / 1000.0
        self.slider_values = [0]*6  # the actual slider percents (-100 to 100)
        self.lagged_slider_values = [0]*6  # values used for sending to festo
        self.dof_oscilate = None # this is instantiated in init_ui
        
    def init_ui(self, frame):
        self.ui = frame_gui(frame)
        # configures
        self.configure_timers(frame)
        self.configure_signals()
        self.configure_buttons()
        
        self.dof_oscilate = Dof_Oscilate(self.frame_rate, self.ui.sld_lag.value)
    
    def closeEvent(self, event):
       self.data_Q.put("exit")
    
    def configure_timers(self, frame):
        self.timer_data_update = QtCore.QTimer(frame) 
        self.timer_data_update.timeout.connect(self.data_update)
        self.timer_data_update.start(int(DATA_PERIOD / 2)) # run faster than update period

    def configure_signals(self):
        self.ui.btn_centre.clicked.connect(self.centre_pos)
        self.ui.btn_load_pos.clicked.connect(self.load_pos)
        self.ui.cmb_repeated_move.activated.connect(self.move_combo_changed)

    def configure_buttons(self):  
        #  button groups
        self.transfrm_sliders = [self.ui.sld_0, self.ui.sld_1, self.ui.sld_2, self.ui.sld_3, self.ui.sld_4, self.ui.sld_5  ]
        self.lag_indicators = [self.ui.pg_0, self.ui.pg_1, self.ui.pg_2, self.ui.pg_3, self.ui.pg_4, self.ui.pg_5]
        if USE_SPACE_MOUSE:
            self.mouse_rbuttons = [self.ui.rb_m_off, self.ui.rb_m_inc, self.ui.rb_m_abs]
            self.mouse_btn_group = QtWidgets.QButtonGroup()
            for i in range(len(self.mouse_rbuttons)):
               self.mouse_btn_group.addButton(self.mouse_rbuttons[i], i)
               
    def move_combo_changed(self, value):       
        print("combo changed:",  value)
        self.dof_oscilate.set_dof(value-1)
       
    def data_update(self):
        if  self.dof_oscilate and self.dof_oscilate.state > 0:
            transform = self.dof_oscilate.oscilate()
            if self.dof_oscilate.state == 0:
                self.ui.cmb_repeated_move.setCurrentIndex(0)
            
        else:     
            percent_delta = 100.0 / (self.ui.sld_lag.value() / DATA_PERIOD)  # max percent change for each update
            for idx, slider in enumerate(self.transfrm_sliders):
                self.slider_values[idx] = slider.value()
                if not self.ui.chk_instant_move.isChecked():  # moves deferred if checked (todo rename to chk_defer_move)
                    if self.lagged_slider_values[idx] + percent_delta <= self.slider_values[idx]:
                        self.lagged_slider_values[idx] += percent_delta
                    elif self.lagged_slider_values[idx] - percent_delta >=  self.slider_values[idx]:
                        self.lagged_slider_values[idx] -= percent_delta
                    else:
                        self.lagged_slider_values[idx] = self.slider_values[idx]
                if self.lagged_slider_values[idx] ==  self.slider_values[idx]:
                    self.lag_indicators[idx].setValue(1)
                else:
                    self.lag_indicators[idx].setValue(0)
            # print("raw sliders", self.slider_values, "lagged:", self.lagged_slider_values )
            if self.ui.rb_m_inc.isChecked(): 
                self.get_mouse_transform()
                print("not implimented")
            elif self.ui.rb_m_abs.isChecked():
                mouse_xform = self.get_mouse_transform()
                for i in range(len(self.transfrm_sliders)):
                    self.transfrm_sliders[i].setValue( int(mouse_xform[i] * 100))
            transform = [x * .01 for x in self.lagged_slider_values]
        if self.data_Q:
            self.data_Q.put(transform)
  
    def centre_pos(self):
        for slider in self.transfrm_sliders:
            slider.setValue(0)

    def load_pos(self):
        for idx, slider in enumerate(self.transfrm_sliders):
            if( idx == 2):
                slider.setValue(-100)
            else:
                slider.setValue(0)
