import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import math

def point_at_distance(slider_angles, idx, d, slider_origin):
    # returns the location using the base reference frame when the given slider moves distance d
    # slider angle list values: [angle in rads, x sign, y sign]
    x = slider_angles[idx][1] * d * math.sin(slider_angles[idx][0]) # + slider_origin[idx][0]
    y = slider_angles[idx][2] * d * math.cos(slider_angles[idx][0]) # + slider_origin[idx][1]    
    return x,y
  
"""
# Define a function that takes six parameters: ax, ay, bx, by, cx, cy, and d
def point_on_line(ax, ay, bx, by, cx, cy, d):
    # Calculate the slope of the line AB
    m = (by - ay) / (bx - ax)
    # Calculate the intercept of the line AB
    b = ay - m * ax
    # Calculate the distance from C to AB
    dist = abs(m * cx - cy + b) / math.sqrt(m ** 2 + 1)
    # Check if the distance is equal to d
    if dist == d:
        return (cx, cy) # Return C as the point on the line
    # Calculate the angle between AB and the x-axis
    theta = math.atan(m)
    # Calculate the horizontal and vertical components of d
    dx = d * math.cos(theta)
    dy = d * math.sin(theta)
    # Calculate the coordinates of the point P on the line AB that is closest to C
    px = (cx + m * cy - m * b) / (m ** 2 + 1)
    py = (m * cx + m ** 2 * cy + b) / (m ** 2 + 1)
    # Calculate the coordinates of the point Q on the line AB that is d away from C
    qx = px + dx
    qy = py + dy
    # Return Q as the point on the line
    return (qx, qy)

# Define a function that takes six parameters: ax, ay, bx, by, cx, cy, and d
def point_on_axis(ax, ay, bx, by, cx, cy, d):
    # Calculate the midpoint of the line segment AB
    mx, my = arrayMean([[ax, bx], [ay, by]], axis=1)
    # Calculate the slope of the line AB
    m = (by - ay) / (bx - ax)
    # Calculate the intercept of the line AB
    b = ay - m * ax
    # Calculate the distance from C to AB
    dist = abs(m * cx - cy + b) / math.sqrt(m ** 2 + 1)
    # Check if the distance is equal to d
    if dist == d:
        return (cx, cy) # Return C as the point on the axis
    # Calculate the angle between AB and the x-axis
    theta = math.atan(m)
    # Calculate the horizontal and vertical components of d
    dx = d * math.cos(theta)
    dy = d * math.sin(theta)
    # Calculate the coordinates of the point Q on the axis AB that is d away from C
    qx = mx + dx
    qy = my + dy
    # Return Q as the point on the axis
    return (qx, qy)
"""

  
def plot(base_pos, platform_pos, platform_mid_height, PLATFORM_NAME, slider_angles= None, slider_endpoints=None):
    base_labels = ['base{0}'.format(i) for i in range(6)]
    platform_labels = ['platform{0}'.format(i) for i in range(6)]
    if PLATFORM_NAME == "Sliding Actuators":
       is_flying_platform = True
       img = plt.imread("images/flying_platform.png")
       plt.imshow(img, zorder=1, extent=[-600, 600, -600, 600])
       # print("slider angles", slider_angles)
       # print("slider endpoints", slider_endpoints)
       for i in range(6):
           x_points = [slider_endpoints[i][0][0], slider_endpoints[i][1][0] ]
           y_points = [slider_endpoints[i][0][1], slider_endpoints[i][1][1] ]
           plt.plot(x_points, y_points, color='black' )
    else:
        is_flying_platform = False
        img = plt.imread("images/chair_red.png")
        plt.imshow(img, zorder=1, extent=[-400, 400, -400, 400])
        
    bx= base_pos[:,0]
    by = base_pos[:,1]
    plt.scatter(bx,by,zorder=2)
    
    px= platform_pos[:,0]
    py = platform_pos[:,1]
    plt.axis('equal')
    plt.scatter(px,py,zorder=3)
    # plt.imshow(img, zorder=0, extent=[-100, 100, -100, 100])

    plt.xlabel('X axis mm')
    plt.ylabel('Y axis mm')
    plt.axhline(0, color='grey', ls='dotted')
    plt.axvline(0, color='grey', ls='dotted')
    plt.title(PLATFORM_NAME)
    if PLATFORM_NAME == "Flying Platform":
        lbl_xoffset = 20
        lbl_yoffset = 20
    else:
         lbl_xoffset = 20
         lbl_yoffset = 20

    for label, x, y in zip(base_labels, bx, by):
        if x > 0 and y < 0:
           h = 'right'
        else:
           h = 'left'
        h = 'right'
        plt.annotate(
            label,
            xy=(x, y), xytext=(lbl_xoffset, lbl_yoffset),
            textcoords='offset points', ha=h, va='bottom',
            bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.5),
            arrowprops=dict(arrowstyle = '->', connectionstyle='arc3,rad=0'))
    for label, x, y in zip(platform_labels, px, py):
        if is_flying_platform:
            h = 'left'
        else:
            if x < 0 and y < 0: h = 'left'
            else: h = 'right'
        if is_flying_platform:  
            if label == "platform1" or label == "platform4" or label == "platform5" :
               offset = (-20, -20)
            else:
               offset = (-20, 20)
        else:
            offset = (-20, 20)
        plt.annotate(
            label,
            xy=(x, y), xytext=(offset),
            textcoords='offset points', ha=h, va='bottom',
            bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.5),
            arrowprops=dict(arrowstyle = '->', connectionstyle='arc3,rad=0'))

    plt.show()

        

