"""cli entry point for spyglass.

Parse command line arguments in, invoke server.
"""
import argparse
import logging
import re
import sys

import libcamera

from picamera2.encoders import MJPEGEncoder, H264Encoder
from picamera2.outputs import FileOutput

from spyglass.exif import option_to_exif_orientation
from spyglass.__version__ import __version__
from spyglass.camera import init_camera
from spyglass.server import StreamingOutput
from spyglass.server import run_server
from spyglass import camera_options


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
    width, height = split_resolution(parsed_args.resolution)
    stream_url = parsed_args.stream_url
    snapshot_url = parsed_args.snapshot_url
    orientation_exif = parsed_args.orientation_exif
    controls = parsed_args.controls
    if parsed_args.controls_string:
        controls += [c.split('=') for c in parsed_args.controls_string.split(',')]
    if parsed_args.list_controls:
        print('Available controls:\n'+camera_options.get_libcamera_controls_string(0))
        return
    
    init_dvr(parsed_args)

    picam2 = init_camera(
        width,
        height,
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

    start_recording_thread(picam2, (width, height), parsed_args.fps, 10, parsed_args.clips_folder)

    output = StreamingOutput()
    picam2.start_recording(MJPEGEncoder(), FileOutput(output))



    try:
        run_server(bind_address, port, picam2, output, stream_url, snapshot_url, orientation_exif)
    finally:
        picam2.stop_recording()


# region args parsers
def init_dvr(args):
    # get the DVR clips folder
    clips_folder = args.clips_folder

    import os

    if clips_folder is None:
        logging.error("No clips folder specified. Exiting.")
        sys.exit(1)

    # check if the folder exists
    if not os.path.exists(clips_folder):
        logging.error(f"Clips folder {clips_folder} does not exist. Creating it.")
        try:
            os.mkdir(clips_folder)
        except OSError as e:
            logging.exception(e)
            logging.error(f"Failed to create clips folder {clips_folder}. Exiting.")
            sys.exit(1)

    # check if the folder is writable
    if not os.access(clips_folder, os.W_OK):
        logging.error(f"Clips folder {clips_folder} is not writable. Exiting.")
        sys.exit(1)

def _get_recording_encoder(resolution, fps, qf):
    print("resolution: ", resolution)
    print("fps: ", fps)
    print("qf: ", qf)

    res_qf = (resolution[0] * resolution[1]) / (1920 * 1080)
    fps_qf = (30 /  fps) *  fps
    bit_rate = int(fps_qf*qf*res_qf*1024*1024)

    print("bit_rate: ", bit_rate)

    # encoder = MJPEGEncoder(bit_rate) if self.hw_encode else JpegEncoder(bit_rate)
    encoder = H264Encoder(bitrate=bit_rate)
    return encoder

# def apply_timestamp(self, request):
#     colour = (255, 255, 255)
#     origin = (0, 30)
#     font = cv2.FONT_HERSHEY_SIMPLEX
#     scale = 1
#     thickness = 2
    
#     timestamp = time.strftime("%Y-%m-%d %X")
#     with MappedArray(request, "main") as m:
#         cv2.putText(m.array, timestamp, origin, font, scale, colour, thickness)
#         cv2.putText(m.array, "FPS: {}".format(self.fps_calc), (0, 60), font, scale, colour, thickness)

def _start_recording(picam2, resolution, fps, qf, clips_folder):
    import datetime
    import os
    from multiprocessing.pool import ThreadPool
    from time import sleep
    encoder = _get_recording_encoder(resolution, fps, qf)
     
    picam2.start()

    # self.api.pre_callback = self.apply_timestamp

    while True:
        clip_name = "clip_" + str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

        clip_path_mp4 = os.path.join(clips_folder, clip_name + ".mp4")

        print("Recording clip: " + clip_name)

        picam2.start_encoder(encoder, clip_path_mp4, name="main")

        sleep(5)

        # self.api.stop_recording()
        picam2.stop_encoder() 

        print("Finished recording clip: " + clip_name)

    picam2.stop_preview()


def start_recording_thread(picam2, resolution, fps, qf, clips_folder):
    import threading
    thread = threading.Thread(target=_start_recording, args=(picam2, resolution, fps, qf, clips_folder))
    thread.start()

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
                             'Format: <control1>=<value1> <control2>=<value2>')
    parser.add_argument('-tf', '--tuning_filter', type=str, default=None, nargs='?', const="",
                        help='Set a tuning filter file name.')
    parser.add_argument('-tfd', '--tuning_filter_dir', type=str, default=None, nargs='?',const="",
                        help='Set the directory to look for tuning filters.')
    parser.add_argument('--list-controls', action='store_true', help='List available camera controls and exits.')
    parser.add_argument('--clips_folder', type=str, default="clips", help='Folder to store DVR clips.')

    return parser

# endregion cli args
