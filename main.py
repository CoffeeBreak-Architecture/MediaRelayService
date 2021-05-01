from flask import Flask, jsonify, request
import socketio
app = Flask(__name__)

sio = socketio.Server()

from aiortc import (
    RTCPeerConnection,
)

@app.route('/positions/<id>', methods=['PATCH'])
def on_movement(id):
    print(request.json)
    return "YES"

@sio.on('clientConnect')
def on_client_connect (client_id):
    print ("Client has connected!")


def init_socket():
    return 0

def init_webrtc():
    return 0



if __name__ == "__main__":
    app.run(host="0.0.0.0")
    init_socket()
    init_webrtc();