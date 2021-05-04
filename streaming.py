from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay


class StreamClientBroadcast:
    def __init__(self, track_in):
        self.track_in = track_in
        self.relay = MediaRelay()

    def subscribe(self):
        return self.relay.subscribe(self.track_in)

    def close(self):
        self.track_in.close()


class ClientNearbyState:
    def __init__(self, nearby):
        self.nearby = nearby

    def get_changes(self, prev, threshold):
        nearby = self.nearby
        prev_nearby = prev

        to_disconnect = []
        to_connect = []

        for key in nearby:
            if key not in prev_nearby:
                to_connect.append(key)

        for key in prev_nearby:
            if key not in nearby:
                to_disconnect.append(key)

        return {'to_disconnect': to_disconnect, 'to_connect': to_connect}




