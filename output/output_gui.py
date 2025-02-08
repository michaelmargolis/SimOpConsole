""" output_gui
Copyright Michael Margolis, Middlesex University 2019; see LICENSE for software rights.

display muscle lengths and platform orientation
"""

from PyQt5 import QtCore, QtGui, QtWidgets, uic

import copy
# import time
from math import degrees
import system_config as cfg

ui, base = uic.loadUiType("output_gui.ui")

class frame_gui(QtWidgets.QFrame, ui):
    def __init__(self, parent=None):
        super(frame_gui, self).__init__(parent)
        self.setupUi(self)
        
class OutputGui(object):

    def init_gui(self, frame, MIN_ACTUATOR_LEN , MAX_ACTUATOR_RANGE):
        # self.ui = Ui_Frame()
        # self.ui.setupUi(frame)
        self.ui = frame_gui(frame)
        self.MIN_ACTUATOR_LEN = MIN_ACTUATOR_LEN
        self.MAX_ACTUATOR_RANGE = MAX_ACTUATOR_RANGE
        # self.actuator_bars = [self.ui.pb_0,self.ui.pb_1,self.ui.pb_2,self.ui.pb_3,self.ui.pb_4,self.ui.pb_5]
        self.txt_xforms = [self.ui.txt_xform_0,self.ui.txt_xform_1,self.ui.txt_xform_2,self.ui.txt_xform_3,self.ui.txt_xform_4,self.ui.txt_xform_5]
        self.actuator_bars = [self.ui.muscle_0,self.ui.muscle_1,self.ui.muscle_2,self.ui.muscle_3,self.ui.muscle_4,self.ui.muscle_5]
        self.txt_muscles = [self.ui.txt_muscle_0,self.ui.txt_muscle_1,self.ui.txt_muscle_2,self.ui.txt_muscle_3,self.ui.txt_muscle_4,self.ui.txt_muscle_5]
        self.txt_up_indices = [self.ui.txt_up_idx_0,self.ui.txt_up_idx_1,self.ui.txt_up_idx_2,self.ui.txt_up_idx_3,self.ui.txt_up_idx_4,self.ui.txt_up_idx_5]
        self.txt_down_indices = [self.ui.txt_down_idx_0,self.ui.txt_down_idx_1,self.ui.txt_down_idx_2,self.ui.txt_down_idx_3,self.ui.txt_down_idx_4,self.ui.txt_down_idx_5]
        self.encoder_bars = [self.ui.encoder_0,self.ui.encoder_1,self.ui.encoder_2,self.ui.encoder_3,self.ui.encoder_4,self.ui.encoder_5]
        self.txt_encoder_vals = [self.ui.txt_enc_0,self.ui.txt_enc_1,self.ui.txt_enc_2,self.ui.txt_enc_3,self.ui.txt_enc_4,self.ui.txt_enc_5]
        self.front_pixmap = QtGui.QPixmap('images/front.png')
        self.side_pixmap = QtGui.QPixmap('images/side.png')
        self.top_pixmap = QtGui.QPixmap('images/top.png')
        self.front_pos =  self.ui.lbl_front_view.pos()
        self.side_pos = self.ui.lbl_side_view.pos()
        self.top_pos = self.ui.lbl_top_view.pos()

    def encoders_is_enabled(self):
        return self.ui.rb_encoders.isChecked()

    def encoders_set_enabled(self, state):
        if state:
            self.ui.rb_encoders.setChecked(True)
        else:
            self.ui.rb_manual.setChecked(True)

    def encoder_change_callback(self, callback):
        self.encoder_callback = callback
        self.ui.rb_encoders.toggled.connect(lambda:self.encoder_callback(self.ui.rb_encoders))
        self.ui.rb_manual.toggled.connect(lambda:self.encoder_callback(self.ui.rb_manual))

    def encoder_reset_callback(self, callback):
        self.ui.btn_reset_encoders.clicked.connect(callback)

    def do_transform(self, widget, pixmap, pos,  x, y, angle):
        widget.move(x + pos.x(), y + pos.y())
        xform = QtGui.QTransform().rotate(angle)  # front view: roll
        xformed_pixmap = pixmap.transformed(xform, QtCore.Qt.SmoothTransformation)
        widget.setPixmap(xformed_pixmap)
        # widget.adjustSize()

    def show_transform(self, transform):
        for idx, x in enumerate(transform):
            if idx < 3:
                self.txt_xforms[idx].setText(format("%d" % x))
            else:
                angle = x * 57.3
                self.txt_xforms[idx].setText(format("%0.1f" % angle))
            
        x = int(transform[0] / 4) 
        y = int(transform[1] / 4)
        z = -int(transform[2] / 4)

        self.do_transform(self.ui.lbl_front_view, self.front_pixmap, self.front_pos, y,z, transform[3] * 57.3) # front view: roll
        self.do_transform(self.ui.lbl_side_view, self.side_pixmap, self.side_pos, x,z, transform[4] * 57.3) # side view: pitch
        self.do_transform(self.ui.lbl_top_view, self.top_pixmap, self.top_pos,  y,x, transform[5] * 57.3)  # top view: yaw

    def show_muscles(self, transform, muscles, processing_percent):  # was passing  pressure_percent
        for i in range(6):
           rect =  self.actuator_bars[i].rect()
           width = muscles[i]            
           rect.setWidth(width)
           self.actuator_bars[i].setFrameRect(rect)
           contraction = self.MAX_ACTUATOR_RANGE - width
           self.txt_muscles[i].setText(format("%d mm" % contraction ))
        self.show_transform(transform) 
        #  processing_dur = int(time.time() % 20) # for testing, todo remove
        self.ui.txt_processing_dur.setText(str(processing_percent))
        rect =  self.ui.rect_dur.rect()
        rect.setWidth(max(2*processing_percent,1) )
        if processing_percent < 50:
            self.ui.rect_dur.setStyleSheet("color: rgb(85, 255, 127)")
        elif processing_percent < 75:
            self.ui.rect_dur.setStyleSheet("color: rgb(255, 170, 0)")
        else:
            self.ui.rect_dur.setStyleSheet("color: rgb(255, 0, 0)")
        self.ui.rect_dur.setFrameRect(rect)

    def show_encoders(self, distances):
        for i in range(6):
            self.txt_encoder_vals[i].setText(str(distances[i]))
            rect =  self.encoder_bars[i].rect()
            width = max(distances[i],0)
            rect.setWidth(width)
            self.encoder_bars[i].setFrameRect(rect)

    def normalize(self, item):
        i = 2 * (item - self.MIN_ACTUATOR_LEN) / (self.MAX_ACTUATOR_LEN - self.MIN_ACTUATOR_LEN)
        return i-1
