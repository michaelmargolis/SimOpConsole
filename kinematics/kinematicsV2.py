""" kinematicsV2
This module provides inverse kinematics for the Mdx motion platforms
  The core method, named inverse_kinematics is passed the desired orientation as: [surge, sway, heave, roll, pitch yaw]
  and returns the platform pose as an array of coordinates for the attachment points 
  Pose is converted to actuator lengths using the method: actuator_len_from_pose
  NOTE: all length values returned represent muscle contraction amounts (not length of muscle)
 


"""
import sys
import math
import traceback
import copy
import numpy as np

import logging
log = logging.getLogger(__name__)

class Kinematics(object):
    def __init__(self):
        np.set_printoptions(precision=3,suppress=True)

    def clamp(self, n, minn, maxn):
        return max(min(maxn, n), minn)
    
    def set_geometry(self, base_coords, platform_coords):
        self.base_coords = base_coords
        self.platform_coords = platform_coords       
        self.intensity = 1.0

    def set_slider_params(self, joint_min_offset, joint_max_offset, strut_length, slider_angles, slider_endpoints ):
        # parameters for the slider platform
        self.joint_min_offset = joint_min_offset
        self.joint_max_offset = joint_max_offset
        self.strut_length = strut_length
        self.slider_angles = slider_angles
        self.slider_endpoints = slider_endpoints
        self.struts_squared =  np.full(6, self.strut_length * self.strut_length)
        self.is_slider = True
        self.slider_origin = copy.deepcopy(self.platform_coords)
        self.slider_origin[:,2] = 0 # set z to zero
        self.temp_max_iter =0
        self.actuator_range = joint_max_offset - joint_min_offset
        log.info("Kinematics set for sliding platform")

    def set_platform_params(self, min_actuator_len, max_actuator_len, fixed_len):
        #  paramaters for a conventional (normal or inverted) stewart platform
        self.min_actuator_len = min_actuator_len
        self.max_actuator_len = max_actuator_len
        self.fixed_len = fixed_len
        self.actuator_range = max_actuator_len - min_actuator_len
        self.is_slider = False  # will be set True iff set_slider_params method is called
        log.info("Kinematics set for chairs")

    def calc_rotation(self, rpy):
        # return rotation matrix from roll,pitch,yaw
        roll = rpy[0]  # positive roll is right side down
        pitch = rpy[1]   # positive pitch is nose down
        yaw = rpy[2]   # positive yaw is CCW
       
        cos_roll = math.cos(roll)
        sin_roll = math.sin(roll)
        cos_pitch = math.cos(pitch)
        sin_pitch = math.sin(pitch)
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        #  calculate rotation matrix
        Rxyz = np.array([[cos_yaw*cos_pitch, cos_yaw*sin_pitch*sin_roll - sin_yaw*cos_roll, cos_yaw*sin_pitch*cos_roll + sin_yaw*sin_roll],
                         [sin_yaw*cos_pitch, sin_yaw*sin_pitch*sin_roll + cos_yaw*cos_roll, sin_yaw*sin_pitch*cos_roll - cos_yaw*sin_roll],
                         [-sin_pitch, cos_pitch*sin_roll, cos_pitch*cos_roll]])
        return Rxyz

    def inverse_kinematics(self, request):
        # request: x,y,z translations in mm, roll, pitch, yaw rotations in radians
        # returns numpy 3d array of platform attachment points
        xyzrpy = np.asarray(copy.deepcopy(request)) * self.intensity
        a = np.array(xyzrpy).transpose()
        platform_xlate = a[0:3] + self.platform_coords # surge, sway, heave
        # print " platform_xlate=",  platform_xlate, self.platform_coords
        #  Calculate rotation matrix elements
        rpy = a[3:6] # + roll is right side down, + pitch is nose down, + yaw is CCW
        # Rxyz = R.from_euler('xyz',rpy).as_dcm()[:3,:]
        Rxyz = self.calc_rotation(rpy)

        self.pose = np.zeros(self.platform_coords.shape)
        for i in range(6):
            self.pose[i, :] = np.dot(Rxyz, platform_xlate[i, :])
        return self.pose  # 6 rows of 3d platform attachment points

    def actuator_lengths(self, xyzrpy):
        pose = self.inverse_kinematics(xyzrpy)
        return self.len_from_pose(pose)
    
    def actuator_percents(self, xyzrpy):
        pose = self.inverse_kinematics(xyzrpy)
        lengths = self.len_from_pose(pose)
        return self.percent_from_len(lengths)
        
    def percent_from_len(self, len):
        percents = [round((l*100.0) /self.actuator_range,1) for l in len]
        return percents
    
    def len_from_pose(self, pose):
        # returns distance actuator must move from min position to achieve given pose
        if self.is_slider:
            self.slider_dist, self.slider_coord = self.slider_pos_from_pose(pose)
            return self.slider_dist
        else:            
            muscle_len = np.linalg.norm(self.pose - self.base_coords, axis=1)
            return [self.clamp(int(round(l-self.min_actuator_len)),0,self.actuator_range) for l in muscle_len]

    def get_pose(self):
        return self.pose    

    def point_at_distance(self, idx, d):
        x = self.slider_angles[idx][1] * d * math.sin(self.slider_angles[idx][0]) + self.slider_origin[idx][0]
        y = self.slider_angles[idx][2] * d * math.cos(self.slider_angles[idx][0]) + self.slider_origin[idx][1]
        return x,y,0
        
    def slider_pos(self, slider_endpoints, top_point, actuator_len):
        v = slider_endpoints[1] - slider_endpoints[0] # slider endpoint vector
        u = v / np.linalg.norm(v) # unit vector of v
        w = top_point - slider_endpoints[1] # vector from start of slider to top point
        c = np.dot(w, u) 
        print("c=", c)
        q = slider_endpoints[0] + u * (c + actuator_len)

        # calculate carriage point
        if np.dot(q - slider_endpoints[0], q - slider_endpoints[1]) <= 0:
            # here if intersecting point is within range of slider
            carriage_point = slider_endpoints[0] + u * (c + actuator_len)
        else:
           carriage_point = slider_endpoints[0] + u * (c - actuator_len)
           
        distance = np.linalg.norm(slider_endpoints[0]  - carriage_point )            
        return carriage_point
        
        
        # get unit vector along slider line
        unit_vector = np.diff(slider_endpoints, axis=0)[0] / np.linalg.norm(np.diff(slider_endpoints, axis=0))
        # find the projection of the top_point onto the line.
        d = np.linalg.norm(np.cross(slider_endpoints[1]- slider_endpoints[0], slider_endpoints[0]-top_point))/np.linalg.norm(slider_endpoints[1]- slider_endpoints[0])
        print('shortest dist = ', d)
        projection = np.dot(top_point, unit_vector) * unit_vector
        # find the point p that is actuator_len units away from the projection along the line. 
        p = projection + actuator_len * unit_vector
        distance = np.linalg.norm(p - slider_endpoints, axis=1)
        print('in slider_pos, line=', slider_endpoints, 'point=', top_point,'distance=', distance)
        return p # todo change point to distance

    def slider_pos_from_pose(self, pose):
        # calculate where the sliders need to be for the given pose
        # returns array of slider offsets and array of slider coordinates
        dist = []
        coords = []
        for idx in range(6): 
            d = (self.joint_max_offset+self.joint_min_offset)/2 # start at slider mid point
            delta = 64 # (self.joint_max_offset-self.joint_min_offset) / 4
            for iter in range(9):
                point = self.point_at_distance(idx, d)
                # d1 is distance from upper ball joint to slider at pos d
                d1 = np.rint(np.linalg.norm(point-pose[idx]))
                if self.strut_length-d1 == 0:
                    break
                else:
                    if self.strut_length-d1 < 0:
                        # here if d1 larger than strut length 
                        if  d < self.joint_min_offset:
                            d = self.joint_min_offset
                            break
                        else:
                            d -= delta
                    else:
                        # here if d1 less than strut length
                        if  d > self.joint_max_offset:
                            d = self.joint_max_offset
                            break
                        else:
                            d += delta
                    if delta >=2: # smallest step is 1mm
                        delta /= 2 
                if iter > 6:
                    print(format("iter= %d, d=%d, err= %d, delta=%d" %(iter, d, self.strut_length-d1, delta)))
            if iter > self.temp_max_iter:
                self.temp_max_iter = iter
            dist.append(d-self.joint_min_offset)
            coords.append(point)
        print("in kinematics, distances:", dist)
        return dist, coords
        
    """
    def slider_percents(self, xyzrpy):
        # convenience method returns array of slider percents for given orientation
        pose = self.inverse_kinematics(xyzrpy)
        return self.slider_percent_from_pose(pose)
    """
    
    def set_intensity(self, intensity):
        self.intensity = intensity
        print("Kinematics intensity set to", self.intensity)
        log.info("Kinematics intensity set to %.1f", intensity)

