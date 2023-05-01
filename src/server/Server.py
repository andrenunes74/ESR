import socket
import threading 
import concurrent.futures
import sys
import json
import time
sys.path.append('../')
from shared.ONodePacket import * 
from shared.StreamRequestTable import *

SERVER_UDP_PORT = 8017
NODE_UDP_PORT = 8017

class ServerSystem:
    network = None
    streams = None

    def __init__(self,streams):
        
        self.network = dict()
        self.streams = StreamRequestTable()

        f = open("../files/Teste5.json",'r')
        self.network = json.load(f)
        f.close()

        for stream in streams:
           self.streams.streams[stream] = {'state': StreamRequestTable.STANDBY, 'requesters': []}

    def getVizinhos(self, addr):
        if addr in self.network:
            return self.network[addr]
            #return self.network[addr]['DEFAULT']
        else: return None

    def activateRoute(self, stream, addr):
        self.streams.activateRoute(stream, addr)

    def deactivateRoute(self, stream, addr):
        self.streams.deactivateRoute(stream, addr, True)
        print(self.streams.getStreams())

    def getRoutes(self, stream):
        return self.streams.getStreamRequesters(stream)

class ServerWorker:

    def __init__(self, localIP):
        self.localIP = localIP

    def processUDP(self, serverSystem, addr, data, s : socket.socket):
        packet = ONodePacketFactory.deserialize(data)

        if packet.tipo == SIGNAL:
            self.processSignals(serverSystem, addr, packet)
        elif packet.tipo == AUTH:
            self.processAuth(serverSystem, addr, packet, s)
        elif packet.tipo == DELETE_ROUTE:
            addr = (packet.originIP, addr[1])
            self.processDeleteRoute(serverSystem, addr, packet)
        elif packet.tipo == RTSP_REQUEST:
            self.processRtspPacket(serverSystem, addr, packet)
        elif packet.tipo == RTSP_REPLY:
            self.processRTSPreply(addr, packet)

    def processSignals(self, serverSystem, addr, packet):
        pass
        #print('[SERVER] Received a signal from ' + str(packet.originIP))

    def processAuth(self, serverSystem, addr, packet,s : socket.socket):
        #print('[SERVER] Received a neighbour request from ' + str(addr[0]))
        vizinhos = serverSystem.getVizinhos(addr[0])
        
        if vizinhos is not None:
            response = ONodePacketFactory().create(NEIGHBOURS, [vizinhos])
            s.sendto(response.serialize(), (addr))

        else:
            print('[SERVER] No neighbours were found for ' + str(addr))

    def processDeleteRoute(self, serverSystem, addr, packet):
        print('[SERVER] Received a delete route from ' + str(addr[0]))
        vizinhos = packet.routesToDelete
        
        for vizinho in vizinhos:
            if vizinho in serverSystem.network[addr[0]]:
                serverSystem.network[addr[0]].remove(vizinho)
                
            if addr[0] in serverSystem.network[vizinho]:
                serverSystem.network[vizinho].remove(addr[0])
                response = ONodePacketFactory().create(DELETE_ROUTE, [[addr[0]], addr[0]])
                s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
                s.connect((vizinho, NODE_UDP_PORT))
                s.sendall(response.serialize())

    def processRtspPacket(self, serverSystem, addr, packet):
        data = packet.rtsp
        request = data.split('\n')
        line1 = request[0].split(' ')
        requestType = line1[0]

        # Get the media file name
        filename = line1[1]
        
        # Get the RTSP sequence number 
        seq = request[1].split(' ')
        
        session = str(request[2].split(' ')[1])
        reply = ''

        print('[SERVER WORKER] RECEIVED: ' + packet.rtsp)
        if requestType == 'PLAY':
            if filename in serverSystem.streams.getStreams():
                serverSystem.activateRoute(filename, packet.originIP)
                reply = 'RTSP/1.0 200 OK\nCSeq: ' + str(seq[1]) + '\nSession: ' + str(session)

            else:    
                reply = 'RTSP/1.0 404 FILE_NOT_FOUND\nCSeq: ' + str(seq[1]) + '\nSession: ' + str(session) 

            response = ONodePacketFactory.create(RTSP_REPLY, [filename, reply, self.localIP])
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.sendto(response.serialize(), (packet.originIP, NODE_UDP_PORT))
            print('[SERVER WORKER] SENT REPLY BACK: ' + str(response.tipo) + ' ' + reply + ' TO: ' + packet.originIP)

        elif requestType == 'TEARDOWN':
            serverSystem.deactivateRoute(filename, packet.originIP)
            print(packet.originIP + " TEARDOWN")

        else:
            return

