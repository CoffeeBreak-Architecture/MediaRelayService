import argparse
import asyncio
import json
import logging
import os
import ssl

import cv2
from aiohttp import web
import aiohttp_cors
from av import VideoFrame

from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.mediastreams import MediaStreamError
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaRelay

class Peer:
    def __init__(self, pc):
        self.pc = pc
        self.tracks = {}

ROOT = os.path.dirname(__file__)
relay = MediaRelay()
clients = {}
listeners = set()
listenerTracks = set()
globaltrack = None;

async def listener_sdp(request):
    params = await request.json()
    username = params['name']
    offer = RTCSessionDescription(sdp=params['sdp'], type='offer')
    print(params)
    pc = RTCPeerConnection()
    print('Number of listeners: ', len(listeners))
    pc.addTrack(relay.subscribe(clients[username].tracks['audio']))
    pc.addTrack(relay.subscribe(clients[username].tracks['video']))
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    listeners.add(pc)
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s", pc.connectionState)
        if pc.connectionState == ("failed") or pc.connectionState == ("closed"):
            await pc.close()
            listeners.discard(pc)
            print(len(listeners))
    return web.Response(
        content_type='application/json',
        text=json.dumps({
            'sdp': pc.localDescription.sdp,
            'type': 'answer'
        })
    )

async def client_sdp(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params['sdp'], type='offer')
    recorder = MediaBlackhole()
    pc = RTCPeerConnection()
    username = params['name']
    print(username)
    clients[username] = Peer(pc)
    print('Number of clients: ', len(clients))
    for x in clients:
        print(x)
    @clients[username].pc.on('track')
    async def on_track(track):
        global globaltrack
        globaltrack = track;
        recorder.addTrack(globaltrack)
        clients[username].tracks[track.kind] = track
    @clients[username].pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s", pc.connectionState)
        if clients[username].pc.connectionState == ("failed") or clients[username].pc.connectionState == ("closed"):
            await clients[username].pc.close()
            del clients[username]
    await clients[username].pc.setRemoteDescription(offer)
    answer = await clients[username].pc.createAnswer()
    await clients[username].pc.setLocalDescription(answer)
    await recorder.start();
    return web.Response(
        content_type='application/json',
        text=json.dumps({
            'sdp': clients[username].pc.localDescription.sdp,
            'type': 'answer'
        })
    )

async def index(request):
    content = open(os.path.join(ROOT, "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)


async def javascript(request):
    content = open(os.path.join(ROOT, "client.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)

async def close_connection(request):
    params = await request.json()
    username = params['name']
    clients[username].pc.close()
    del clients[username]

async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in clients] + [pc.close() for pc in listeners]
    await asyncio.gather(*coros)
    clients.clear()
    listeners.clear()

if __name__ == '__main__':
    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_post('/offer', client_sdp)
    app.router.add_post('/listener', listener_sdp)
    app.router.add_post('/shutdown', close_connection)
    app.router.add_get("/client.js", javascript)
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
    })

    for route in list(app.router.routes()):
        cors.add(route)

    web.run_app(app, port='80')