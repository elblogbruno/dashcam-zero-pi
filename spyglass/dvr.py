import logging
import os
import sys
import datetime
from time import sleep
from threading import Thread
from picamera2.encoders import H264Encoder 
import serial
import pynmea2
from picamera2.outputs import FfmpegOutput

class DVR:
    def __init__(self, picam2, clips_folder, resolution, fps, qf, clip_duration, gps_serial_port):
        self.clips_folder = clips_folder
        self.resolution = resolution
        self.fps = fps
        self.qf = qf
        self.clip_duration = clip_duration
        self.picam2 = picam2
        self._init_clips_folder()
        self.thread = None

        self.last_gps_data = None

        self.gps_available = False
        
        if gps_serial_port: 
            try:
                self.gps_serial = serial.Serial(gps_serial_port, 9600, timeout=1)
                self.gps_available = True
                logging.info(f"Opened GPS serial port {gps_serial_port}")
            except serial.SerialException as e:
                logging.error(f"Failed to open GPS serial port {gps_serial_port}: {e}")
                self.gps_available = False

    def _init_clips_folder(self):
        if not self.clips_folder:
            logging.error("No clips folder specified. Exiting.")
            sys.exit(1)

        if not os.path.exists(self.clips_folder):
            logging.error(f"Clips folder {self.clips_folder} does not exist. Creating it.")
            try:
                os.mkdir(self.clips_folder)
            except OSError as e:
                logging.exception(e)
                logging.error(f"Failed to create clips folder {self.clips_folder}. Exiting.")
                sys.exit(1)

        if not os.access(self.clips_folder, os.W_OK):
            logging.error(f"Clips folder {self.clips_folder} is not writable. Exiting.")
            sys.exit(1)

    def _get_recording_encoder(self):
        res_qf = (self.resolution[0] * self.resolution[1]) / (1920 * 1080)
        fps_qf = (30 / self.fps) * self.fps
        bit_rate = int(fps_qf * self.qf * res_qf * 1024 * 1024)

        logging.info(f"Bit rate: {bit_rate}")
        encoder = H264Encoder(bitrate=bit_rate)
        return encoder

    
    async def gather_gps(self): 

        update_interval = 4
        last_update_time = 0  # seconds

        import time
        
        while True:

            if self.gps_available:
                gps_data = self.gps_serial.readline()
                try:
                    if gps_data.startswith(b'$GPGGA'):
                        gps_data_parsed = pynmea2.parse(gps_data.decode("utf-8"))
                        self.last_gps_data = gps_data_parsed
                        gps_data_str = f"{gps_data.latitude} {gps_data.longitude}"


                        current_time = time.time()
        
                        # Update temperature every `update_interval` seconds
                        if (current_time - last_update_time) >= update_interval:
                            logging.info(f"GPS data: {gps_data_str}")
                            last_update_time = current_time

                            # append the GPS data to .csv file
                            with open(os.path.join(self.clips_folder, "gps_data.csv"), "a") as f:
                                f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')},{gps_data_str}\n")

                except pynmea2.ParseError as e:
                    logging.error(f"Failed to parse GPS data: {e}")

            

    async def start_recording(self):
        import asyncio
        encoder = self._get_recording_encoder()
        # self.picam2.start()

        self.recording = True

        while True:
            clip_name = "clip_" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            clip_path_mp4 = os.path.join(self.clips_folder, clip_name + ".h264")

            # logging.info(f"Gathering GPS data: {self.gps_available} {self.gps_serial.in_waiting}")

            # if self.gps_available and self.gps_serial.in_waiting:
            #     gps_data = self.gps_serial.read_all()
            #     try:
            #         if gps_data.startswith(b'$GPGGA'):
            #             gps_data_parsed = pynmea2.parse(gps_data.decode("utf-8"))
            #             self.last_gps_data = gps_data_parsed
            #             logging.info(f"GPS data: {gps_data_parsed}")
            #     except pynmea2.ParseError as e:
            #         logging.error(f"Failed to parse GPS data: {e}")
            # create a folder inside clips folder with today's date
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            today_folder = os.path.join(self.clips_folder, today)
            if not os.path.exists(today_folder):
                os.mkdir(today_folder)

            clip_path_mp4 = os.path.join(self.clips_folder, today_folder, clip_name + ".h264")
            output = FfmpegOutput(clip_path_mp4)

            try:
                logging.info(f"Recording clip: {clip_name}")
                # self.picam2.start_encoder(encoder, clip_path_mp4, name="main")
                self.picam2.start_recording(encoder, output, name="main")
                # sleep(self.clip_duration)
                await asyncio.sleep(self.clip_duration)
                # self.picam2.stop_encoder()
                # encoder.stop()
                self.picam2.stop_recording()
                logging.info(f"Finished recording clip: {clip_name}")
            except asyncio.CancelledError:
                logging.info("Recording cancelled.")
                self.recording = False

            # # use ExifTool to add GPS data to the clip
            # if self.gps_available and self.last_gps_data:
            #     gps_data = self.last_gps_data
            #     try:
            #         gps_data_str = f"{gps_data.latitude} {gps_data.longitude}"
            #         logging.info(f"Adding GPS data to clip: {gps_data_str}")
            #         os.system(f"exiftool -GPSLatitude={gps_data.latitude} -GPSLongitude={gps_data.longitude} -GPSAltitude={gps_data.altitude} -GPSLatitudeRef={gps_data.lat_dir} -GPSLongitudeRef={gps_data.lon_dir} -GPSAltitudeRef={gps_data.altitude_units} {clip_path_mp4}")
            #         logging.info(f"Finished adding GPS data to clip: {gps_data_str}")

            #         # open gps_data.csv and append the GPS data     
            #         with open(os.path.join(self.clips_folder, "gps_data.csv"), "a") as f:
            #             f.write(f"{clip_name},{gps_data_str}\n")
            #     except Exception as e:  
            #         logging.error(f"Failed to add GPS data to clip: {e}")

    def list_clips(self, start_time, end_time):
        clips = []
        if os.path.exists(self.clips_folder):
            for clip in os.listdir(self.clips_folder):
                if clip.endswith(".h264") and os.path.getctime(clip) >= start_time and os.path.getctime(clip) <= end_time:
                    clip_path = os.path.join(self.clips_folder, clip)
                    clips.append({"name": clip, "path": clip_path, "size": os.path.getsize(clip_path), "created": os.path.getctime(clip_path)})
        return clips

    # def start_recording_thread(self):
    #     self.thread = Thread(target=self._start_recording)
    #     self.thread.start()

    def start_gather_gps_thread(self):
        self.thread = Thread(target=self.gather_gps)
        self.thread.start()

    # def stop_recording(self):
    #     if self.thread:
    #         self.thread.join()
    #         self.picam2.stop()

 
    def get_memory_info(self):
        memory = os.popen("free -m").readlines()
        memory = memory[1].split()

        total = int(memory[1]) / 1024
        used = int(memory[2]) / 1024
        free = int(memory[3]) / 1024
        shared = int(memory[4]) / 1024
        buff_cache = int(memory[5]) / 1024
        available = int(memory[6]) / 1024

        memory_info = {
            "total": f"{total:.2f} GB",
            "used": f"{used:.2f} GB",
            "free": f"{free:.2f} GB",
            "shared": f"{shared:.2f} GB",
            "buff_cache": f"{buff_cache:.2f} GB",
            "available": f"{available:.2f} GB"
        }

        return memory_info

    def get_cpu_temperature(self):
        temp = os.popen("vcgencmd measure_temp").readline()
        temp = temp.replace("temp=", "").replace("'C\n", "")
        return temp

    def get_os_info(self):
        memory_info = self.get_memory_info()
        cpu_temp = self.get_cpu_temperature()

        os_info = {
            "total": memory_info["total"],
            "used": memory_info["used"],
            "free": memory_info["free"],
            "shared": memory_info["shared"],
            "buff_cache": memory_info["buff_cache"],
            "available": memory_info["available"],
            "cpu_temp": cpu_temp
        }

        return os_info

    def get_system_status(self):
        os_info = self.get_os_info()

        status = {
            "recording": self.recording,
            "gps_thread_alive": self.thread.is_alive() if self.thread else False, 
            "gps_available": self.gps_available,
            "os_info": os_info
        }

        return status