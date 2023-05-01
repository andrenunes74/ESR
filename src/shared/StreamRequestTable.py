import threading

class StreamRequestTable:

    DEACTIVATED = 0
    STANDBY = 1
    ACTIVATED = 2

    def __init__(self):
        self.streams = dict()

    def activateRoute(self, stream, neighbourIP):
        l = threading.Lock()
        with l:
            if stream in self.streams.keys():
                if neighbourIP not in self.streams[stream]['requesters']:
                    self.streams[stream]['requesters'].append(neighbourIP)
                else:
                    pass
                    #print("Something went wrong " + neighbourIP + " " + self.streams[stream]['requesters'])
            else:
                self.streams[stream]= {'state':self.STANDBY, 'requesters':[neighbourIP], 'origin':""}

    def addStream(self, stream):
        l = threading.Lock()
        with l:
            if stream not in self.streams.keys():
                self.streams[stream]= {'state':self.STANDBY, 'requesters':[], 'origin':""}
    
    def setRouteState(self, stream, newState):    
        l = threading.Lock()
        with l:
            if stream in self.streams.keys():
                self.streams[stream]['state'] = newState

    def getRouteState(self, stream):
        res = self.DEACTIVATED
        l = threading.Lock()

        with l:
            if stream in self.streams.keys():
                res = self.streams[stream]['state']
            
            return res

    def deactivateRoute(self, stream, neighbourIP, isClient):
        l = threading.Lock()
        with l:
            if stream in self.streams and neighbourIP in self.streams[stream]['requesters']:
                self.streams[stream]['requesters'].remove(neighbourIP)

                if self.streams[stream]['requesters'] == [] and not isClient:
                    self.streams.pop(stream)
                    
    def removeSelf(self, stream, ip):
        l = threading.Lock()
        with l:
            if stream in self.streams and self.streams[stream]['requesters'] == []:
                self.streams.pop(stream)

    def removeEntry(self, alternatives):
        l = threading.Lock()
        with l:
            list = self.streams.copy()
            for stream, info in list.items():
                if info['origin'] in alternatives:
                    self.streams.pop(stream)

    def getStreamRequesters (self, stream):
       l = threading.Lock()
       with l:
            if stream in self.streams.keys():
                return self.streams[stream]['requesters']
            else:
                return []

    def getStreams(self):
       l = threading.Lock()
       with l:
            return self.streams.keys()
    
    def updateOrigin(self, stream, origin):
        l = threading.Lock()
        with l:
            self.streams[stream]['origin'] = origin

    def getOrigin(self, stream):
        l = threading.Lock()
        with l:
            if stream in self.streams:
                return self.streams[stream]['origin']
            else:
                return ""

    def getStreamsOrigins(self):
        res = []
        l = threading.Lock()
        with l:
            for stream, info in self.streams.items():
                if info['state'] == self.ACTIVATED:
                    res.append((stream, info['origin']))

            return res

    def getAllRequesters(self):
        res = []
        l = threading.Lock()
        with l:
            for stream, info in self.streams.items():
                for requester in info['requesters']:
                    if requester not in res:
                        res.append((stream, requester))

            return res

