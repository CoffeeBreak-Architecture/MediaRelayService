from flask import Flask, jsonify, request
from flask_socketio import SocketIO, send, emit
from distance_measure import get_within_threshold
from streaming import StreamClientBroadcast, ClientNearbyState
from aiortc import RTCPeerConnection, RTCSessionDescription
import asyncio

app = Flask(__name__)
loop = asyncio.get_event_loop()

signalling = SocketIO(app, cors_allowed_origins='*')
connection_distance_threshold = 256

id_mapping = {}
positions = {}
broadcasts = {}
nearby_states = {}
connections = {}


@app.route('/threshold', methods=['POST'])
def update_threshold():
    json = request.json
    global connection_distance_threshold  # i don't understand python
    connection_distance_threshold = json['threshold']


@app.route('/positions/<client_id>', methods=['POST'])
def on_movement(client_id):
    json = request.json
    x = json['x']
    y = json['y']
    update_connections(client_id, x, y)
    return "", 200


def update_connections(client_id, x, y):
    set_client_position(client_id, x, y)

    prev = None
    if client_id in nearby_states:
        prev = nearby_states[client_id]
    else:
        prev = ClientNearbyState({})

    threshold = connection_distance_threshold
    nearby = get_within_threshold(x, y, positions, threshold)  # arbitrary distance, set with POST later.
    new_state = ClientNearbyState(nearby)
    changes = new_state.get_changes(prev.nearby, threshold)
    nearby_states[client_id] = new_state
    to_update = []

    for to_disconnect in changes['to_disconnect']:
        disconnect(client_id, to_disconnect)
        to_update.append(to_disconnect)

    for to_connect in changes['to_connect']:
        connect(client_id, to_connect)
        to_update.append(to_connect)

    for other in to_update:
        update_connections(other, positions[other]['x'], positions[other]['y'])


def connect(receiver_id, broadcaster_id):
    print("Connecting '" + receiver_id + "' to: '" + broadcaster_id + "'...")


def disconnect(receiver_id, broadcaster_id):
    print("Disconnecting '" + receiver_id + "' from: '" + broadcaster_id + "'...")


def disconnect_from_all(client_id):
    pass


async def offer_connection(target_client_id):
    connection = RTCPeerConnection()
    connection.addTransceiver('video', direction='recvonly')
    connection.addTransceiver('audio', direction='recvonly')
    channel = connection.createDataChannel('data')
    print('Offering connection to: \'' + target_client_id + '\'.')

    offer = await connection.createOffer()
    local_id = id_mapping[target_client_id]

    @signalling.on('answerCall')
    def receive_call_answer(answer):
        answer = RTCSessionDescription(sdp=answer['sdp'], type=answer['type'])
        loop.run_until_complete(connection.setRemoteDescription(answer))
        connections[target_client_id] = connection
        print(answer)

    await connection.setLocalDescription(offer)

    @connection.on('connectionstatechange')
    def on_connection_state_change():
        print("Connection state is %s" % connection.connectionState)
        if connection.connectionState == "failed":
            connection.close()
            connections.pop(target_client_id)

    signalling.emit('offerCall', {'sdp': offer.sdp, 'type': offer.type}, room=local_id)


# this feels terrible to do, but I see no other simple options rn.
# Alternatively we would need to find a way to generate SDPs elsewhere and send it to this server.
# Maybe for a potential future version?
@signalling.on('selfReportId')
def on_client_self_report_id(client_id):
    sid = request.sid
    set_id_mapping(client_id, sid)
    loop.run_until_complete(offer_connection(client_id))
    print("Client with local SID " + sid + " has self-reported their room SID to be: " + client_id)


@signalling.on('connect')
def on_connect():
    print('Client connected.')
    sid = request.sid
    emit('onSelfConnectedToStreamServer')


@signalling.on('disconnect')
def on_disconnect():
    print('Client disconnected: ' + request.sid)

    id_mapping_inverse = id_mapping.keys()
    key = id_mapping_inverse[request.sid]

    positions.pop(key)
    broadcasts.pop(key)
    nearby_states.pop(key)
    disconnect_from_all(key)


def set_id_mapping(client_id, sid):
    id_mapping[client_id] = sid


def set_client_position(client_id, x, y):
    positions[client_id] = {'id': client_id, 'x': x, 'y': y}


def compute_client_streaming_changes(client_id):
    position = positions[client_id]


if __name__ == "__main__":
    app.run(host="0.0.0.0")
    print("Media Relay Server is running.")
