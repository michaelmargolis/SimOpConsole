import time
import sys
import numpy as np
import logging
import traceback

import output.festo_itf as festo_itf

log = logging.getLogger(__name__)

PLOT_PRESSURES = False

class MuscleOutput(object):
    def __init__(self, d_to_p_func, sleep_func, FST_ip='192.168.0.10', max_muscle_length= 1000, muscle_length_range=250):
        """ Initialize the muscle output control module. """
        self.muscle_length_to_pressure = d_to_p_func
        self.sleep_func = sleep_func
        self.festo = festo_itf.Festo(FST_ip)
        self.MAX_MUSCLE_LENGTH = max_muscle_length
        self.MUSCLE_LENGTH_RANGE = muscle_length_range  # max change in muscle length (not actuator length)
        self.muscle_lengths = [max_muscle_length] * 6 
        self.muscle_percents = [100] * 6
        self.in_pressures = [0] * 6
        self.progress_callback = None
        # self.percent_factor = self.MUSCLE_LENGTH_RANGE / 100  # Divide muscle length by this factor to get percent
        self.is_enabled = False
        self.loaded_payload_weight = 100  # Default payload in kg
        self.prev_time = time.perf_counter()
        self.sent_pressures = [0] * 6
        
        if PLOT_PRESSURES:
            from common.plot_itf import PlotItf
            nbr_plots = 6
            traces_per_plot = 2
            titles = ('Muscle 0', 'Muscle 1', 'Muscle 2', 'Muscle 3', 'Muscle 4', 'Muscle 5')                 
            legends = ('Muscle Length', 'Pressure')
            main_title = "Muscle Length and Pressure Values for Platform Actuators"
            self.plotter = PlotItf(nbr_plots, traces_per_plot, main_title, titles, legends=legends, minmax=(0, 100), grouping='traces')

    def set_progress_callback(self, cb):
        """ Set the progress callback function. """
        self.progress_callback = cb

    def send_pressures(self, pressures):
        """ Send pressure commands to the Festo interface. """
        try:
            self.festo.send_pressures(pressures)
            self.sent_pressures = pressures
        except Exception as e:
            print("error in send pressures", str(e), traceback.format_exc(),pressures)

    def get_pressures(self):
        """ Return actual pressures from Festo, or sent pressures if real values are unavailable. """
        self.in_pressures = self.festo.get_pressure()
        if all(val == 0 for val in self.in_pressures):
            return self.sent_pressures
        else:
            return self.in_pressures
        
    def set_brake(self, state):
        """ Enable or disable brakes to prevent unintended movement. """
        if state:
            print("TODO: Turn brakes on")
        else:
            print("TODO: Turn brakes off")

    def enable_poll_pressures(self, state):
        """ Enable or disable polling of pressure data from the Festo interface. """
        self.festo.enable_poll_pressure(state)

    def set_wait_ack(self, state):
        """ Set whether the system should wait for Festo acknowledgment before proceeding. """
        self.festo.set_wait_ack(state)
        log.debug("MuscleOutput module: wait for Festo pressure set to %d", state)

    def set_piston_flag(self, state):
        """ Enable or disable the piston flag. """
        self.activate_piston_flag = 1 if state else 0

    def set_payload(self, payload_kg):
        """ Set the payload weight in kilograms. """
        self.loaded_payload_weight = payload_kg

    def set_enable(self, state, current_actuator_lengths, target_actuator_lengths):
        """
        enable platform if True, disable if False        
        moves from (if disabled) or to (if enabled) actuator_lengths needed to achieve desired orientation
        """
        #fixme check if passed lengths are muscle lengths
        if self.is_enabled != state:
            self.is_enabled = state
            log.debug("Platform enabled state is %s", str(state))
   
    def get_muscle_lengths(self):
        return self.muscle_lengths
        
    def get_output_status(self):
        #  return string describing output status
        if self.festo.wait:
            if not self.festo.netlink_ok:
                return ("Error: check Festo power and LAN", "red")
            else:
                return (format("Festo network ok (latency=%d ms)" % self.festo.msg_latency), "green")
        else:
           return ("Festo msgs not checked", "orange")
        
        if False:  # enable this to check festo pressures
            ###self._get_pressure()
            if not self.festo.netlink_ok:
                return ("Festo network error (check ethernet cable and festo power)", "red")
            else:    
                bad = []
                in_pressures = self.festo.get_pressure()
                if 0 in in_pressures:
                    for idx, v in enumerate(in_pressures):
                       if v == 0:
                          bad.append(idx)
                    if len(bad) == 6:
                       return ("Festo Pressure Zero on all muscles", "red")
                    else:
                       bad_str = ','.join(map(str, bad))                   
                       return ("Festo Pressure Zero on muscles: " + bad_str, "red")
                elif any(p < 10 for p in self.pressure_percent):
                    return ("Festo Pressure is Low", "orange")
                elif any(p < 10 for p in self.pressure_percent):
                    return ("Festo Pressure is High", "orange")
                else:
                    return ("Festo Pressure is Good", "green")  # todo, also check if pressure is low
        else:        
            return ("Festo controller responses not being used", "orange")

    def prepare_ride_start(self):
        pass

    def prepare_ride_end(self):
        pass

    def do_pressure_plot(self, distances, percents, out_pressures):
        #trace1 = [d/2 for d in distances]
        #trace2 = [p/60 for p in out_pressures]
        # self.plotter.plot([trace1, trace2])  
        plots = []
        for i in range (6):            
            plots.append([distances[i]/2, out_pressures[i]/60])
        self.plotter.plot(plots)  
        """
        percent_deltas = []
        try:
            for idx, p in enumerate(percents):
                percent_deltas.append(self.prev_percents[idx] - p + 50)
            self.prev_percents = percents     
        except Exception as e:
            percent_deltas = [50]*6     
            print(e, traceback.format_exc())            
        percents =  percent_deltas
        """
        """
        prefix = "Strut 0:0;100,Strut 1:0;100,Strut 2:0;100,Strut 3:0;100,Strut 4:0;100,Strut 5:0;100"
       
        trace_data = []      
        for i in range(6):
            plot = []
            plot.append('{}:{}'.format('Distance', str(round(distances[i])/2)))
            plot.append('{}:{}'.format('Pressure', str(round(out_pressures[i]/60))))                  
            trace_data.append(','.join(trace for trace in plot))

        msg = prefix + '#' + ';'.join(trace for trace in trace_data)   
        self.plot_socket.sendto(msg.encode('utf-8'), ('127.0.0.1', 10029))
        # print("in do_pressure_plot sent", msg)
        """
    
    def set_muscle_lengths(self, muscle_lengths):
        """ parm is list of muscle lengths in mm """ 
        try:
            out_pressures = self.muscle_length_to_pressure(muscle_lengths)
            # print("in set_muscle_lengths,", (','.join(str(d) for d in distances)), "pressures,", (','.join(str(p) for p in out_pressures)))
            self.send_pressures(out_pressures)
            self.muscle_lengths = muscle_lengths
        except Exception as e:
            print("error in set_muscle_lengths", str(e), traceback.format_exc(),muscle_lengths)
            log.error("error in set_muscle_lengths %s, %s", e, sys.exc_info()[0])

    def set_muscle_percents(self, percents):
        # percents are list of contraction amount, 0% is max muscle length 
        clamped_percents = [max(0, min(percent, 100)) for percent in percents]
        muscle_lengths = [
            self.MAX_MUSCLE_LENGTH * (0.75 + percent / 400)
            for percent in clamped_percents
        ]
        self.set_muscle_lengths(muscle_lengths)
        
    def set_contraction_percents(self, percents):
        # percents are list of contraction amount, 0% is max muscle length 
        clamped_percents = [100 - max(0, min(percent, 100)) for percent in percents]
        self.set_muscle_percents(clamped_percents)

    def calibrate(self):
        # moves platform to mid pressure to determine best d_to_p files
        self.slow_pressure_move(0,3000, 1000)

    def slow_move(self, start_lengths, end_lengths, rate_cm_per_s, new_target):
        rate_mm = rate_cm_per_s * 10
        interval = 0.05  
        muscle_length = max([abs(j - i) for i, j in zip(start_lengths, end_lengths)])
        steps = int(muscle_length / rate_mm / interval)

        if steps < 1:
            self.set_muscle_lengths(end_lengths)
        else:
            current = start_lengths
            delta = [float(e - s) / steps for s, e in zip(start_lengths, end_lengths)]

            for step in range(steps):
                new_end = new_target()
                if new_end is not None:
                    print(f"New target {new_end} detected, slowing down before switching.")
                    for _ in range(5):  # Reduce speed before switching
                        current = [x + (y * 0.2) for x, y in zip(current, delta)]
                        self.set_muscle_lengths(current)
                        self.sleep_func(interval)

                    self.slow_move(current, new_end, rate_cm_per_s, new_target)
                    return  

                current = [x + y for x, y in zip(current, delta)]
                current = np.clip(current, 0, 6000)
                self.set_muscle_lengths(current)
                self.sleep_func(interval)

    """
    def slow_move(self, start, end, rate_cm_per_s):
        raise Exception("slow_move method now implimented in platform_controller")
        # moves from the given start to end lengths at the given duration
        #  caution, this moves even if disabled
        rate_mm = rate_cm_per_s *10
        interval = .05  # ms between steps
        # distance = max(end - start, key=abs)
        distance = max([abs(j-i) for i,j in zip(start, end)])
        print("max distance=", distance)
        dur = abs(distance) / rate_mm
        steps = int(dur / interval)
        if steps < 1:
            self.move_distance(end)
        else:
            current = start
            print("moving from", start, "to", end, "steps", steps)
            # print "percent", (end[0]/start[0]) * 100
            delta = [float(e - s)/steps for s, e in zip(start, end)]
            for step in range(steps):
                current = [x + y for x, y in zip(current, delta)]
                current = np.clip(current, 0, 6000)
                self.move_distance(current)
                self.sleep_func(interval)
    """  
    def slow_pressure_move(self, start_pressure, end_pressure, duration_ms):
        #  caution, this moves even if disabled
        interval = 50  # time between steps in ms
        steps = duration_ms / interval
        if steps < 1:
            self.send_pressures([end_pressure]*6)
        else:            
            current = [start_pressure]*6
            #  print("moving from", start_pressure, "to", end_pressure, "steps", steps)
            delta = float(end_pressure - start_pressure)/steps
            #  print("delta = ", delta)
            for step in range(steps):
                current  =  [p+delta for p in current]
                #  print(current)
                self.sleep_func(interval / 1000.0)
                if self.progress_callback:
                    self.progress_callback(100 * step/steps)

    ##### legacy code for chairs
    """
    def chair_move_distance(self, lengths):
        # print("lengths:\t ", ",".join('  %d' % item for item in lengths))
        now = time.perf_counter()
        timeDelta = now - self.prev_time
        self.prev_time = now
        load_per_muscle = self.loaded_weight / 6  # if needed we could calculate individual muscle loads
        pressures = []
        # print("LENGTHS = ",lengths)
        for idx, delta_len in enumerate(lengths):
            len = self.max_actuator_len - delta_len - self.fixed_len     
            pressures.append(int(1000*self._convert_MM_to_pressure(idx, len,  timeDelta, load_per_muscle)))
        self.send_pressures(pressures)    
        print("lengths", lengths, "pressures", pressures)
   
    def set_platform_params(self, min_actuator_len, max_actuator_len, fixed_len):
        #  paramaters for a conventional (normal or inverted) stewart platform
        # "todo temp remove and do the percent calc in kinematics"
        self.min_actuator_len = min_actuator_len
        self.max_actuator_len = max_actuator_len
        self.fixed_len = fixed_len
        self.prev_pos = [0, 0, 0, 0, 0, 0]  # fixme requested distances stored here 

   
    def _convert_MM_to_pressure(self, idx, muscle_len, timeDelta, load):
        #  returns pressure in bar
        #  calculate the percent of muscle contraction to give the desired distance
        PRINT_MUSCLES = False
        percent = (self.max_actuator_len - muscle_len) / float(self.max_actuator_len)
        #  check for range between 0 and .25
        # print("muscle Len =", muscle_len, "percent =", percent)

        if percent < 0 or percent > 0.25:
            print "%.2f percent contraction out of bounds for muscle length %.1f" % (percent, muscle_len)

        distDelta = muscle_len-self.prev_pos[idx]  # the change in length from the previous position
        accel = (distDelta/1000) / timeDelta  # accleration units are meters per sec
        if distDelta < 0:
            force = load * (1-accel)  # TODO  here we assume force is same magnitude as expanding muscle ???
            #  TODO modify formula for force
            #  pressure = 30 * percent*percent + 12 * percent + .01  # assume 25 Newtons for now
            pressure = 35 * percent*percent + 15 * percent + .03  # assume 25 Newtons for now
            if PRINT_MUSCLES:
                print("muscle %d contracting %.1f mm to %.1f, accel is %.2f, force is %.1fN, pressure is %.2f"
                      % (idx, distDelta, muscle_len, accel, force, pressure))
        else:
            force = load * (1+accel)  # force in newtons not yet used
            #  TODO modify formula for expansion
            pressure = 35 * percent*percent + 15 * percent + .03  # assume 25 Newtons for now
            if PRINT_MUSCLES:
                print("muscle %d expanding %.1f mm to %.1f, accel is %.2f, force is %.1fN, pressure is %.2f"
                      % (idx, distDelta, muscle_len, accel, force, pressure))

        self.prev_pos[idx] = muscle_len  # store the muscle len
        MAX_PRESSURE = 6.0 
        MIN_PRESSURE = .05  # 50 millibar is minimin pressure
        pressure = max(min(MAX_PRESSURE, pressure), MIN_PRESSURE)  # limit range 
        return pressure
    """  
    
if __name__ == "__main__":
    log_level = logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%H:%M:%S')
    out = MuscleOutput()
    out.slow_pressure_move(0,3000, 1000)
    out.slow_pressure_move(3000, 2000,  1000)