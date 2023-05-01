import pickle, ast, sys
sys.path.append('../')
from shared.RtpPacket import RtpPacket

SIGNAL = 1
AUTH = 2
NEIGHBOURS = 3
CORRECTION_REQUEST = 4
FLOODING = 5
DELETE_ROUTE = 6
RTP = 7
RTSP_REQUEST = 8
RTSP_REPLY = 9

HEADER_SIZE = 8
PACKET_SIZE = 512

class ONodePacketSignal:
    def __init__(self, origin):
        self.tipo = SIGNAL
        self.originIP = origin

    @classmethod
    def deserialize(self, arr):
        self.tipo = int.from_bytes([arr[0], arr[1]], 'big')
        self.originIP = arr[2:].decode("utf-8")
        return self

    def serialize(self):
        packet = bytearray()
        packet += bytearray((self.tipo).to_bytes(2,'big'))
        packet += self.originIP.encode("utf-8")
        return packet

class ONodePacketAuth:
    
    def __init__(self, originIP):
        self.tipo = AUTH
        self.originIP = originIP
   
    @classmethod
    def deserialize(self, arr):
        self.tipo = int.from_bytes([arr[0], arr[1]], 'big')
        self.originIP = arr[2:].decode("utf-8")
        return self

    def serialize(self):
        packet = bytearray()
        packet += bytearray((self.tipo).to_bytes(2,'big'))
        packet += self.originIP.encode("utf-8")
        return packet

class ONodePacketNeighbours:
    
    def __init__(self, neighbours):
        self.tipo = NEIGHBOURS
        self.neighbours = neighbours
   
    @classmethod
    def deserialize(self, arr):
        self.tipo = NEIGHBOURS
        self.neighbours = ast.literal_eval(arr[2:].decode("utf-8"))
        return self

    def serialize(self):
        packet = bytearray()
        packet += bytearray((self.tipo).to_bytes(2,'big'))
        packet += bytearray(str(self.neighbours).encode("utf-8"))
        return packet

class ONodePacketCorrectionRequest:
    
    def __init__(self, inactiveNeighbours, originIP):
        self.tipo = CORRECTION_REQUEST
        self.inactiveNeighbours = inactiveNeighbours
        self.originIP = originIP

    @classmethod
    def deserialize(self, arr):
        self.tipo = CORRECTION_REQUEST
        temp = arr[2:].decode("utf-8")
        temp = temp.split(";")
        self.inactiveNeighbours = ast.literal_eval(temp[0])
        self.originIP = temp[1]
        return self

    def serialize(self):
        packet = bytearray()
        packet += bytearray((self.tipo).to_bytes(2,'big'))
        packet += bytearray((str(self.inactiveNeighbours) + ';').encode("utf-8"))
        packet += self.originIP.encode("utf-8")
        return packet

class ONodePacketFlooding:
    
    def __init__(self, originIP, weight):
        self.tipo = FLOODING
        self.originIP = originIP
        self.weight = weight
         
    @classmethod
    def deserialize(self, arr):
        self.tipo = FLOODING
        self.weight = int.from_bytes([arr[2], arr[3],arr[4],arr[5]], 'big')
        self.originIP = arr[6:].decode("utf-8")
        return self

    def serialize(self):
        packet = bytearray()
        packet += bytearray((self.tipo).to_bytes(2,'big'))
        packet += bytearray((self.weight).to_bytes(4,'big'))
        packet += self.originIP.encode("utf-8")
        return packet

class ONodePacketDeleteRoute:
    
    def __init__(self, routesToDelete, originIP):
        self.tipo = DELETE_ROUTE
        self.routesToDelete = routesToDelete
        self.originIP = originIP
        
    @classmethod
    def deserialize(self, arr):
        self.tipo = DELETE_ROUTE
        temp = arr[2:].decode("utf-8")
        temp = temp.split(";")
        self.routesToDelete = ast.literal_eval(temp[0])
        self.originIP = temp[1]
        return self

    def serialize(self):
        packet = bytearray()
        packet += bytearray((self.tipo).to_bytes(2,'big'))
        packet += bytearray((str(self.routesToDelete) + ";").encode("utf-8"))
        packet += self.originIP.encode("utf-8")
        return packet

