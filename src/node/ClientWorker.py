import tkinter.messagebox as tkMessageBox
import socket, threading, sys, traceback, os, queue

from tkinter import *
from PIL import Image, ImageTk
from socket import timeout

sys.path.append('../')
from shared.RtpPacket import RtpPacket
from shared.ONodePacket import * 

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

SERVER_UDP_PORT = 8017
NODE_UDP_PORT = 8017

class ClientWorker:
    
    PLAY = 'PLAY'
    TEARDOWN = 'TEARDOWN'
    PAUSE = 'PAUSE'
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT
    sessionId = 1
    OK_200 = 0
    FILE_NOT_FOUND_404 = 1
    CON_ERR_500 = 2
        
    # Initiation..
    def __init__(self,root,  node, filename, localIP):
        self.master = Toplevel(root)
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.node = node
        self.teardownAcked = 0
        self.frameNbr = 0

        self.requestSent = None 
        self.seq = 0        
        self.session = self.node.addToWatchList(filename)
        self.ReplyQueue = self.node.getReplyQueue(self.session)
        self.RtpQueue = self.node.getRTPqueue(self.session)
        self.node.startWatching(self.session)
        self.node.streamRequestTable.addStream(filename)
        self.localIP = localIP

    def createWidgets(self):
        """Build GUI."""
        # Create Setup button
        self.setup = Button(self.master, width=20, padx=3, pady=3)
        self.setup["text"] = "Setup"
        self.setup["command"] = self.setupMovie
        self.setup.grid(row=1, column=0, padx=2, pady=2)
        
        # Create Play button 
        self.start = Button(self.master, width=20, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=1, column=1, padx=2, pady=2)
        
        # Create Pause button 
        self.pause = Button(self.master, width=20, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=1, column=2, padx=2, pady=2)
        
        # Create Teardown button
        self.teardown = Button(self.master, width=20, padx=3, pady=3)
        self.teardown["text"] = "Teardown"
        self.teardown["command"] =  self.exitClient
        self.teardown.grid(row=1, column=3, padx=2, pady=2)
        
        # Create a label to display the movie
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 
    
    def setupMovie(self):
        """Setup button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.PLAY)
            self.playEvent = threading.Event()
            self.playEvent.clear()
    
    def exitClient(self):
        """Teardown button handler."""
        if self.state != self.INIT:

            if self.state == self.PLAYING:
                self.sendRtspRequest(self.TEARDOWN) 
                self.playEvent.set()
                self.rtp_thread.join()
            elif self.state == self.READY:
                self.RtpQueue.put('TEARDOWN')
                self.rtp_thread.join()

            os.remove(CACHE_FILE_NAME + self.localIP + str(self.session) + CACHE_FILE_EXT) # Delete the cache image from video

        self.master.destroy() # Close the gui window

    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.TEARDOWN)
            self.playEvent.set()
            self.state = self.READY
    
    def playMovie(self):
        """Play button handler."""
        if self.state == self.READY:
            # Create a new thread to listen for RTP packets
            self.playEvent = threading.Event()
            self.playEvent.clear()

            self.node.startWatching(self.session)

            self.sendRtspRequest(self.PLAY)
            self.state = self.PLAYING
    
    def listenRtp(self): 
        print("""Listen for RTP packets.""")
        while True:
            try:
                data = self.RtpQueue.get(block=True, timeout=10)
                self.RtpQueue.task_done()
                
                if data == 'TEARDOWN':
                    self.teardownAcked = 1
                    break
                elif data:
                    currFrameNbr = data.seqNum()
 
                    if currFrameNbr > self.frameNbr: 
                        self.frameNbr = currFrameNbr
                        self.updateMovie(self.writeFrame(data.getPayload()))

            except queue.Empty:
                print("STOPPED RECEIVING RTP PACKET: TIMED OUT\n")
                self.sendPlayWithoutTimeout(self.node.getStreamName(self.session), self.PLAY)
                
            except Exception as e: 
                if self.playEvent.isSet():
                    print("IS SET")
                    break
                
                if self.teardownAcked == 1:
                    break
                                 
    def writeFrame(self, data):                 
        """Write the received frame to a temp image file. Return the image file."""
        cachename = CACHE_FILE_NAME + self.localIP  + str(self.session) + CACHE_FILE_EXT
        file = open(cachename, "wb")
        file.write(data)
        file.close()
        
        return cachename
    
    def updateMovie(self, imageFile):
        """Update the image file as video frame in the GUI."""
        photo = ImageTk.PhotoImage(Image.open(imageFile))
        self.label.configure(image = photo, height=288)
        self.label.image = photo
        
    def sendRtspRequest(self, requestCode):
        """Send RTSP request to the server."""  
        neighbour = ""
        # Play request
        filename = self.node.getStreamName(self.session)

        if requestCode == self.PLAY and (self.state == self.INIT or self.state == self.READY):
            #print(self.node.streamRequestTable.getStreamRequesters(filename))
            if self.node.streamRequestTable.getStreamRequesters(filename) == []:
                self.sendPlay(filename, requestCode)
            else:
                self.rtp_thread = threading.Thread(target = self.listenRtp)
                self.rtp_thread.start()
                self.state = self.PLAYING
            
        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            
            self.node.stopWatching(self.session) 
            print('[CLIENT] STOPPED WATCHING THE STREAM') 
            if self.node.streamRequestTable.getStreamRequesters(filename) == []:
                self.sendTeardown(filename, requestCode)
               
            else:
                self.state = self.READY
                self.playEvent.set()                    

        elif requestCode == self.TEARDOWN and not self.state == self.INIT:
            
            self.node.stopWatching(self.session) 
            print('[CLIENT] STOPPED WATCHING THE STREAM') 
            
            if self.node.streamRequestTable.getStreamRequesters(filename) == []:
                self.sendTeardown(filename, requestCode)                        

            else:
                self.state = self.INIT
                self.playEvent.set()
                self.RtpQueue.put('TEARDOWN')
                self.rtp_thread.join()
                # Flag the teardownAcked to close the socket.
                self.teardownAcked = 1 
        else:
            return

    def sendPlay(self, filename, requestCode):
        self.seq += 1

        # Write the RTSP request to be sent.
        request = 'PLAY ' + filename + ' RTSP/1.0\n'  
        request += 'CSeq: ' + str(self.seq) + '\n'
        request += 'Session: ' + str(self.session)

        if filename not in self.node.streamRequestTable.getStreams():
            self.node.streamRequestTable.addStream(filename)

        # Keep track of the sent request.
        neighbour = self.node.routingTable.getBestPathToServer()
        self.node.streamRequestTable.updateOrigin(filename, neighbour)
                
        if neighbour == None:
            print('[CLIENT] FLOODING NOT YET DONE\n')
        else:
            while self.sendRtspWithTimeout(neighbour, request, requestCode):
                neighbour = self.node.routingTable.getBestPathToServer()
                self.node.streamRequestTable.updateOrigin(filename, neighbour)

    def sendPlayWithoutTimeout(self, filename, requestCode):
        # Write the RTSP request to be sent.
        request = 'PLAY ' + filename + ' RTSP/1.0\n'  
        request += 'CSeq: -1\n'
        request += 'Session: -1' 

        if filename not in self.node.streamRequestTable.getStreams():
            self.node.streamRequestTable.addStream(filename)

        neighbour = self.node.routingTable.getBestPathToServer()
        self.node.streamRequestTable.updateOrigin(filename, neighbour)
                
        if neighbour == None:
            print('[CLIENT] FLOODING NOT YET DONE\n')
        else:
            print('[CLIENT] Sending new play to ' + str(neighbour))
            self.sendRtsp(neighbour, request, requestCode)
            self.node.streamRequestTable.updateOrigin(filename, neighbour)

    def sendTeardown(self, filename, requestCode): 
        # Write the RTSP request to be sent.
        request = 'TEARDOWN ' + filename + ' RTSP/1.0\n'  
        request += 'CSeq: ' + str(self.seq) + '\n'
        request += 'Session: ' + str(self.session)
                
        # Keep track of the sent request.
        self.RtpQueue.put('TEARDOWN')
        neighbour = self.node.streamRequestTable.getOrigin(filename)
        self.sendRtsp(neighbour, request, requestCode)    
        self.node.streamRequestTable.removeSelf(filename, self.localIP)
           
    def sendRtspWithTimeout(self, neighbour, request, requestCode):
        packet = ONodePacketFactory.create(RTSP_REQUEST, [request, self.localIP])
        s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.requestSent = requestCode
        
        arr = packet.serialize()
        s.sendto(arr,(neighbour, NODE_UDP_PORT))
        print('\n[CLIENT] RTSP REQUEST ' + str(requestCode) + '  SENT TO ' + neighbour+'\n')
                
        try:
            packet = self.recvRtspReply(10)
            return False
        
        except queue.Empty: 
            print('[CLIENT] TIMEDOUT')
            return True
            
    def sendRtsp(self, neighbour, request, requestCode):
        packet = ONodePacketFactory.create(RTSP_REQUEST, [request, self.localIP])
        s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            
        self.requestSent = requestCode
        arr = packet.serialize()
        s.sendto(arr,(neighbour, NODE_UDP_PORT))
        
    def recvRtspReply(self, timeout):
        """Receive RTSP reply from the server."""
        reply = self.ReplyQueue.get(block=True,timeout=timeout)    
        self.ReplyQueue.task_done() 
        return self.parseRtspReply(reply) 

    def parseRtspReply(self, data):
        """Parse the RTSP reply from the server."""
        lines = data.split('\n')
        seqNum = int(lines[1].split(' ')[1])
        
        session = int(lines[2].split(' ')[1])
        replyType = int(lines[0].split(' ')[1]) 
        # Process only if the server reply's sequence number is the same as the request's

        if seqNum == self.seq and self.session == session and replyType == 200:
            if self.requestSent == self.PLAY:

                print('[CLIENT] GOT A PLAY REPLY 200 with seq: ' + str(seqNum) + ' and session ' + str(session))
                
                self.rtp_thread = threading.Thread(target = self.listenRtp)
                self.rtp_thread.start()
                self.state = self.PLAYING
                self.teardownAcked = 1 
        elif seqNum == self.seq and self.session == session and replyType == 404:
            print('[CLIENT] STREAM REQUESTED DOES NOT EXIST')
            self.master.destroy() # Close the gui window

        else:
            if seqNum != self.seq:
                print('[CLIENT] REPLY HAD A DIFFERENT SEQ: CLIENT SEQ -> ' + str(self.seq) + ' REPLY SEQ ' + str(seqNum))

            elif self.session != session:
                print('[CLIENT] REPLY HAD A DIFFERENT SESSION NUM: CLIENT SESSION NUM -> ' + str(self.session) + ' REPLY SESSION NUM ' + str(session))

    def handler(self):
        """Handler on explicitly closing the GUI window."""
        self.pauseMovie()
        if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else: 
            self.playMovie()
