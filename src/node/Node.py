import datetime
import threading, sys, socket
import concurrent.futures
sys.path.append('../')
from shared.ONodePacket import * 
import time
from tkinter import *
import tkinter.messagebox as msgbox
from node.ClientWorker import *
from shared.StreamRequestTable import *

SERVER_UDP_PORT = 8017
NODE_UDP_PORT = 8017

class RoutingTable():
    neighbours = None
    TIMEOUT = 15
    
    def __init__(self):
        self.neighbours = dict()
        self.best = None
        self.changed = True

    def addNewNeighbour(self, address, pathToServer, pathWeight, isAlternativeRoute, createdByMe):
        l = threading.Lock()
        with l:
            if address not in self.neighbours.keys():
                self.neighbours[address] = {'signalLastUpdate': datetime.datetime.now(), 'weight': -1, 'createdByMe': createdByMe, 'alternative': isAlternativeRoute, 'floodingLastUpdate': datetime.datetime.now()}
                self.changed = True
                
    def removeNeighbours(self, addresses):
        l = threading.Lock()
        with l:
            for address in addresses:
                if address in self.neighbours.keys() and self.neighbours[address]['alternative']:
                    self.neighbours.pop(address)
    
    def getFloodingUpdate(self, address):
        l = threading.Lock()

        with l:
            return self.neighbours[address]['floodingLastUpdate']
        
    def getCreatedByMe(self, address):
        l = threading.Lock()
        with l:
            return self.neighbours[address]['createdByMe']

    def removeAlternatives(self, alternatives):
        l = threading.Lock()
        with l:
            res = []
            for alternative in alternatives:
                if self.neighbours[alternative]['createdByMe']:
                    self.neighbours.pop(alternative)
                    if alternative not in res:
                        res.append(alternative)
            return res
                
    def getAlternative(self, address):
        l = threading.Lock()
        with l:
            return self.neighbours[address]['alternative']

    def updateFlooding(self, address, weight):
        l = threading.Lock()
        with l:
            if address in self.neighbours:
                self.neighbours[address]['signalLastUpdate'] = datetime.datetime.now()
                self.neighbours[address]['floodingLastUpdate'] = datetime.datetime.now()
                self.neighbours[address]['weight'] = weight
                self.changed = True
                
    def getLowestWeight(self):
        lowest = float('inf')
        l = threading.Lock()
        with l:
            for address in self.neighbours.keys():
                if self.neighbours[address]['weight'] < lowest and self.neighbours[address]['weight'] >= 0:
                    lowest = self.neighbours[address]['weight']
            return lowest

    def updateSignals(self, address):
        l = threading.Lock()
        with l:
            self.changed = True
            if address in self.neighbours:
                self.neighbours[address]['signalLastUpdate'] = datetime.datetime.now() 

    def getSignalsUpdate(self, address):
        l = threading.Lock()
        with l:
            return self.neighbours[address]['signalLastUpdate']

    def getTypeOfRoute(self, address):
        l = threading.Lock()
        with l:
            return self.neighbours[address]['alternative']

    def getpathweight(self, address):
        l = threading.Lock()
        with l:
            if address not in self.neighbours.keys():
                return -1 
            return self.neighbours[address]['weight']

    def getAllAlternatives(self):
        ret = []
        
        for key, value in self.neighbours.items():
            if value['alternative']:
                ret.append(key)
                
        return ret

    def getBestPathToServer(self):
        best = None
        temp = float('inf') 
    
        l = threading.Lock()
        with l:
            if self.changed:
                for key, value in self.neighbours.items():
                    diff_signal = datetime.datetime.now() - value['signalLastUpdate']
                    diff_flooding = datetime.datetime.now() - value['floodingLastUpdate']
                    #print('[FINDING BEST PATH TO SERVER] ' + key + ' ' + str(value['weight']) + ' ' + str(diff_signal.total_seconds()) + ' ' + str(diff_flooding.total_seconds()) + ' ' + str(value['alternative']))
                    if diff_signal.total_seconds() < self.TIMEOUT and diff_flooding.total_seconds() < self.TIMEOUT and value['weight'] >= 0:
                        if best is None:
                            temp = value['weight']
                            best = key
                        
                        elif value['weight'] < temp and not value['alternative']:
                            temp = value['weight']
                            best = key
                            
                self.changed = best != self.best
                self.best = best
                        
                return best
            
            else:
                return self.best

    def getNeighbours(self):
        l = threading.Lock()
        with l:
            return self.neighbours.keys()
        
    def getDeadNeighbours(self):
        ret = []
        l = threading.Lock()
        with l:
            for key, value in self.neighbours.items():
                diff = datetime.datetime.now() - value['signalLastUpdate']
                if diff.total_seconds() > self.TIMEOUT:
                    ret.append(key)
            return ret

