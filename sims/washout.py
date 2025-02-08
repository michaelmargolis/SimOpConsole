# derived from https://github.com/harwoodr/motion
# see also: https://github.com/breeswish/hexi

import numpy as np
from scipy import signal
from scipy import constants
import math

class RealtimeFilter():
  #  adopted from: 
  def __init__(self, b, a):
    assert(len(b) == len(a))
    self.n = len(b) # n = order + 1
    self.b = b
    self.a = a
    self.reset()

  def reset(self):
    self.input = np.zeros(self.n, dtype=float)
    self.output = np.zeros(self.n, dtype=float)

  def apply(self, v):
    self.input[self.n - 1] = v
    self.output[self.n - 1] = 0
    output = 0
    for i in range(0, self.n):
      output = output + \
        self.b[i] * self.input[self.n - 1 - i] - \
        self.a[i] * self.output[self.n - 1 - i]
    self.output[self.n - 1] = output
    for i in range(0, self.n - 1):
      self.input[i] = self.input[i+1]
      self.output[i] = self.output[i+1]
    return output

class motionCueing():
    def __init__(self):
        self.tGain = 200 # was 20
        self.rGain = 2 # was 20
        self.yGain = 2 # was 20
        self.freq = 20
        self.omega = 25
        self.zeta = 1
        self.max_translational_acceleration = 10                                     #in m/s^2
        self.max_rotational_velocity = np.deg2rad(30)                               #in deg/s
        self.max_rotational_acceleration = math.sin(np.deg2rad(30)) * constants.g   #in deg/s^2

        #filters
        #tuning will require individial omega/zeta parameters for filters...
        #surge and pitch filters

        self.surge_hp2 = self.secondhp_filter(self.zeta,self.omega)
        self.surge_hp1 = self.firsthp_filter(self.omega)
        self.surge_dint = self.dint_filter()
        self.pitch_hp2 = self.secondhp_filter(1,5)
        self.pitch_sint = self.sint_filter()
        self.sp_tilt_lp = self.firstlp_filter(self.omega)

        #sway and roll filters
        self.sway_hp2 = self.secondhp_filter(self.zeta,self.omega)
        self.sway_hp1 = self.firsthp_filter(self.omega)
        self.sway_dint = self.dint_filter()
        self.roll_hp2 = self.secondhp_filter(1,5)
        self.roll_sint = self.sint_filter()
        self.sr_tilt_lp = self.firstlp_filter(self.omega)

        #heave and yaw filters
        self.heave_hp2 = self.secondhp_filter(self.zeta,self.omega)
        self.heave_hp1 = self.firsthp_filter(self.omega)
        self.heave_dint = self.dint_filter()
        self.yaw_hp2 = self.secondhp_filter(self.zeta,self.omega)
        self.yaw_sint = self.sint_filter()

    #high pass filter - third order
    def thirdhp_filter(self, z,w):
        b=[1,0,0,0]
        a=[1,(2*z*w + w),(w**2 + 2*z*w**2), w**3]
        return RealtimeFilter(*signal.bilinear(b,a,fs=self.freq))

    #low pass filter - first order
    def firstlp_filter(self, w):
        b= [0,w]
        a= [1,w]
        return RealtimeFilter(*signal.bilinear(b,a,fs=self.freq))


    #high pass filter - second order
    def secondhp_filter(self, z,w):
        b=[1,0,0]
        a=[1,2*z*w,w**2]
        return RealtimeFilter(*signal.bilinear(b,a,fs=self.freq))

    def firsthp_filter(self, w):
        b=[1,0]
        a=[1,w]
        return RealtimeFilter(*signal.bilinear(b,a,fs=self.freq))

    #single integrator - 1/s
    def sint_filter(self):
        b= [0,1]
        a= [1,0]
        return RealtimeFilter(*signal.bilinear(b,a,fs=self.freq))

    #double integrator - 1/s**2
    def dint_filter(self):
        b= [0,0,1]
        a= [1,0,0]
        return RealtimeFilter(*signal.bilinear(b,a,fs=self.freq))

    def tilt_scaling(self, scalar):
        return scalar * (self.max_rotational_acceleration / self.max_translational_acceleration)

    def apply_scaling(self, x, max_x, max_y):
        if max_x == 0:
            return 0
        sign = np.sign(x)
        if abs(x) > max_x:
            return sign * max_y
        else:
            return (max_y / max_x) * x

    def apply_movement_scaling(self, scalar):
        return self.apply_scaling(scalar, 3, self.max_translational_acceleration)

    def apply_rotate_scaling(self, scalar):
        return self.apply_scaling(scalar,2, self.max_rotational_velocity)

    def wash(self, transform): # input xlations in g, rotations in radians/sec
        xIn = transform[0] * constants.g # convert g to m/s^2
        xOut = self.tGain*self.apply_movement_scaling(self.surge_dint.apply(self.surge_hp2.apply(self.surge_hp1.apply(xIn))))
 
        yIn = transform[1] * constants.g  
        yOut = self.tGain*self.apply_movement_scaling(self.sway_dint.apply(self.sway_hp2.apply(self.sway_hp1.apply(yIn))))
    
        zIn = transform[2] * constants.g  
        zOut = self.tGain*self.apply_movement_scaling(self.heave_dint.apply(self.heave_hp2.apply(self.heave_hp1.apply(zIn))))
  
        rollIn = transform[3] 
        rollOut = -self.rGain*self.apply_rotate_scaling(self.roll_sint.apply(self.roll_hp2.apply(rollIn)) + self.tilt_scaling(self.sr_tilt_lp.apply(yIn)/constants.g))     
        
        pitchIn = transform[4]
        pitchOut = -self.rGain*self.apply_rotate_scaling(self.pitch_sint.apply(self.pitch_hp2.apply(pitchIn)) + self.tilt_scaling(self.sp_tilt_lp.apply(xIn)/constants.g))
        
        yawIn = transform[5]
        yawOut = self.yGain*self.apply_rotate_scaling(self.yaw_sint.apply(self.yaw_hp2.apply(yawIn)))

        washed = [xOut, yOut, zOut, rollOut, pitchOut, yawOut]
        # print(washed)
        return washed


