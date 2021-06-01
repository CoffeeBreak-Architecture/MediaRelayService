import asyncio
import json
import os


from aiohttp import web
import aiohttp_cors
from av import VideoFrame

from aiortc import RTCPeerConnection, RTCSessionDescription,
from aiortc.mediastreams import MediaStreamError
from aiortc.contrib.media import MediaBlackhole, MediaRelay
class Peer:
    def __init__(self, pc):
        self.pc = pc
        self.tracks = {}
        self.relay = MediaRelay()

ROOT = os.path.dirname(__file__)
clients = {}
listeners = set()
globaltrack = None;

async def listener_connection(request):
    params = await request.json()
    username = params['name']
    offer = RTCSessionDescription(sdp=params['sdp'], type='offer')
    pc = RTCPeerConnection()
    print('Number of listeners: ', len(listeners))
    #Adds the requested clients tracks subscribed to the MediaRelay
    pc.addTrack(clients[username].relay.subscribe(clients[username].tracks['audio']))
    pc.addTrack(clients[username].relay.subscribe(clients[username].tracks['video']))
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    listeners.add(pc)
    #Handles removal of dead connections
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

async def client_connection(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params['sdp'], type='offer')
    recorder = MediaBlackhole()
    pc = RTCPeerConnection()
    username = params['name']
    print(username)
    #Inits a clients dict entry
    clients[username] = Peer(pc)
    print('Number of clients: ', len(clients))
    #Remote track event. If fired
    @clients[username].pc.on('track')
    async def on_track(track):
        clients[username].tracks[track.kind] = track
        recorder.addTrack(clients[username].relay.subscribe(track))
    @clients[username].pc.on("connectionstatechange")
    #Handles removal of dead connections
    async def on_connectionstatechange():
        print("Connection state is %s", pc.connectionState)
        if clients[username].pc.connectionState == ("failed") or clients[username].pc.connectionState == ("closed"):
            await clients[username].pc.close()
            del clients[username]
    await clients[username].pc.setRemoteDescription(offer)
    answer = await clients[username].pc.createAnswer()
    await clients[username].pc.setLocalDescription(answer)
    #Starts media playing in order to stream to listeners
    await recorder.start();
    return web.Response(
        content_type='application/json',
        text=json.dumps({
            'sdp': clients[username].pc.localDescription.sdp,
            'type': 'answer'
        })
    )

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
    #Exposes paths for function API calls
    app.router.add_post('/offer', client_connection)
    app.router.add_post('/listener', listener_connection)
    app.router.add_post('/shutdown', close_connection)
    
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