class Node:
    def __init__(self):
        self.routingTable= RoutingTable()
        self.firstFlooding = False
        self.startTime = datetime.datetime.now()
        self.session = 0
        self.streamRequestTable = StreamRequestTable()
        self.watchList = dict()
    
    def getFirstFlooding(self):
        diff = datetime.datetime.now() - self.startTime
        return self.firstFlooding or diff.total_seconds() > RoutingTable.TIMEOUT
    
    def addToWatchList(self, name):
        l = threading.Lock()
        with l:
            self.session += 1
            self.watchList[self.session] = {'name': name, 'client': False, 'RTPqueue': queue.Queue(), 'ReplyQueue': queue.Queue()}
            return self.session

    def startWatching(self, session):
        l = threading.Lock()
        with l:
            self.watchList[session]['client'] = True

    def stopWatching(self, session):
        l = threading.Lock()
        with l:
            self.watchList[session]['client'] = False
    
    def addRTPtoSession(self, session, rtp):
        l = threading.Lock()
        with l:
            self.watchList[session]['RTPqueue'].put(rtp)
    
    def getStreamName(self, session):
        l = threading.Lock()
        with l:
            return self.watchList[session]['name']

    def getRTPqueue(self, session):
        l = threading.Lock()
        with l:
            return self.watchList[session]['RTPqueue']

    def getReplyQueue(self, session):
        l = threading.Lock()
        with l:
            return self.watchList[session]['ReplyQueue']

    def isWatchingRightNow(self, name):
        l = threading.Lock()
        with l:
            for session, info in self.watchList.items():
                if info['name'] == name:
                    return True

            return False
    
    def addReplyToSession(self, session, reply):
        l = threading.Lock()
        with l:
            self.watchList[session]['ReplyQueue'].put(reply)
    

    def addRTP(self, name, rtp):
        l = threading.Lock()
        with l:

            for session, info in self.watchList.items():
                if info['name'] == name:
                    info['RTPqueue'].put(rtp)

class NodeListener:
    def __init__(self, localIP, serverIP, node):
        self.localIP = localIP
        self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.socket.bind((localIP, NODE_UDP_PORT))
        self.serverIP = serverIP
        self.node = node

    def start(self):
        print('[NODE LISTENER] Listening for UDP packets at ' + self.localIP + ':' + str(3001))

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            while True:
                data, addr = self.socket.recvfrom(21000)
                #print('[NODE LISTENER] Received data: ' + str(ONodePacketFactory.deserialize(data))+'from: '+ str(addr))
                executor.submit(NodeWorker(self.node, self.localIP, self.serverIP).processUDP(addr, data))

