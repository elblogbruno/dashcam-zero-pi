import io
import logging
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from threading import Condition
from spyglass.url_parsing import check_urls_match, get_url_params
from spyglass.exif import create_exif_header
from spyglass.camera_options import parse_dictionary_to_html_page, process_controls
from . import logger
import uvicorn
from picamera2.encoders import MJPEGEncoder 
from picamera2.outputs import FileOutput

from spyglass.dvr import DVR
from fastapi.responses import StreamingResponse

import time
import asyncio

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.event = asyncio.Event()

    def write(self, buf):
        self.frame = buf
        self.event.set()

    async def read(self):
        await self.event.wait()
        self.event.clear()
        return self.frame


from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio


# async def print_task(s): 
#     while True:
#         print('Hello')
#         await asyncio.sleep(s)

        
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run at startup
    asyncio.create_task(dvr.start_recording())
    dvr.start_gather_gps_thread()
    yield
    # Run on shutdown (if required)
    print('Shutting down...')


app = FastAPI(lifespan=lifespan)
# app = FastAPI()

output = StreamingOutput()
exif_header = create_exif_header(0)

camera = None
bind_address = None
port = None
dvr = None

@app.get("/stream")
async def stream(request: Request):
    print("Starting streaming again.")

    output = StreamingOutput()
    encoder = MJPEGEncoder()
    # camera.pre_callback = apply_timestamp
    camera.start_encoder(encoder, FileOutput(output), name="lores")
    # camera.start()

    time.sleep(1)

    async def generate():
        try:
            while True:
                frame = await output.read()
                # print(f"Frame length: {len(frame)}")  # Debugging frame length
                yield b'--FRAME\r\n'
                yield b'Content-Type: image/jpeg\r\n'
                yield b'Content-Length: ' + str(len(frame)).encode() + b'\r\n'
                yield b'\r\n' + frame + b'\r\n'
        except asyncio.CancelledError:
            print("Client disconnected, stopping recording.")
            # camera.stop_encoder()
            encoder.stop()
            raise

    async def monitor_disconnect():
        await request.is_disconnected()
        raise asyncio.CancelledError

    loop = asyncio.get_event_loop()
    loop.create_task(monitor_disconnect())

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=FRAME")

@app.get("/videos")
async def list_videos(start_time: int = 0, end_time: int = 0):
    return dvr.list_clips(start_time, end_time)

@app.get("/status")
async def status():
    return dvr.get_system_status()

@app.get("/videos/{clip_id}")
async def stream_video_clip(clip_id: str):
    file_path = f"{dvr.clips_folder}/{clip_id}.h264" 

    def iterfile():
        with open(file_path, "rb") as file_like:
            yield from file_like
    return StreamingResponse(iterfile(), media_type="video/mp4")

@app.get("/read_mode")
async def read_mode():
    # Stops this program recording 
    exit(1)

@app.get("/controls")
async def controls(request: Request):
    parsed_controls = get_url_params(str(request.url))
    parsed_controls = parsed_controls if parsed_controls else None
    processed_controls = process_controls(camera, parsed_controls)
    camera.set_controls(processed_controls)
    content = parse_dictionary_to_html_page(camera, parsed_controls, processed_controls).encode('utf-8')
    return Response(content, media_type='text/html')


@app.on_event("startup")
async def startup_event():
    logger.info('Server listening on %s:%d', bind_address, port)
    logger.info('Streaming endpoint: /stream')
    logger.info('Snapshot endpoint: /snapshot')
    logger.info('Controls endpoint: /controls')

    # dvr.start_recording_thread()


def run_server(server_bind_address,
               server_port,
               picamera,
               pidvr: DVR,
               stream_url='/stream',
               snapshot_url='/snapshot',
               orientation_exif=0):
    
    global exif_header
    exif_header = create_exif_header(orientation_exif)

    global camera
    camera = picamera

    global bind_address
    bind_address = server_bind_address

    global port
    port = server_port

    global dvr
    dvr = pidvr

    uvicorn.run(app, host=bind_address, port=port)