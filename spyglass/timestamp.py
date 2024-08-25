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
            logging.info(f"CPU temperature: {self.last_temp}°C")
            self.last_update_time = current_time

        timestamp = time.strftime("%Y-%m-%d %X")

        last_gps_data = self.dvr.last_gps_data

        # Check recording status
        # is_recording = self.check_recording_status()  # Assuming this function exists to check if recording
        is_recording = self.dvr.is_recording

        # Load the recording icon
        # recording_icon = cv2.imread("/assets/recording_icon.png", cv2.IMREAD_UNCHANGED)
        icon_size = (50, 50)  # Resize icon if needed
        # recording_icon = cv2.resize(recording_icon, icon_size)

        with MappedArray(request, "main") as m: 
            # Add timestamp and temperature text
            cv2.putText(m.array, timestamp, origin, font, scale, colour, thickness)
            if self.last_temp is not None:
                cv2.putText(m.array, f"TEMP: {self.last_temp:.1f}°C", (0, 60), font, scale, colour, thickness)
            if last_gps_data:
                cv2.putText(m.array, f"GPS: {last_gps_data}", (0, 90), font, scale, colour, thickness)
            
            # Add recording icon and text if recording
            # if is_recording:
            #     icon_origin = (m.array.shape[1] - icon_size[0] - 10, 10)  # Position icon at top-right
            #     m.array[10:10+icon_size[1], -10-icon_size[0]:-10] = recording_icon  # Overlay icon on the frame
            #     cv2.putText(m.array, "REC", (m.array.shape[1] - 80, 60), font, scale, colour, thickness)
