"""cli entry point for spyglass.

Parse command line arguments in, invoke server.
"""
import argparse
import logging
import re
import sys

import libcamera

# from picamera2.encoders import MJPEGEncoder, H264Encoder
# from picamera2.outputs import FileOutput



from spyglass.exif import option_to_exif_orientation
from spyglass.__version__ import __version__
from spyglass.camera import init_camera
# from spyglass.server import StreamingOutput
from spyglass.server import run_server
from spyglass import camera_options
from spyglass.dvr import DVR
from spyglass.timestamp import Timestamp 

MAX_WIDTH = 1920
MAX_HEIGHT = 1920


def main(args=None):
    """Entry point for hello cli.

    The setup_py entry_point wraps this in sys.exit already so this effectively
    becomes sys.exit(main()).
    The __main__ entry point similarly wraps sys.exit().
    """
    logging.info(f"Spyglass {__version__}")

    if args is None:
        args = sys.argv[1:]

    parsed_args = get_args(args)

    bind_address = parsed_args.bindaddress
    port = parsed_args.port

    stream_width, stream_height = split_resolution(parsed_args.resolution)
    clip_width, clip_height = split_resolution(parsed_args.clip_resolution)

    stream_url = parsed_args.stream_url
    snapshot_url = parsed_args.snapshot_url
    orientation_exif = parsed_args.orientation_exif
    controls = parsed_args.controls
    if parsed_args.controls_string:
        controls += [c.split('=') for c in parsed_args.controls_string.split(',')]
    if parsed_args.list_controls:
        print('Available controls:\n'+camera_options.get_libcamera_controls_string(0))
        return
    


    picam2 = init_camera(
        clip_width,
        clip_height,
        stream_width,
        stream_height,
        parsed_args.fps,
        parse_autofocus(parsed_args.autofocus),
        parsed_args.lensposition,
        parse_autofocus_speed(parsed_args.autofocusspeed),
        parsed_args.upsidedown,
        parsed_args.flip_horizontal,
        parsed_args.flip_vertical,
        controls,
        parsed_args.tuning_filter,
        parsed_args.tuning_filter_dir)


    clip_duration = parsed_args.clip_duration

    sftp_info = (parsed_args.sftp_user, parsed_args.sftp_password, parsed_args.sftp_server, parsed_args.sftp_dir)

    dvr = DVR(picam2, 
              parsed_args.clips_folder, 
              (clip_width, clip_height), 
              parsed_args.clip_fps, 
              parsed_args.quality_factor, 
              clip_duration, parsed_args.update_interval
              , parsed_args.gps_serial_port, 
              parsed_args.disk_alert_threshold, 
              parsed_args.cpu_temp_alert_threshold, 
              sftp_info)
    
    timestamp = Timestamp(picam2, dvr)
    picam2.start()


    try:
        run_server(bind_address, port, picam2, dvr, stream_url, snapshot_url, orientation_exif)
    finally:
        picam2.stop_recording()




def resolution_type(arg_value, pat=re.compile(r"^\d+x\d+$")):
    if not pat.match(arg_value):
        raise argparse.ArgumentTypeError("invalid value: <width>x<height> expected.")
    return arg_value

def control_type(arg_value: str):
    if '=' in arg_value:
        return arg_value.split('=')
    else:
        raise argparse.ArgumentTypeError(f"invalid control: Missing value: {arg_value}")


def orientation_type(arg_value):
    if arg_value in option_to_exif_orientation:
        return option_to_exif_orientation[arg_value]
    else:
        raise argparse.ArgumentTypeError(f"invalid value: unknown orientation {arg_value}.")


def parse_autofocus(arg_value):
    if arg_value == 'manual':
        return libcamera.controls.AfModeEnum.Manual
    elif arg_value == 'continuous':
        return libcamera.controls.AfModeEnum.Continuous
    else:
        raise argparse.ArgumentTypeError("invalid value: manual or continuous expected.")


def parse_autofocus_speed(arg_value):
    if arg_value == 'normal':
        return libcamera.controls.AfSpeedEnum.Normal
    elif arg_value == 'fast':
        return libcamera.controls.AfSpeedEnum.Fast
    else:
        raise argparse.ArgumentTypeError("invalid value: normal or fast expected.")


def split_resolution(res):
    parts = res.split('x')
    w = int(parts[0])
    h = int(parts[1])
    if w > MAX_WIDTH or h > MAX_HEIGHT:
        raise argparse.ArgumentTypeError("Maximum supported resolution is 1920x1920")
    return w, h

# endregion args parsers


# region cli args


def get_args(args):
    """Parse arguments passed in from shell."""
    return get_parser().parse_args(args)