def plot_actuator(slider_endpoints, top_point, slider_pos):
       img = plt.imread("images/flying_platform.png")
       plt.imshow(img, zorder=1, extent=[-600, 600, -600, 600])
       print("\nslider_endpoints", slider_endpoints, "top point", top_point, "slider_pos", slider_pos)
       x_points = [slider_endpoints[0][0], slider_endpoints[1][0] ]
       y_points = [slider_endpoints[0][1], slider_endpoints[1][1] ]
       plt.plot(x_points, y_points, color='black' )
       x1_points = [top_point[0], slider_pos[0] ]
       y1_points = [top_point[1], slider_pos[1] ]
       plt.plot(x1_points, y1_points, color='red' ) 
   
       plt.show()

class Plot3dCarriages:
    def __init__(self, cfg, slider_points):
        fig = plt.figure()
        self.ax = fig.add_subplot(111, projection='3d')
        plt.ion()
        self.cfg = cfg
        self.slider = slider_points
        
    def plot(self, pose, carriage_points,):
        plt.cla()
        for i in range(6):
            a = pose[i]
            if i == 5:
                b = pose[0]
            else:
                b = pose[i+1]
            self.ax.plot( [a[0],b[0]], [a[1],b[1]],[a[2],b[2]], 'black')

        for i in range(6):
            self.ax.plot([self.slider[i][0][0], self.slider[i][1][0]],[self.slider[i][0][1], self.slider[i][1][1]],[0,0],'black')

        for i in range(6):
            a = pose[i]
            b = carriage_points[i]
            self.ax.plot( [a[0],b[0]], [a[1],b[1]],[a[2],b[2]], label = str(i))
            self.ax.legend()

        self.ax.set_xlabel('X Movement')
        self.ax.set_ylabel('Y Movement')
        self.ax.set_zlabel('Z Movement')
        if self.cfg.PLATFORM_MID_HEIGHT < 0:
            zlimit = (-self.cfg.limits_1dof[2] + self.cfg.PLATFORM_MID_HEIGHT,0)
        else:
            zlimit = (0, self.cfg.limits_1dof[2] + self.cfg.PLATFORM_MID_HEIGHT)
        self.ax.set_zlim3d(zlimit)
        self.ax.set_title(self.cfg.PLATFORM_NAME)

        plt.show()
        plt.pause(0.01)

