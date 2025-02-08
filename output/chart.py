# chart.py

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

class Chart():
    SOLID = 0
    DASHED = 1
    DASH_DOT = 2
    DOTTED = 3
    
    def __init__(self, step_size,nbr_sensors=0, nbr_active_sensors=0):
       self.step_size = step_size
       self.nbr_sensors = nbr_sensors
       self.nbr_active_sensors = nbr_active_sensors
       self.dir_str = ["up", "down"] 
       self.linestyles = ['-', '--', '-.', ':']
       plt.style.use('fivethirtyeight')
       plt.rcParams['figure.figsize'] = (11, 8)
       # plt.style.use('seaborn-whitegrid')
       sns.set()
    
    def sensor_averages(self, ax, title, data, linestyle_idx, color):
        ylabel = 'Distance in mm'
        # legend =[label + ' cycle ' + str(n) for n in range(cycles)]
        legend = "" # legend now done by caller
        self.plot_pressures(ax, title, data, ylabel, legend, self.linesytle_by_index(linestyle_idx), color ) 
        
    def force(self, ax, title, x,y, ylabel, color):
        # X axis is pressure steps 
        if color == "":
            ax.plot(x,y)
        else:
            ax.plot(x,y, color=color)
        ax.set_title(title)
        ax.set_ylabel(ylabel,color=color)
        ax.set_xlabel('Time')
        # xtick = 500
        ax.set_xticks([]) 
        # ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: format(int(10*x*xtick))))
        #plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: format(int(x*10))))
        #  print data


    def sensor_average_time(self, ax, title, data, linestyle_idx, color):
        ylabel = 'Time in seconds'
        # legend =['LRF ' + str(n) for n in range(self.nbr_active_sensors)]
        # legends now done by caller
        self.plot_pressures(ax, title, data, ylabel, "", self.linesytle_by_index(linestyle_idx), color ) 
        
    def sensor_stddev(self, ax, title, data, linestyle_idx, color):
        ylabel = 'Standard Deviation (mm)'
        legend =['LRF ' + str(n) for n in range(self.nbr_active_sensors)]
        self.plot_pressures(ax, title, data, ylabel, legend, self.linesytle_by_index(linestyle_idx), color ) 
        ax.set_ylabel('Standard Deviation')
    
    def pressure_averages(self, ax, title, data,linestyle_idx):
        ylabel = 'Pressure in millibars'
        legend =['Actuator ' + str(n) for n in range(self.nbr_active_sensors)]
        self.plot_pressures(ax, title, data, ylabel, legend, self.linesytle_by_index(linestyle_idx), "" ) 
        
    def pressure_stddev(self, ax, title, data, linestyle_idx, color=''):
        ylabel = 'Standard Deviation (mb)'
        legend =['Actuator ' + str(n) for n in range(self.nbr_active_sensors)]
        self.plot_pressures(ax, title, data, ylabel, legend, self.linesytle_by_index(linestyle_idx), color ) 

    def percent(self, ax, title, data, linestyle_idx):
        ylabel = 'Percent'
        legend =['Actuator ' + str(n) for n in range(self.nbr_active_sensors)]
        self.plot_pressures(ax, title, data, ylabel, legend, self.linesytle_by_index(linestyle_idx), "" )
        
    def plot_pressures(self, ax, title, data, ylabel, legend, linestyle, color):
         ax.set_prop_cycle(color=['red', 'blue', 'green', 'cyan', 'magenta', 'yellow'])
         # X axis is pressure steps 
         if color == "":
             ax.plot(data, linestyle=linestyle)
         else:
             ax.plot(data, linestyle=linestyle, color=color)
         ax.set_title(title)
         ax.set_ylabel(ylabel)
         ax.set_xlabel('Pressure in millibars')
         xtick = self.step_size/10
         ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: format(int(10*x*xtick))))
         #plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: format(int(x*10))))
         #  print data
         if legend != "":
             ax.legend(legend)
             
    def plot_distance(self, ax, title, x, y):
        ax.set_title(title)
        ax.set_xlabel("Pressure")   
        ax.set_ylabel("Distance")  
        ax.plot(x,y)

    def scatter(self, ax, title, datax, datay, ylabel, legend):
         ax.set_prop_cycle(color=['red', 'blue', 'green', 'cyan', 'magenta', 'yellow'])
         # X axis is pressure steps 
         #  ax.plot(data, linestyle =  linestyle)
         ax.scatter(datax, datay)
         ax.set_title(title)
         ax.set_ylabel(ylabel)
         ax.set_xlabel('Pressure in millibars')
         xtick = self.step_size/10
         ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: format(int(x*xtick))))
         #plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: format(int(x*10))))
         if legend != "":
             ax.legend(legend)

    def figure(self):
        fig, ax = plt.subplots()
        return fig, ax

    def set_title(self, ax, title):
        ax.set_title(title) 
        
    def linesytle_by_index(self, index):
        return  self.linestyles[index % len(self.linestyles)]
         
    def show(self):
        plt.show()
        
    def save_figures(self, fname):
        print("Saving:", fname)
        plt.savefig('%s.png' % (fname), bbox_inches='tight')
        """
        for i in plt.get_fignums():
            plt.figure(i)
            plt.savefig('%s%d.png' % (fname,i), bbox_inches='tight')
        """             
        plt.close()
    