class ONodePacketRtp:

    def __init__(self, stream, rtp, origin):
        self.tipo = RTP
        self.stream = stream
        self.rtp = rtp
        self.originIP = origin
   
    @classmethod
    def deserialize(self, arr):
        self.tipo = RTP
        size = int.from_bytes(arr[2:6], 'big')
        self.stream = arr[6:(6+size)].decode("utf-8")

        sizeIP = int.from_bytes(arr[(6+size):(10+size)], 'big')    
        self.originIP = arr[10+size:10+size+sizeIP].decode("utf-8")
        self.rtp = RtpPacket()
        self.rtp.decode(arr[(10+size+sizeIP):])
         
        return self

    def serialize(self):
        packet = bytearray()
        packet += bytearray((self.tipo).to_bytes(2,'big'))
        stream_bytes = bytearray(str(self.stream).encode("utf-8"))
        packet += len(stream_bytes).to_bytes(4, 'big')
        packet += stream_bytes
        packet += len(self.originIP).to_bytes(4, 'big')
        packet += self.originIP.encode("utf-8")
        packet += self.rtp.getPacket()
        
        return packet

class ONodePacketRtspRequest:
    
    def __init__(self, rtsp, origin):
        self.tipo = RTSP_REQUEST
        self.rtsp = rtsp
        self.originIP = origin

    @classmethod
    def deserialize(self, arr):
        self.tipo = RTSP_REQUEST
        temp = ""
        temp = arr[2:].decode("utf-8")
        temp = temp.split(";")
        self.originIP = temp[0]
        self.rtsp = temp[1]
        return self

    def serialize(self):
        packet = bytearray()
        packet += bytearray((self.tipo).to_bytes(2,'big'))

        packet += bytearray((self.originIP + ";").encode("utf-8"))
        packet += bytearray(self.rtsp.encode("utf-8"))
        return packet

class ONodePacketRtspReply:
    
    def __init__(self, stream, rtspReply, origin):
        self.tipo = RTSP_REPLY
        self.stream = stream
        self.rtsp = rtspReply
        self.originIP = origin
   
    @classmethod
    def deserialize(self, arr):
        self.tipo = int.from_bytes([arr[0], arr[1]], 'big')
        size = int.from_bytes(arr[2:6], 'big')
        self.stream = arr[6:(6+size)].decode("utf-8")
        temp = ""
        temp = arr[(6+size):].decode("utf-8")
        temp = temp.split(";")
        self.originIP = temp[0]
        self.rtsp = temp[1]

        return self

    def serialize(self):
        packet = bytearray()
        packet += bytearray((self.tipo).to_bytes(2,'big'))
        stream_bytes = bytearray(str(self.stream).encode("utf-8"))
        packet += len(stream_bytes).to_bytes(4, 'big')
        packet += stream_bytes
        packet += bytearray((self.originIP + ";").encode("utf-8"))
        packet += bytearray(self.rtsp.encode("utf-8"))
        return packet

class ONodePacketFactory:

    NODE_UDP_PORT = 8000
    NODE_TCP_PORT = 8888

    def __init__(self):
        pass
    
    @classmethod 
    def create(self, tipo, args):
        if tipo == SIGNAL:
            return ONodePacketSignal(args[0])
        elif tipo == AUTH:
            return ONodePacketAuth(args[0])
        elif tipo == NEIGHBOURS:
            return ONodePacketNeighbours(args[0])
        elif tipo == CORRECTION_REQUEST:
            return ONodePacketCorrectionRequest(args[0], args[1])
        elif tipo == FLOODING:
            return ONodePacketFlooding(args[0], args[1])
        elif tipo == DELETE_ROUTE:
            return ONodePacketDeleteRoute(args[0], args[1])
        elif tipo == RTP:
            return ONodePacketRtp(args[0], args[1], args[2])
        elif tipo == RTSP_REQUEST:
            return ONodePacketRtspRequest(args[0], args[1])
        elif tipo == RTSP_REPLY:
            return ONodePacketRtspReply(args[0], args[1], args[2])

    @classmethod
    def deserialize(self, arr):
        packet = None
        try:
            tipo = int.from_bytes([arr[0], arr[1]], 'big')
        except:
            tipo = None

        if tipo == SIGNAL:
            packet = ONodePacketSignal.deserialize(arr)
        elif tipo == AUTH:
            packet = ONodePacketAuth.deserialize(arr)
        elif tipo == NEIGHBOURS:
            packet = ONodePacketNeighbours.deserialize(arr)
        elif tipo == CORRECTION_REQUEST:
            packet = ONodePacketCorrectionRequest.deserialize(arr)
        elif tipo == FLOODING:
            packet = ONodePacketFlooding.deserialize(arr)
        elif tipo == DELETE_ROUTE:
            packet = ONodePacketDeleteRoute.deserialize(arr)
        elif tipo == RTP:
            packet = ONodePacketRtp.deserialize(arr)
        elif tipo == RTSP_REQUEST:
            packet = ONodePacketRtspRequest.deserialize(arr)
        elif tipo == RTSP_REPLY:
            packet = ONodePacketRtspReply.deserialize(arr)

        return packet
