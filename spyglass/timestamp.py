import cv2
from picamera2 import MappedArray
import time
import re, subprocess

import logging

# Global variables for timing and temperature
last_update_time = 0
last_temp = None

def check_CPU_temp():
    temp = None
    err, msg = subprocess.getstatusoutput('vcgencmd measure_temp')
    if not err:
        m = re.search(r'-?\d\.?\d*', msg)   # https://stackoverflow.com/a/49563120/3904031
        try:
            temp = float(m.group())
        except:
            pass
    return temp, msg

def apply_timestamp(request):
    global last_update_time, last_temp
    
    # Define constants
    colour = (255, 255, 255)
    origin = (0, 30)
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 1
    thickness = 2
    update_interval = 5  # seconds

    current_time = time.time()
    
    # Update temperature every `update_interval` seconds
    if (current_time - last_update_time) >= update_interval:
        last_temp, msg = check_CPU_temp()
        logging.info (last_temp) 
        last_update_time = current_time

    timestamp = time.strftime("%Y-%m-%d %X")

    
    with MappedArray(request, "main") as m: 
        # Add timestamp and temperature text
        cv2.putText(m.array, timestamp, origin, font, scale, colour, thickness)
        if last_temp is not None:
            cv2.putText(m.array, f"TEMP: {last_temp:.1f}°C", (0, 60), font, scale, colour, thickness)