def get_parser():
    """Return ArgumentParser for hello cli."""
    parser = argparse.ArgumentParser(
        allow_abbrev=True,
        prog='spyglass',
        description='Start a webserver for Picamera2 videostreams.',
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-b', '--bindaddress', type=str, default='0.0.0.0', help='Bind to address for incoming '
                                                                                 'connections')
    parser.add_argument('-p', '--port', type=int, default=8080, help='Bind to port for incoming connections')
    parser.add_argument('-r', '--resolution', type=resolution_type, default='640x480',
                        help='Resolution of the images width x height. Maximum is 1920x1920.')
    parser.add_argument('-f', '--fps', type=int, default=15, help='Frames per second to capture')
    parser.add_argument('-st', '--stream_url', type=str, default='/stream',
                        help='Sets the URL for the mjpeg stream')
    parser.add_argument('-sn', '--snapshot_url', type=str, default='/snapshot',
                        help='Sets the URL for snapshots (single frame of stream)')
    parser.add_argument('-af', '--autofocus', type=str, default='continuous', choices=['manual', 'continuous'],
                        help='Autofocus mode')
    parser.add_argument('-l', '--lensposition', type=float, default=0.0,
                        help='Set focal distance. 0 for infinite focus, 0.5 for approximate 50cm. '
                             'Only used with Autofocus manual')
    parser.add_argument('-s', '--autofocusspeed', type=str, default='normal', choices=['normal', 'fast'],
                        help='Autofocus speed. Only used with Autofocus continuous')
    parser.add_argument('-ud', '--upsidedown', action='store_true',
                        help='Rotate the image by 180° (sensor level)')
    parser.add_argument('-fh', '--flip_horizontal', action='store_true',
                        help='Mirror the image horizontally (sensor level)')
    parser.add_argument('-fv', '--flip_vertical', action='store_true',
                        help='Mirror the image vertically (sensor level)')
    parser.add_argument('-or', '--orientation_exif', type=orientation_type, default='h',
                        help='Set the image orientation using an EXIF header:\n'
                             '  h      - Horizontal (normal)\n'
                             '  mh     - Mirror horizontal\n'
                             '  r180   - Rotate 180\n'
                             '  mv     - Mirror vertical\n'
                             '  mhr270 - Mirror horizontal and rotate 270 CW\n'
                             '  r90    - Rotate 90 CW\n'
                             '  mhr90  - Mirror horizontal and rotate 90 CW\n'
                             '  r270   - Rotate 270 CW'
                        )
    parser.add_argument('-c', '--controls', default=[], type=control_type, action='extend', nargs='*',
                        help='Define camera controls to start with spyglass. '
                             'Can be used multiple times.\n'
                             'Format: <control>=<value>')
    parser.add_argument('-cs', '--controls-string', default='', type=str,
                        help='Define camera controls to start with spyglass. '
                             'Input as a long string.\n'
                             'Format: <control1>=<value1> <control2>=<valuparsed_args.e2>')
    parser.add_argument('-tf', '--tuning_filter', type=str, default=None, nargs='?', const="",
                        help='Set a tuning filter file name.')
    parser.add_argument('-tfd', '--tuning_filter_dir', type=str, default=None, nargs='?',const="",
                        help='Set the directory to look for tuning filters.')
    parser.add_argument('--list-controls', action='store_true', help='List available camera controls and exits.')
    parser.add_argument('--clips_folder', type=str, default="clips", help='Folder to store DVR clips.')
    parser.add_argument('-qf', '--quality_factor', type=int, default=20, help='Quality factor for the video recording.')
    parser.add_argument('--clip_duration', type=int, default=10, help='Duration of each clip in seconds.')
    parser.add_argument('--update_interval', type=int, default=300, help="Update interval to record videos (set 0 to record always.) Records X seconds video after every X update interval")
    parser.add_argument('--clip_fps', type=int, default=30, help='Frames per second of the video recording.')
    parser.add_argument('--clip_resolution', type=resolution_type, default='1920x1080',
                        help='Resolution of the images width x height. Maximum is 1920x1920.')
    parser.add_argument('--gps_serial_port', type=str, default='/dev/ttyACM0', help='Serial port for GPS data.')

    parser.add_argument('--disk_alert_threshold', type=float, default=0.10, help="Disk Space Threshold to Send warning.")
    parser.add_argument('--cpu_temp_alert_threshold', type=float, default=65.0, help="CPU Temp Threshold to Send warning.")

    parser.add_argument('--sftp_user', type=str, default="root", help="SFTP User")
    parser.add_argument('--sftp_password', type=str, default="root", help="SFTP Server password.")
    parser.add_argument('--sftp_server', type=str, default="127.0.0.1", help="SFTP Server url.")
    parser.add_argument('--sftp_dir', type=str, default="/", help="SFTP Server dir to store clips.")



    return parser

# endregion cli args