def test(request):
    distances =  k.actuator_lengths(request)
    print(request,   "distances:", distances,  "percents:", k.percent_from_len(distances))
   

def test_suite():
    test([0,0,0,0,0,0])
    test([0,0,75,0,0,0])
    test([0,0,-75,0,0,0])

    print("start of timing test")
    start = time.time()
    for z in range(-75,75):
        k.actuator_percents([.1,.1,z,.1,.1,.05])
        # k.actuator_lengths([.1,.1,z,.1,.1,.05])
    t = time.time() - start
    print(format("%d kinematic calculations in %.3f ms" % ( 150, t*1000)))
    # print "max iters = ", k.temp_max_iter
    return
    print("Standard tests:")
    test([0,0,0,0,0,0])
    test([0,0,75,0,0,0])
    test([0,0,-75,0,0,0])
    test([0,0,0,.5,0,0])
    test([0,0,0,-.5,0,0])
    test([0,0,0,0,.5,0])
    test([0,0,0,0,-.5,0])
    test([0,0,0,0,0,.5])
    test([0,0,0,0,0,-.5])
    test([70,0,0,0,0,0])
    test([-70,0,0,0,0,0])
    test([0,70,0,0,0,0])
    test([0,-70,0,0,0,0])
    test([30,10,10,.1,.1,0])
    k.set_intensity(.1)
    print("intensity set to 0.1")
    test([0,0,75,0,0,0])
    test([0,0,-75,0,0,0])
    k.set_intensity(1)
    print("intensity set back to 1\n")



