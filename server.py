import argparse
import asyncio
import json
import logging
import os
import ssl
import uuid

from aiohttp import web
from av import VideoFrame

from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaRelay

ROOT = os.path.dirname(__file__)

logger = logging.getLogger("pc")
pcs = {}
relay = MediaRelay()
trackUser = {}
async def index(request):
    content = open(os.path.join(ROOT, "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)


async def javascript(request):
    content = open(os.path.join(ROOT, "client.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    username = params["name"]
    peer = Peer(RTCPeerConnection())
    pc_id = "PeerConnection(%s)" % uuid.uuid4()
    pcs[pc_id] = peer
    print(pc_id)
    def log_info(msg, *args):
        logger.info(pc_id + " " + msg, *args)

    log_info("Created for %s", request.remote)

    # prepare local media
    if args.record_to:
        recorder = MediaRecorder(args.record_to)
    else:
        recorder = MediaBlackhole()

    @pcs[pc_id].pc.on("connectionstatechange")
    async def on_connectionstatechange():
        log_info("Connection state is %s", pcs[pc_id].pc.connectionState)
        if pcs[pc_id].pc.connectionState == "failed":
            pcs[pc_id].pc.close()
            pcs.discard(pcs[pc_id].pc)
    @pcs[pc_id].pc.on("track")
    def on_track(track, ):
        log_info("Track %s received", track.kind)
        for id in pcs:
            if checkKey(pcs[id].tracks, username) != True:
                pcs[id].tracks[username] = set()
                pcs[id].tracks[username].add(PublicTrack(track, False))
            else:
                pcs[id].tracks[username].add(PublicTrack(track, False))
        log_info(track.id)
        for id in pcs:
            for key in pcs[id].tracks:
                for publictrack in pcs[id].tracks[key]:
                    if(publictrack.used == False):
                        log_info("track added")
                        if publictrack.track.kind == "audio":
                            pcs[id].pc.addTrack(publictrack.track)
                            pcs[id].pc.addTransceiver("audio", "sendrecv")
                            print(id)
                            publictrack.used = True
                            if args.record_to:
                                recorder.addTrack(relay.subscribe(publictrack.track))
                        elif publictrack.track.kind == "video":
                            publictrack.used = True
                            pcs[id].pc.addTrack(publictrack.track)
                            print(id)
                            if args.record_to:
                                recorder.addTrack(relay.subscribe(publictrack.track))
        
                

        @track.on("ended")
        async def on_ended():
            log_info("Track %s ended", track.kind)
            await recorder.stop()
    # handle offer
    await pcs[pc_id].pc.setRemoteDescription(offer)
    await recorder.start()

    # send answer
    answer = await pcs[pc_id].pc.createAnswer()
    await pcs[pc_id].pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pcs[pc_id].pc.localDescription.sdp, "type": pcs[pc_id].pc.localDescription.type}
        ),
    )


async def on_shutdown(app):
    # close peer connections
    coros = [pc.pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

def checkKey(dict, key):
      
    if key in dict.keys():
        return True
    else:
        return False

class PublicTrack:
    def __init__(self, track, used):
        self.track = track
        self.used = used
class Peer:
    def __init__(self, pc):
        self.pc = pc
        self.tracks = {}
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="WebRTC audio / video / data-channels demo"
    )
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port for HTTP server (default: 8080)"
    )
    parser.add_argument("--record-to", help="Write received media to a file."),
    parser.add_argument("--verbose", "-v", action="count")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if args.cert_file:
        ssl_context = ssl.SSLContext()
        ssl_context.load_cert_chain(args.cert_file, args.key_file)
    else:
        ssl_context = None

    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_post("/offer", offer)
    web.run_app(
        app, access_log=None, host=args.host, port=args.port, ssl_context=ssl_context
    )

