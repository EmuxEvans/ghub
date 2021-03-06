#!/usr/bin/python
# -*- coding: utf-8 -*-
from concurrent import futures
import grpc
import ghub_pb2
import time
import logging
from docopt import docopt

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class Channel(object):
    def __init__(self, stub, timestamp):
        self.stub = stub
        self.timestamp = timestamp


class GHubServer(ghub_pb2.GHubServerServicer):
    def __init__(self):
        self.clients = {}

    def Register(self, request, context):
        now = time.time()
        if request.name not in self.clients:
            addr = '{}:{}'.format(request.ip, request.port)
            channel = grpc.insecure_channel(addr)
            stub = ghub_pb2.GHubClientStub(channel)
            self.clients[request.name] = Channel(stub, now)
            logger.info('client {} from {} registered.'.format(
                request.name, addr))
        else:
            self.clients[request.name].timestamp = now
        return ghub_pb2.ReturnState(ret=0)

    def RemoteCall(self, request, context):
        dst_name = request.dst
        if dst_name not in self.clients:
            return ghub_pb2.ReturnState(ret=-1)
        channel = self.clients[dst_name]
        stub = channel.stub
        ret = stub.ForwardCall.future(request)
        ret.result()
        return ghub_pb2.ReturnState(ret=0)

    def CheckChannels(self):
        now = time.time()
        rm_channels = []
        for name, channel in self.clients.iteritems():
            if now - channel.timestamp >= 60:
                rm_channels.append(name)

        for name in rm_channels:
            self.clients.pop(name, None)
            logger.info('client {} disconnected.'.format(name))


def serve():
    doc = """Usage:
        ghub.py -p <port>
        ghub.py (-h | --help)

    Options:
        -h --help       Show this screen
        -p              Specify the listening port
    """
    args = docopt(doc, version="ghub ver1.0")
    hub_port = int(args['<port>'])
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    ghub_server = GHubServer()
    ghub_pb2.add_GHubServerServicer_to_server(ghub_server, server)
    server.add_insecure_port('[::]:{}'.format(hub_port))
    server.start()
    try:
        while True:
            time.sleep(10)
            ghub_server.CheckChannels()
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    serve()