if __name__ == "__main__":
    log_level = logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%H:%M:%S')
    ECHO_TO_SOLIDWORKS = False
    log.info("echo to solidworks is %s", ECHO_TO_SOLIDWORKS)
    from cfg_SlidingActuators import *
    # from cfg_SuspendedChair import *  # comment above and uncomment this for chair
    import plot_config
    import time
    if ECHO_TO_SOLIDWORKS:    
        import sw_api as sw
    
    cfg = PlatformConfig()
    cfg.calculate_coords()
    k = Kinematics()

    k.set_geometry( cfg.BASE_POS, cfg.PLATFORM_POS)
    if cfg.PLATFORM_TYPE == "SLIDER":
        k.set_slider_params(cfg.joint_min_offset, cfg.joint_max_offset, cfg.strut_length, cfg.slider_angles, cfg.slider_endpoints)
        is_slider = True
      
    else:
        k.set_platform_params(cfg.MIN_ACTUATOR_LEN, cfg.MAX_ACTUATOR_LEN, cfg.FIXED_LEN)
        is_slider = False

    #  uncomment the following to plot the array coordinates
    # plot_config.plot(cfg.BASE_POS, cfg.PLATFORM_POS, cfg.PLATFORM_MID_HEIGHT, cfg.PLATFORM_NAME )

    # test_suite()    

    #  user input
    print("translation values in mm, rotation in degrees") 
    
    plot3D = plot_config.Plot3dCarriages(cfg, k.slider_endpoints)
    
    while True:
        inp = input("enter orientation on command line as: surge, sway, heave, roll, pitch yaw ")
        if inp == "":
            exit()
        inp_list = list(map( float, inp.split(',') ))
        print("input", inp_list)
        if len(inp_list) == 6:
            request = []
            for idx, val in enumerate(inp_list):
                if idx < 3: 
                    request.append(val)
                else:
                    request.append(val * 0.01745329)
            print("request", request)
            pose = k.inverse_kinematics(request)
            if is_slider:

                carriage_points = []
                for i in range(6): 
                    pos = k.slider_pos(k.slider_endpoints[i], pose[i], 400  )
                    carriage_points.append(pos)    
                print("carriage_points", carriage_points)   
                print("pose", pose)                
                # plot_config.plot3d_carriages(cfg, pose, carriage_points, k.slider_endpoints)
                # plot3D.plot(pose, carriage_points)
                # print(carriage_points)
                """ 
                dist, coords = k.slider_pos_from_pose(pose)
                print(dist)
                print(coords)
                """
 
                distances = k.len_from_pose(pose)
                if ECHO_TO_SOLIDWORKS:   
                    sw.set_struts(distances)
                slider_endpoints = np.array([[-100,0,0],[100,0,0]])
                top_point = np.array([350,350,0])
                dist = k.slider_pos(slider_endpoints, top_point, 400  )
                pos =  dist # temp np.array([-100 + dist, 0,0 ])
                # plot_config.plot_actuator(slider_endpoints, top_point, pos)     
                print( 'slider_endpoints', slider_endpoints,'top_point',top_point, 'pos',   pos)               
                plot_config.plot3d(cfg, k.pose)

            else:
               print(k.len_from_pose(k.inverse_kinematics(request)))
        else:
           print("expected 3 translation values in mm and 3 rotations values in radians")
    
    
    