""" following for testing only """
washout_factor = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
#  washout_time is number of seconds to decay below 2%
washout_time = [12, 12, 12, 12, 0, 12] 
prev_value = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

from copy import deepcopy

def init_regulate(frame_rate):
    for idx, value in enumerate(washout_time):
        if value != 0:
            washout_factor[idx] = 1.0 - frame_rate /  value * 4
    print(washout_factor)
    
def regulate(request):  
    global prev_value
    r =  deepcopy(request)#  np.clip(request, -1, 1, request)  # clip normalized values
    for idx, f in enumerate(washout_factor):
        #  if washout enabled and request is less than prev washed value, decay more
        if prev_value[idx] == 0:
           prev_value[idx] = request[idx]
        if f != 0 and abs(request[idx]) < abs(prev_value[idx]):
            #  here if washout is enabled
            # print("wha", r[idx])
            r[idx] =  prev_value[idx] * washout_factor[idx]
    prev_value = r
    print(r)    
    return r
        

def pulse(wave, period, dur, start_step, step_interval, gain, step ):
    # period, dur  and interval in seconds
    end_step =  start_step + round(dur/step_interval)
    # print(start_step, end_step, step)
    if step >= start_step and step <= end_step:
        elapsed =  (step - start_step) * step_interval
        if wave == 'sin':
            p =  (elapsed / period) * 2 * math.pi
            # print("wha", step, p, math.sin(p))
            return math.sin(p) * gain
        elif wave == 'square':
            if elapsed < period/2:
                return 1
            else:
                return 0        
    else:
        return 0  
 

if __name__ == "__main__":
    import os, sys, time
    RUNTIME_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(os.path.dirname(RUNTIME_DIR))
    from common.plot_itf import PlotItf        
 
    frame_rate = 0.01
    nbr_plots = 6
    traces_per_plot = 2
    titles = ('x (surge)', 'y (sway)', 'z (heave)', 'roll', 'pitch', 'yaw')
    legends = ('transform', 'washed')

    plotter = PlotItf("Transform Washouts", nbr_plots, titles, traces_per_plot, legends=legends,  minmax=(-1,1), grouping= 'traces') 
    mca = motionCueing()

    init_regulate(frame_rate)
    for i in range(500):      
        plots = []
        for p in range (6):
            start =  p*70
            val = pulse('square', 4, 2, start, frame_rate, .5, i)
            plots.append(val)
        washed = mca.wash(plots)  
        regulated = list(regulate(np.array(plots)))
        # print(plots, washed) 
        plotter.plot((plots,washed) )
        # plotter.plot((plots,regulated) )
        time.sleep(.01)