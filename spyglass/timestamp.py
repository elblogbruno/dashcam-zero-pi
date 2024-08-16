import cv2
from picamera2 import MappedArray
import time
import re, subprocess

import logging

from spyglass.dvr import DVR

class Timestamp:
    def __init__(self, picam2, dvr: DVR):
        self.picam2 = picam2
        
        picam2.pre_callback = self.apply_timestamp

        # Global variables for timing and temperature
        self.last_update_time = 0
        self.last_temp = None

        self.dvr = dvr

    def check_CPU_temp(self):
        temp = None
        err, msg = subprocess.getstatusoutput('vcgencmd measure_temp')
        if not err:
            m = re.search(r'-?\d\.?\d*', msg)   # https://stackoverflow.com/a/49563120/3904031
            try:
                temp = float(m.group())
            except:
                pass
        return temp, msg

    def apply_timestamp(self, request): 
        # Define constants
        colour = (255, 255, 255)
        origin = (0, 30)
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 1
        thickness = 2
        update_interval = 5  # seconds

        current_time = time.time()
        
        # Update temperature every `update_interval` seconds
        if (current_time - self.last_update_time) >= update_interval:
            self.last_temp, msg = self.check_CPU_temp()
            logging.info (f"CPU temperature: {self.last_temp}°C")
            self.last_update_time = current_time

        timestamp = time.strftime("%Y-%m-%d %X")

        last_gps_data = self.dvr.last_gps_data
        
        with MappedArray(request, "main") as m: 
            # Add timestamp and temperature text
            cv2.putText(m.array, timestamp, origin, font, scale, colour, thickness)
            if self.last_temp is not None:
                cv2.putText(m.array, f"TEMP: {self.last_temp:.1f}°C", (0, 60), font, scale, colour, thickness)
            if last_gps_data:
                cv2.putText(m.array, f"GPS: {last_gps_data}", (0, 90), font, scale, colour, thickness)