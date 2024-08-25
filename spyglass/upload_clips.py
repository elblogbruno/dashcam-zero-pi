#!/usr/bin/env python3
import os
import sys
import time
import paramiko
from dotenv import load_dotenv
from queue import Queue
from threading import Thread
import socket

# Load environment variables from .env file
dotenv_path = "/root/printer_data/config/.env"

print("Loading env from " + dotenv_path)

load_dotenv(dotenv_path)

# Retrieve SFTP credentials from environment variables
SFTP_USER = os.getenv("FTP_USER")
SFTP_PASSWORD = os.getenv("FTP_PASSWORD")
SFTP_SERVER = os.getenv("FTP_SERVER")
SFTP_DIR = os.getenv("FTP_DIR")

# Retry delay in seconds
RETRY_DELAY = 10

# Queue to hold the file paths of the clips
clip_queue = Queue()

def check_internet(host="8.8.8.8", port=53, timeout=3):
    """Check if internet connection is available."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error as ex:
        print(f"No internet connection: {ex}")
        return False

def create_sftp_connection():
    """Create and return an SFTP connection."""
    try:
        transport = paramiko.Transport((SFTP_SERVER, 22))
        transport.connect(username=SFTP_USER, password=SFTP_PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)
        return sftp
    except Exception as e:
        print(f"Failed to connect to SFTP server: {e}")
        return None

def create_remote_directory(sftp, remote_path):
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

def upload_clip(file_path, remote_dir):
    """Upload a single clip to the SFTP server."""
    sftp = create_sftp_connection()
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
        clip_queue.put(file_path)
    finally:
        sftp.close()

def process_queue(remote_dir):
    """Process the upload queue."""
    while True:
        if not clip_queue.empty():
            file_path = clip_queue.get()
            if check_internet():
                upload_clip(file_path, remote_dir)
            else:
                print(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
                clip_queue.put(file_path)
        else:
            time.sleep(5)  # Wait for 5 seconds before checking the queue again

def monitor_directory(clip_dir):
    """Monitor the directory for new video clips that are ready for upload."""
    while True:
        for file_name in os.listdir(clip_dir):
            if file_name.startswith("TMP_"):
                continue  # Skip files still being written

            if file_name.endswith(".mp4"):
                file_path = os.path.join(clip_dir, file_name)
                if file_path not in clip_queue.queue:
                    print(f"New clip detected: {file_path}")
                    clip_queue.put(file_path)
        
        time.sleep(2)  # Check for new files every 2 seconds

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python upload_clips.py <clip_directory>")
        sys.exit(1)

    # Get the clip directory from command-line arguments
    CLIP_DIR = sys.argv[1]

    if not os.path.isdir(CLIP_DIR):
        print(f"Error: {CLIP_DIR} is not a valid directory")
        sys.exit(1)

    # Create the corresponding directory on the SFTP server
    remote_today_dir = os.path.join(SFTP_DIR, os.path.basename(CLIP_DIR))
    print(remote_today_dir)

    sftp = create_sftp_connection()
    if sftp is not None:
        # Manually set a directory and then print it
        directory_contents = sftp.listdir('.')
        print(f"Contents of the current directory: {directory_contents}")

        current_dir = sftp.getcwd()
        print(f"Current directory on SFTP server: {current_dir}")

        create_remote_directory(sftp, remote_today_dir)
        sftp.close()

    # Start the queue processing thread
    queue_thread = Thread(target=process_queue, args=(remote_today_dir,))
    queue_thread.daemon = True
    queue_thread.start()

    # Start monitoring the directory for new clips
    monitor_directory(CLIP_DIR)
