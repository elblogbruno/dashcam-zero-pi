import logging
import os
import sys
import datetime
from time import sleep
from threading import Thread
from picamera2.encoders import H264Encoder 

class DVR:
    def __init__(self, picam2, clips_folder, resolution, fps, qf, clip_duration):
        self.clips_folder = clips_folder
        self.resolution = resolution
        self.fps = fps
        self.qf = qf
        self.clip_duration = clip_duration
        self.picam2 = picam2
        self._init_clips_folder()
        self.thread = None

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

    def _start_recording(self):
        encoder = self._get_recording_encoder()
        # self.picam2.start()

        while True:
            clip_name = "clip_" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            clip_path_mp4 = os.path.join(self.clips_folder, clip_name + ".h264")

            logging.info(f"Recording clip: {clip_name}")
            self.picam2.start_encoder(encoder, clip_path_mp4, name="main")
            sleep(self.clip_duration)
            # self.picam2.stop_encoder()
            encoder.stop()
            
            logging.info(f"Finished recording clip: {clip_name}")

        self.picam2.stop_preview()

    async def start_recording(self):
        import asyncio
        encoder = self._get_recording_encoder()
        # self.picam2.start()

        while True:
            clip_name = "clip_" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            clip_path_mp4 = os.path.join(self.clips_folder, clip_name + ".h264")

            logging.info(f"Recording clip: {clip_name}")
            self.picam2.start_encoder(encoder, clip_path_mp4, name="main")
            # sleep(self.clip_duration)
            await asyncio.sleep(self.clip_duration)
            # self.picam2.stop_encoder()
            encoder.stop()
            logging.info(f"Finished recording clip: {clip_name}")



    def start_recording_thread(self):
        self.thread = Thread(target=self._start_recording)
        self.thread.start()

    def stop_recording(self):
        if self.thread:
            self.thread.join()
            self.picam2.stop()

 