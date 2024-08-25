#!/usr/bin/env python3
import os
import sys
import time
import paramiko
from queue import Queue
from threading import Thread
import socket


class UploadClips:
    def __init__(self, clip_folder, sftp_user, sftp_password, sftp_server, sftp_dir, retry_delay=10):
        # Queue to hold the file paths of the clips
        self.clip_queue = Queue()
        self.gps_queue = []


        self.sftp_user = sftp_user
        self.sftp_password = sftp_password
        self.sftp_server = sftp_server
        self.retry_delay = retry_delay

        # Get the clip directory from command-line arguments
        self.clip_folder = clip_folder

        if not os.path.isdir(clip_folder):
            print(f"Error: {clip_folder} is not a valid directory")
            sys.exit(1)

        # Create the corresponding directory on the SFTP server
        remote_today_dir = os.path.join(sftp_dir, os.path.basename(clip_folder))
        print(remote_today_dir)

        sftp = self.create_sftp_connection()
        if sftp is not None:
            # Manually set a directory and then print it
            directory_contents = sftp.listdir('.')
            print(f"Contents of the current directory: {directory_contents}")

            current_dir = sftp.getcwd()
            print(f"Current directory on SFTP server: {current_dir}")

            self.create_remote_directory(sftp, remote_today_dir)
            sftp.close()

        # Start the queue processing thread
        queue_thread = Thread(target=self.process_queue, args=(remote_today_dir,))
        queue_thread.daemon = True
        queue_thread.start()

    def check_internet(self, host="8.8.8.8", port=53, timeout=3):
        """Check if internet connection is available."""
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except socket.error as ex:
            print(f"No internet connection: {ex}")
            return False

    def create_sftp_connection(self):
        """Create and return an SFTP connection."""
        try:
            transport = paramiko.Transport((self.s, 22))
            transport.connect(username=self.sftp_user, password=self.sftp_password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            return sftp
        except Exception as e:
            print(f"Failed to connect to SFTP server: {e}")
            return None

    def create_remote_directory(self, sftp, remote_path):
        """Create directory on SFTP server if it doesn't exist."""
        # Remove leading/trailing slashes and split the path
        directories = remote_path.strip('/').split('/')
        current_dir = ''

        print(directories)

        try:
            sftp.chdir(remote_path)  # Test if remote_path exists
        except IOError:
            sftp.mkdir(remote_path)  # Create remote_path
            sftp.chdir(remote_path)

        print(f"Directory {remote_path} is ready on SFTP server.")

    def upload_clip(self, file_path, remote_dir):
        """Upload a single clip to the SFTP server."""
        sftp = self.create_sftp_connection()
        if sftp is None:
            return

        try:
            # Verify the file exists before attempting to upload
            if not os.path.isfile(file_path):
                print(f"File does not exist: {file_path}")
                return

            # Ensure the remote directory for today exists
            #create_remote_directory(sftp, remote_dir)
            #sftp.chdir(remote_dir)

            # Upload the file to the correct remote directory
            remote_path = os.path.join(remote_dir, os.path.basename(file_path))
            # sftp.chdir(remote_dir)
            print("info")
            #print(sftp.listdir(remote_dir))
            print("basename: " + os.path.basename(file_path))

            sftp.put(file_path, remote_path)
            print(f"Uploaded: {file_path} to {remote_path}")
            
            os.remove(file_path)  # Remove the file after successful upload
        except Exception as e:
            print(f"Failed to upload {file_path}: {e}")
            self.clip_queue.put(file_path)
        finally:
            sftp.close()

    def add_file_to_queue(self, file_path):
        self.clip_queue.put(file_path)

    def add_gps_to_queue(self, timestamp, gps_data):
        self.gps_queue.append((timestamp, gps_data))

    def look_for_closest_gps_data(self, file_path):
        # TODO: we need to look at file_path, extract filename, get timestamp of video
        # for d in self.gps_queue: 
        #     if d[0] - 

        pass

    def join_gps_to_video(file_path, gps_data):
        pass

        # TODO: use ExifTool to add GPS data to the clip
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


    def process_queue(self, remote_dir):
        """Process the upload queue."""
        while True:
            if not self.clip_queue.empty():
                file_path = self.clip_queue.get()
                if self.check_internet():
                    gps_data = self.look_for_closest_gps_data(file_path)
                    if gps_data is None: # TODO: we need to check if file is in queue for long time and forgotten. EX: if after 5 readd to queues we dont upload it because we are missing gps data, do it anyway.
                        self.clip_queue.put(file_path)
                        continue

                    self.join_gps_to_video(file_path, gps_data)
                    self.upload_clip(file_path, remote_dir)
                else:
                    print(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                    self.clip_queue.put(file_path)
            else:
                time.sleep(5)  # Wait for 5 seconds before checking the queue again

    # def monitor_directory(self, clip_dir):
    #     """Monitor the directory for new video clips that are ready for upload."""
    #     while True:
    #         for file_name in os.listdir(clip_dir):
    #             if file_name.startswith("TMP_"):
    #                 continue  # Skip files still being written

    #             if file_name.endswith(".mp4"):
    #                 file_path = os.path.join(clip_dir, file_name)
    #                 if file_path not in self.clip_queue.queue:
    #                     print(f"New clip detected: {file_path}")
    #                     self.clip_queue.put(file_path)
            
    #         time.sleep(2)  # Check for new files every 2 seconds

# if __name__ == "__main__":
#     if len(sys.argv) != 2:
#         print("Usage: python upload_clips.py <clip_directory>")
#         sys.exit(1)

#     # Get the clip directory from command-line arguments
#     CLIP_DIR = sys.argv[1]

#     if not os.path.isdir(CLIP_DIR):
#         print(f"Error: {CLIP_DIR} is not a valid directory")
#         sys.exit(1)

#     # Create the corresponding directory on the SFTP server
#     remote_today_dir = os.path.join(SFTP_DIR, os.path.basename(CLIP_DIR))
#     print(remote_today_dir)

#     sftp = create_sftp_connection()
#     if sftp is not None:
#         # Manually set a directory and then print it
#         directory_contents = sftp.listdir('.')
#         print(f"Contents of the current directory: {directory_contents}")

#         current_dir = sftp.getcwd()
#         print(f"Current directory on SFTP server: {current_dir}")

#         create_remote_directory(sftp, remote_today_dir)
#         sftp.close()

#     # Start the queue processing thread
#     queue_thread = Thread(target=process_queue, args=(remote_today_dir,))
#     queue_thread.daemon = True
#     queue_thread.start()

#     # Start monitoring the directory for new clips
#     monitor_directory(CLIP_DIR)