class NodeWorker:
    BUFFER_SIZE = 1024

    PAUSE = 'PAUSE'
    PLAY = 'PLAY'
    TEARDOWN = 'TEARDOWN'

    OK_200 = 0
    FILE_NOT_FOUND_404 = 1
       
    def __init__(self, node, nodeIP, serverIP):
        self.node = node
        self.nodeIP = nodeIP
        self.serverIP = serverIP

    def processUDP(self, addr, data):
        packet = ONodePacketFactory.deserialize(data)
        if packet.tipo == SIGNAL:
            self.processSignals(addr, packet)
        elif packet.tipo == FLOODING:
            self.processRouteFlooding(addr, packet)
        elif packet.tipo == RTSP_REQUEST:
            self.processRTSPpacket(addr, packet)
        elif packet.tipo == RTSP_REPLY:
            self.processRTSPreply(addr, packet)
        elif packet.tipo == RTP:
            self.processRTPpacket(addr, packet)
    
    def removeAlternativeRoutes(self, bestNeighbour):
        if bestNeighbour is not None and not self.node.routingTable.getAlternative(bestNeighbour):
            alternatives = self.node.routingTable.getAllAlternatives()
            alternatives = self.node.routingTable.removeAlternatives(alternatives)
            
            if alternatives != []:
                self.node.streamRequestTable.removeEntry(alternatives)
                    
                notificationPacket = ONodePacketFactory.create(DELETE_ROUTE, [alternatives, self.nodeIP])
                s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
                s.connect((self.serverIP, NODE_UDP_PORT))
                s.sendall(notificationPacket.serialize())
                
                print('[Node Worker] Sent request to server to remove alternative routes: ' + str(alternatives))
    
    def switchToNewNeighbour(self, addr, packet):
        bestNeighbour = self.node.routingTable.getBestPathToServer()
        #print('[NODE] Melhor vizinho ' + str(bestNeighbour) + ' First flooding: ' + str(self.node.firstFlooding))
        deadNeighbours = self.node.routingTable.getDeadNeighbours()
        
        if bestNeighbour is None and self.node.getFirstFlooding() and deadNeighbours != []:
            #Envia todos os vizinhos q estão down ao servidor
            notificationPacket = ONodePacketFactory.create(CORRECTION_REQUEST, [deadNeighbours, self.nodeIP])
            print('[NODE] Sending dead neighbour nodes to server')

            s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            s.connect((self.serverIP, NODE_UDP_PORT))
            s.sendall(notificationPacket.serialize())
        
        elif bestNeighbour is not None:
            # Remove alternative routes
            self.removeAlternativeRoutes(bestNeighbour)

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

    def processSignals(self, addr, packet):
        self.node.routingTable.updateSignals(packet.originIP)
        #print('[NODE] Processing signal from ' + packet.originIP)
        
    def sendSignals(self):
        s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        signalPacket = ONodePacketFactory.create(SIGNAL, [self.nodeIP])
        arr = signalPacket.serialize()

        while True:
            neighbours = self.node.routingTable.getNeighbours()
            for neighbour in neighbours:
                s.sendto(arr, (neighbour, NODE_UDP_PORT))
                #print('[NODE] signal sent to ' + neighbour)
            
            s.sendto(arr, (self.nodeIP, NODE_UDP_PORT))
        
            time.sleep(5)
    
    #Processa um pacote de flooding enviando de forma controlada para os vizinhos.
    #Envia um valor de numero de saltos igual ao vizinho com menor número de saltos adicionando uma unidade.
    #Tambem so envia para os vizinhos que tiverem um peso maior que o peso que vem no pacote ou para aqueles que ainda tem o valor do peso = -1
    def processRouteFlooding(self, addr, packet):
        self.node.routingTable.updateFlooding(packet.originIP, packet.weight)
        neighbours = self.node.routingTable.getNeighbours()
        
        s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
         
        for neighbour in neighbours:
            if neighbour != packet.originIP and (self.node.routingTable.getpathweight(neighbour) >= packet.weight or self.node.routingTable.getpathweight(neighbour) < 0):
                print('[NODE] Sending route flooding packet to ' + str(neighbour) + '. Path: ' + ' Weight: ' + str(packet.weight + 1))
                newPacket = ONodePacketFactory.create(FLOODING, [self.nodeIP, self.node.routingTable.getLowestWeight() + 1])
                s.sendto(newPacket.serialize(), (neighbour, NODE_UDP_PORT))
                
        self.node.firstFlooding = True
        self.switchToNewNeighbour(packet.originIP, packet)

    def processRTPpacket(self, addr, packet):
        bestNeighbour = self.node.routingTable.getBestPathToServer()
        actualNeighbour = self.node.streamRequestTable.getOrigin(packet.stream)
        
        # Remove alternative routes
        self.removeAlternativeRoutes(bestNeighbour)
        deadNeighbours = self.node.routingTable.getDeadNeighbours()
        
        # Recebeu um pacote do novo melhor nodo
        if actualNeighbour != bestNeighbour and packet.originIP == bestNeighbour and (self.node.routingTable.getpathweight(bestNeighbour) < self.node.routingTable.getpathweight(actualNeighbour) or actualNeighbour in deadNeighbours):
            request = 'TEARDOWN ' + packet.stream + ' RTSP/1.0\n'  
            request += 'CSeq: -1'  + '\n'
            request += 'Session: -1'
            self.sendRtspRequest(actualNeighbour, packet.stream, request)
            self.node.streamRequestTable.updateOrigin(packet.stream, bestNeighbour)
   
        # envia teardown caso nng esteja a ver, ou tenha recebido um rtp de um nodo q não é o melhor
        if (packet.originIP != self.node.streamRequestTable.getOrigin(packet.stream) or 
            (self.node.streamRequestTable.getStreamRequesters(packet.stream) == [] and 
             not self.node.isWatchingRightNow(packet.stream)) or
              packet.originIP not in self.node.routingTable.getNeighbours()
            ):
            request = 'TEARDOWN ' + packet.stream + ' RTSP/1.0\n'  
            request += 'CSeq: -1'  + '\n'
            request += 'Session: -1'
            self.sendRtspRequest(packet.originIP, packet.stream, request)

        else:
            if self.node.isWatchingRightNow(packet.stream): 
                self.node.addRTP(packet.stream, packet.rtp)

            self.relayRTPpacket(packet)
        
    #Retransmite o pacote RTP para os vizinhos que lhe pedem a stream 
    def relayRTPpacket(self, packet):
        s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

        relayPacket = ONodePacketFactory.create(RTP, [packet.stream, packet.rtp, self.nodeIP]) 

        for neighbour in self.node.streamRequestTable.getStreamRequesters(packet.stream):
            print('[NODE WORKER] RTP packet sent to ' + neighbour)
            s.sendto(relayPacket.serialize(), (neighbour, NODE_UDP_PORT))

    #Recebe uma resposta RTSP
    def processRTSPreply(self, addr, packet):
        reply = packet.rtsp.split('\n')
        line1 = reply[0].split(' ')
        replyType = int(line1[1])
        filename = packet.stream
        seq = int(reply[1].split(' ')[1])
        session = int(reply[2].split(' ')[1]) 

        #Se estiver a realizar uma stream coloca na estrutura dos pacotes RTSP
        #Para que o worker do cliente possa processá-los
        #Caso contrário processa ao nivel do worker do nodo
        if (self.node.isWatchingRightNow(filename)) or self.node.streamRequestTable.getStreamRequesters(filename) != []:
            bestNeighbour = self.node.routingTable.getBestPathToServer()
            actualNeighbour = self.node.streamRequestTable.getOrigin(filename)

            if replyType == 200 and self.node.streamRequestTable.getRouteState(filename) == StreamRequestTable.STANDBY:
                self.node.streamRequestTable.setRouteState(filename, StreamRequestTable.ACTIVATED)
                self.relayReplyToNeighbours(packet, replyType, filename)

            elif replyType == 404:
                self.relayReplyToNeighbours(packet, replyType, filename)

            if bestNeighbour != actualNeighbour and packet.originIP == bestNeighbour and replyType == 200 and self.node.routingTable.getpathweight(bestNeighbour) < self.node.routingTable.getpathweight(actualNeighbour):

                print('\n[NODE WORKER] SENDING TEARDOWN TO ' + str(actualNeighbour) + ' BECAUSE THE BEST NEIGHBOUR: ' + str(bestNeighbour) + ' IS AVAILABLE.\n')

                self.node.streamRequestTable.updateOrigin(packet.stream, bestNeighbour)
                request = 'TEARDOWN ' + packet.stream + ' RTSP/1.0\n'  
                request += 'CSeq: -1'  + '\n'
                request += 'Session: -1'
                self.sendRtspRequest(actualNeighbour, packet.stream, request)

            if self.node.isWatchingRightNow(filename) and seq >= 0 and session >= 1:
                print('\n[NODE WORKER] REPLY ' + filename + ' WAS ADDED TO THE SESSION: ' + str(session) + '\n')
                self.node.addReplyToSession(session, packet.rtsp)
            
    def relayReplyToNeighbours(self, packet, replyType, filename):
        s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        
        neighbours = self.node.streamRequestTable.getStreamRequesters(filename)
        print('\n[NODE WORKER] SENDING REPLY ' + str(replyType) + ' TO REQUESTERS: ' + str(neighbours)+'\n')

        for neighbour in neighbours:            
            if replyType == 404:     
                self.node.streamRequestTable.deactivateRoute(filename, neighbour, self.node.isWatchingRightNow(filename))

            relayPacket = ONodePacketFactory.create(RTSP_REPLY, [packet.stream, packet.rtsp, self.nodeIP]) 
            s.sendto(relayPacket.serialize(), (neighbour, NODE_UDP_PORT))

    #Processar receção de pacotes RTSP request
    def processRTSPpacket(self, addr, packet):
        data = packet.rtsp
        newRequest = ''
        request = data.split('\n')
        line1 = request[0].split(' ')
        requestType = line1[0]

        # Get the media file name
        filename = line1[1]
        
        # Get the RTSP sequence number 
        seq = request[1].split(' ')[1]

        session = int(request[2].split(' ')[1])
        print('\n[NODE WORKER] GOT REQUEST ' + str(requestType) + ' FROM ' + packet.originIP + ' WITH SEQ NUM: ' + str(seq) + ' AND SESSION: ' + str(session) + '\n') 

        # Process SETUP request
        if requestType == self.PLAY:
            #Se já existir uma entrada para esta stream na streamRequestTable e a rota estiver ativa
            #envia de imediato uma resposta para quem lhe pediu a stream
            if filename in self.node.streamRequestTable.getStreams() and self.node.streamRequestTable.getRouteState(filename) == self.node.streamRequestTable.ACTIVATED:
                print('\n[NODE WORKER] O FLUXO DE STREAM ' + filename + ' ESTÁ ATIVADO NESTE NODO ATRAVES DE: ' + str(self.node.streamRequestTable.getOrigin(filename)) + "\n")
                self.node.streamRequestTable.activateRoute(filename, packet.originIP)
                self.replyRtsp(packet.originIP, filename, self.OK_200, seq, session)

            #Caso a rota esteja em standby nao envia uma resposta de imediato
            elif filename in self.node.streamRequestTable.getStreams() and self.node.streamRequestTable.getRouteState(filename) == self.node.streamRequestTable.STANDBY:
                print('\n[NODE WORKER] O FLUXO DESTA STREAM ' + filename + ' ESTA EM STAND BY.')
                self.node.streamRequestTable.activateRoute(filename, packet.originIP)

            #Caso não haja uma entrada para esta stream cria-a em standby e envia um pedido de stream ao melhor vizinho
            else:
                bestNeighbour = self.node.routingTable.getBestPathToServer()
            
                if bestNeighbour != None:
                    print('\n[NODE WORKER] FLUXO DA STREAM ' + filename + ' NUNCA FOI PEDIDO. A PEDIR A: ' + str(bestNeighbour) + '\n')
                    self.node.streamRequestTable.activateRoute(filename, packet.originIP)
                    self.node.streamRequestTable.updateOrigin(filename, bestNeighbour) 
                    self.sendRtspRequest(bestNeighbour, filename, data)
                else:
                    print('\n[NODE WORKER] FLUXO DA STREAM  ' + filename + ' NUNCA FOI PEDIDO. DE MOMENTO NAO HA NENHUM MELHOR VIZINHO. \n')
                 
        #Process TEARDOWN request
        elif requestType == self.TEARDOWN:
            origin = self.node.streamRequestTable.getOrigin(filename)
            self.node.streamRequestTable.deactivateRoute(filename, packet.originIP, self.node.isWatchingRightNow(filename))
             
            #Se não houver mais espectadores desta stream
            if filename not in self.node.streamRequestTable.getStreams(): 
                print('\n[NODE WORKER] SENDING TEARDOWN REQUEST TO ' + str(origin) + ' BECAUSE THERE IS NO ONE WATCHING AND I AM NOT A CLIENT OF THIS STREAM\n')
                self.sendRtspRequest(origin, filename, data)
                     
           # self.replyRtsp(packet.originIP, filename, self.OK_200, seq, session)

    #Envia o pedido rtsp pelo socket
    def sendRtspRequest(self, bestNeighbour, filename, request):
        packet = ONodePacketFactory.create(RTSP_REQUEST, [request, self.nodeIP])
        s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        s.sendto(packet.serialize(),(bestNeighbour, NODE_UDP_PORT))

    #Envia uma resposta a um pedido RTSP que pode ser OK_200 ou 404_FILE_NOT_FOUND
    def replyRtsp(self, neighbour, filename, code, seq, session):
        s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        reply = ''

        if code == self.OK_200:
            reply = 'RTSP/1.0 200 OK\nCSeq: ' + str(seq) + '\nSession: ' + str(session)

        elif code == self.FILE_NOT_FOUND_404:
            reply = 'RTSP/1.0 404 FILE_NOT_FOUND\nCSeq: ' + str(seq) + '\nSession: ' + str(session)

        replyPacket = ONodePacketFactory.create(RTSP_REPLY, [filename, reply, self.nodeIP]) 
        s.sendto(replyPacket.serialize(), (neighbour, NODE_UDP_PORT))
    