class ServerListener:
    def __init__(self, localIP, localPort):
        self.localIP = localIP
        self.localPort = localPort
        self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.socket.bind((localIP,localPort))

    def start(self, serverSystem):
        print('[SERVER LISTENER] Listening for UDP packets at ' + self.localIP + '/' + str(self.localPort))
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            while True:
                data, addr = self.socket.recvfrom(1024)
                print('[SERVER LISTENER] Received data: ' + str(ONodePacketFactory.deserialize(data))+'from: '+ str(addr))
                executor.submit(ServerWorker(self.localIP).processUDP(serverSystem, addr, data,self.socket))

def sendSignals(serverSystem, localIP, localPort):
    s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    signalPacket = ONodePacketFactory.create(SIGNAL, [localIP])
    arr = signalPacket.serialize()

    while True:
        neighbours = serverSystem.getVizinhos(localIP)
        for neighbour in neighbours:
            s.sendto(arr, (neighbour, NODE_UDP_PORT))
            #print('[NODE] signal sent to ' + neighbour)
        
        s.sendto(arr, (localIP, NODE_UDP_PORT))
        time.sleep(5)   

def startRouteFlooding(serverSystem, localIP, localPort):
    s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    packet = ONodePacketFactory.create(FLOODING, [localIP, 0])
    arr = packet.serialize()

    #print('[SERVER] Started flooding')
    
    while True:
        vizinhos = serverSystem.getVizinhos(localIP)
        for vizinho in vizinhos:
            s.sendto(arr, (vizinho, NODE_UDP_PORT))
            #print('[SERVER] Flooding packet sent to ' + vizinho)
        time.sleep(5)

class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		try:
			self.file = open('../files/'+filename, 'rb')
		except:
			raise IOError
		self.frameNum = 0
		
	def nextFrame(self):
		"""Get next frame."""
		data = self.file.read(5) # Get the framelength from the first 5 bits
		if data: 
			framelength = int(data)
							
			# Read the current frame
			data = self.file.read(framelength)
			self.frameNum += 1
		return data
		
	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum
	
class StreamWorker:
        def __init__(self, serverSystem, stream, serverIP):
                self.serverSystem = serverSystem
                self.stream = stream
                self.videoStream = VideoStream(stream)
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.serverIP = serverIP

        def start(self):
                print("[StreamWorker] Started streaming " + self.stream)
                while True:
                        data = self.videoStream.nextFrame()
                        if data:
                                frameNumber = self.videoStream.frameNbr()
                                
                                for addr in self.serverSystem.getRoutes(self.stream):
                                        try:
                                                rtpPacket = self.makeRtp(data, frameNumber)
                                                onodePacket = ONodePacketFactory.create(RTP, [self.stream, rtpPacket, self.serverIP])
                                                self.socket.sendto(onodePacket.serialize(),(addr,NODE_UDP_PORT))
                                        except Exception as e:
                                                print(e)
                                                print("Connection Error")
                                                #print('-'*60)
                                                #traceback.print_exc(file=sys.stdout)
                                                #print('-'*60)
                                time.sleep(1/30)
                        else:
                                frameNumber = self.videoStream.frameNbr()
                                self.videoStream = VideoStream(self.stream)
                                self.videoStream.frameNum = frameNumber

                self.serverSystem.deactivateRoute(self.stream)

        def makeRtp(self, payload, frameNbr):
                """RTP-packetize the video data."""
                version = 2
                padding = 0
                extension = 0
                cc = 0
                marker = 0
                pt = 26 # MJPEG type
                seqnum = frameNbr
                ssrc = 0 
                
                rtpPacket = RtpPacket()
                
                rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)
                
                return rtpPacket

def main():
    args = sys.argv[1:]
    localIP = args[0]
    localPort = SERVER_UDP_PORT

    streams = []

    f = open('../files/Streams.json','r')
    streams = json.load(f)['streams']
    f.close()

    serverSystem = ServerSystem(streams)
    threading.Thread(target=ServerListener(localIP,localPort).start,args=[serverSystem]).start()

    for stream in streams:
        threading.Thread(target=StreamWorker(serverSystem, stream, args[0]).start).start()
        print(stream)

    threading.Thread(target=startRouteFlooding, args=[serverSystem, args[0], NODE_UDP_PORT]).start()
    sendSignals(serverSystem, localIP, NODE_UDP_PORT)
    
if __name__ == '__main__':
    main()