import numpy as np

a =  np.asarray([0,0,0,0,0,0])
b =  np.asarray([9,100,100,100,100, 110])
c =  np.asarray([1000,1000,1000,1000,1000, 1000])
d =  np.asarray([6000,6000,6000,6000,6000, 4000])


def slow_move(start, end, rate_cm_per_s):
    # moves from the given start to end lengths at the given duration
    #  caution, this moves even if disabled
    rate_mm = rate_cm_per_s *10
    interval = .05  # ms between steps
    distance = max(end - start, key=abs)
    print "max distance=", distance
    dur = abs(distance) / rate_mm
    steps = int(dur / interval)
    print "steps", steps, type(steps)
    if steps < 1:
        self.move_distance(end)
    else:
        current = start
        print("moving from", start, "to", end, "steps", steps)
        # print "percent", (end[0]/start[0]) * 100
        delta = [float(e - s)/steps for s, e in zip(start, end)]
        print("move_func todo in step!!!!!!!!!!!")
        for step in range(steps):
            current = [x + y for x, y in zip(current, delta)]         
            current = np.clip(current, 0, 6000)
            print step, current  

slow_move(a, d, 5000)