def authenticate(node, serverIP, nodeIP):
    serverPort = SERVER_UDP_PORT

    print('[NODE] Requesting neighbours to server ' + serverIP + ':' + str(serverPort))

    authenticationPacket = ONodePacketFactory.create(AUTH, [nodeIP])

    s = socket.socket(family=socket.AF_INET,  type=socket.SOCK_DGRAM)
    s.connect((serverIP, serverPort))
    s.sendall(authenticationPacket.serialize())

    print('[NODE] Request sent and waiting for response')

    data = s.recvfrom(1024)    
    responsePacket = ONodePacketFactory.deserialize(data[0])
    
    neighbours = responsePacket.neighbours

    print('[NODE] received the following neighbours: ' + str(neighbours))

    for neighbour in neighbours:
        node.routingTable.addNewNeighbour(neighbour, [], 0, False, False)
        
    s.close()

class StreamApp:
    def __init__(self, master, node, localIP):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.node = node
        self.localIP = localIP
        self.master.title('STREAMING SERVICE')
        self.master.geometry('400x200')
        self.streamName = Label(master, text='Enter stream name', padx=10,pady=10)
        self.streamName.pack()
        self.inputName = Entry(master)
        self.inputName.pack()
        self.button = Button(master,text="Start Watching", command=self.openNewStream) 
        self.button.pack()
 
    def openNewStream(self):
        name = self.inputName.get()
        app = ClientWorker(self.master, self.node, name, self.localIP)


    def handler(self):
        """Handler on explicitly closing the GUI window."""
        count = 0
        for window in self.master.winfo_children():
            if isinstance(window, Toplevel) and window.winfo_exists():
                count += 1 
        if count > 0:
            msgbox.showwarning(title="WARNING", message="Close streams before main window")
        else:
            self.master.destroy()

def startStreaming(nodeSystem, localIP):
    root = Tk() 
    app = StreamApp(root, nodeSystem, localIP)
    root.mainloop()  

def processInput(user_input, nodeSystem, localIP):
    args = user_input.split()
    if len(args) == 1 and args[0] == 'stream':
        startStreaming(nodeSystem, localIP)

def main():
    args = sys.argv[1:]
    node = Node() 

    authenticate(node, args[1], args[0])
    
    listener = NodeListener(args[0], args[1],node)
    threading.Thread(target=listener.start).start()

    nw = NodeWorker(node, args[0], args[1])
    threading.Thread(target=nw.sendSignals).start()

    user_input = ""
    while(user_input != "exit"):
        user_input = input('Command: ') 
        processInput(user_input, node, args[0])

if __name__ == '__main__':
    main()