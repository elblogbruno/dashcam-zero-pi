import libcamera
from spyglass.camera_options import process_controls
from picamera2 import Picamera2

def init_camera(
        clip_width: int,
        clip_height: int,
        stream_width: int,
        stream_height: int,
        fps: int,
        autofocus: str,
        lens_position: float,
        autofocus_speed: str,
        upsidedown=False,
        flip_horizontal=False,
        flip_vertical=False,
        control_list: list[list[str]]=[],
        tuning_filter=None,
        tuning_filter_dir=None):

    tuning = None

    if tuning_filter:
        params = {'tuning_file': tuning_filter}
        if tuning_filter_dir:
            params['dir'] = tuning_filter_dir
        tuning = Picamera2.load_tuning_file(**params)

    picam2 = Picamera2(tuning=tuning)
    controls = {'FrameRate': fps}

    c = process_controls(picam2, [tuple(ctrl) for ctrl in control_list])
    controls.update(c)

    if 'AfMode' in picam2.camera_controls:
        controls['AfMode'] = autofocus
        controls['AfSpeed'] = autofocus_speed
        if autofocus == libcamera.controls.AfModeEnum.Manual:
            controls['LensPosition'] = lens_position
    else:
        print('Attached camera does not support autofocus')

    transform = libcamera.Transform(hflip=int(flip_horizontal or upsidedown), vflip=int(flip_vertical or upsidedown))

    mode = picam2.sensor_modes[1]

    print(mode)

    picam2.configure(picam2.create_video_configuration(main={'size': (clip_width, clip_height)}, 
                                                       lores={"size": (stream_width, stream_height)}, 
                                                       controls=controls, 
                                                       transform=transform,
                                                       sensor={'output_size': mode['size'], 'bit_depth': mode['bit_depth']}))

    return picam2
