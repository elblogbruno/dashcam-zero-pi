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

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


app = FastAPI()
output = StreamingOutput()
exif_header = create_exif_header(0)

camera = None
bind_address = None
port = None


@app.get("/stream")
async def stream(request: Request):
    async def generate():
        while True:
            with output.condition:
                logging.debug('Waiting for frame')
                output.condition.wait()
                frame = output.frame
            yield b'--FRAME\r\n'
            if exif_header is None:
                yield frame
            else:
                yield exif_header + frame[2:]
            yield b'\r\n'

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=FRAME")


@app.get("/snapshot")
async def snapshot(request: Request):
    with output.condition:
        output.condition.wait()
        frame = output.frame
    return StreamingResponse(frame, media_type="image/jpeg")


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


def run_server(server_bind_address,
               server_port,
               picamera,
               pioutput: StreamingOutput,
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

    global output
    output = pioutput

    uvicorn.run(app, host=bind_address, port=port)