def plot3d_carriages(cfg, pose, carriage_points, slider_points, percents):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    
    plt.ion()
        
    def on_move(event):
        if event.inaxes:
            ax.view_init(elev=ax.elev, azim=ax.azim - event.xdata)

    def on_scroll(event):
        if event.inaxes:
            ax.view_init(elev=ax.elev - event.step, azim=ax.azim)
   
    fig.canvas.mpl_connect('motion_notify_event', on_move)
    fig.canvas.mpl_connect('scroll_event', on_scroll)
   
    for i in range(6):
        a = pose[i]
        if i == 5:
            b = pose[0]
        else:
            b = pose[i+1]
        ax.plot( [a[0],b[0]], [a[1],b[1]],[a[2],b[2]], 'black')
        
    # print("platform type =", cfg.PLATFORM_TYPE)
    if cfg.PLATFORM_TYPE == "SLIDER":
        for i in range(6):
            ax.plot([slider_points[i][0][0], slider_points[i][1][0]],[slider_points[i][0][1], slider_points[i][1][1]],[0,0],'black')
            # ax.plot([cfg.center_to_inner_joint,cfg.center_to_inner_joint],[0,-cfg.joint_max_offset],[0,0],'black')
            # ax.plot([cfg.center_to_outer_joint,cfg.center_to_outer_joint],[0,cfg.joint_max_offset],[0,0], 'black')


    for i in range(6):
        a = pose[i]
        b = carriage_points[i]
        ax.plot( [a[0],b[0]], [a[1],b[1]],[a[2],b[2]], label = str(i))
        ax.legend()


    ax.set_xlabel('X Movement')
    ax.set_ylabel('Y Movement')
    ax.set_zlabel('Z Movement')
    if cfg.PLATFORM_MID_HEIGHT < 0:
        zlimit = (-cfg.limits_1dof[2] + cfg.PLATFORM_MID_HEIGHT,0)
    else:
        zlimit = (0, cfg.limits_1dof[2] + cfg.PLATFORM_MID_HEIGHT)
    ax.set_zlim3d(zlimit)
    ax.set_title(cfg.PLATFORM_NAME)
    
    percents_str = 'Actuator movement: ' + '%  '.join(str(p) for p in percents) + '%'  
    fig.text(.5, .02, percents_str, ha='center') 

    plt.show()
    plt.pause(0.01)

    
def plot3d(cfg, pose): 
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    for i in range(6):
        a = pose[i]
        if i == 5:
            b = pose[0]
        else:
            b = pose[i+1]
        ax.plot( [a[0],b[0]], [a[1],b[1]],[a[2],b[2]], 'yellow')
        
    print("platform type =", cfg.PLATFORM_TYPE)
    if cfg.PLATFORM_TYPE == "SLIDER":
        ax.plot([cfg.center_to_inner_joint,cfg.center_to_inner_joint],[0,-cfg.joint_max_offset],[0,0],'black')
        ax.plot([cfg.center_to_outer_joint,cfg.center_to_outer_joint],[0,cfg.joint_max_offset],[0,0], 'black')


    for i in range(6):
        a = pose[i]
        b = cfg.BASE_POS[i]
        ax.plot( [a[0],b[0]], [a[1],b[1]],[a[2],b[2]], label = str(i))
        ax.legend()


    ax.set_xlabel('X Movement')
    ax.set_ylabel('Y Movement')
    ax.set_zlabel('Z Movement')
    if cfg.PLATFORM_MID_HEIGHT < 0:
        zlimit = (-cfg.limits_1dof[2] + cfg.PLATFORM_MID_HEIGHT,0)
    else:
        zlimit = (0, cfg.limits_1dof[2] + cfg.PLATFORM_MID_HEIGHT)
    ax.set_zlim3d(zlimit)
    ax.set_title(cfg.PLATFORM_NAME)
    plt.show()