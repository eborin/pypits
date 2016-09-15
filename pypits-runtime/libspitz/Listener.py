#!/usr/bin/env python

# The MIT License (MIT)
#
# Copyright (c) 2015 Caian Benedicto <caian@ggaunicamp.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy 
# of this software and associated documentation files (the "Software"), to 
# deal in the Software without restriction, including without limitation the 
# rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL 
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS 
# IN THE SOFTWARE.

from libspitz import ClientEndpoint
from libspitz import config

import socket, threading, time, logging, os, traceback, sys

class Listener(object):
    """Threaded TCP/UDS listener with callback"""

    def __init__(self, mode, address, port, callback, user_args):
        self.mode = mode
        self.addr = address
        self.port = port
        self.callback = callback
        self.user_args = user_args
        self.thread = None
        self.socket = None
        
    def GetConnectableAddr(self):
        addr = '' #self.mode
        if self.mode == config.mode_tcp:
            addr += socket.gethostname() + ':' + str(self.port)
        elif self.mode == config.mode_uds:
            addr += socket.gethostname() + ':' + str(self.addr)
        else:
            logging.error('Invalid listener mode %s provided!' % (self.mode))
            raise Exception()
        return addr

    def listener(self):
        if self.mode == config.mode_tcp:
            logging.info('Listening to network at %s:%d...',
                self.addr, self.port)
        elif self.mode == config.mode_uds:
            logging.info('Listening to file at %s...',
                self.addr)
        while True:
            try:
                conn, addr = self.socket.accept()

                # Assign the address from the connection
                if self.mode == config.mode_tcp:
                    # TCP
                    addr, port = addr
                elif self.mode == config.mode_uds:
                    # UDS
                    addr = 'uds'
                    port = 0

                # Create the endpoint and send to a thread to
                # process the request
                endpoint = ClientEndpoint(addr, port, conn)
                threading.Thread(target = self.callback,
                    args=((endpoint, addr, port) + self.user_args)).start()
            except:
                print(sys.exc_info())
                traceback.print_exc()
                logging.debug('O oh!')
                time.sleep(10)

    def Start(self):
        if self.socket:
            return
        
        if self.mode == config.mode_tcp:
            # Create a TCP socket
            socktype = socket.AF_INET
            sockaddr = (self.addr, self.port)
        elif self.mode == config.mode_uds:
            # Remove an old socket
            try:
                os.unlink(self.addr)
            except:
                pass
            
            # Create an Unix Data Socket instead of a
            # normal TCP socket
            try:
                socktype = socket.AF_UNIX
            except AttributeError:
                logging.error('The system does not support ' +
                    'Unix Domain Sockets!')
                raise
            sockaddr = self.addr
        else:
            logging.error('Invalid listener mode %s provided!' % (self.mode))
            raise Exception()
        
        try:
            self.socket = socket.socket(socktype, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except socket.error:
            logging.error('Failed to create listener socket!')
            
        try:    
            self.socket.bind(sockaddr)
            self.socket.listen(1)
        except socket.error:
            logging.error('Failed to bind listener socket!')
            
        # If any port is selected, get the 
        # actual port assigned by the system
        if self.mode == config.mode_tcp and self.port == 0:
            addr, port = self.socket.getsockname()
            self.port = port
            
        self.thread = threading.Thread(target=self.listener)
        self.thread.start()

    def Stop(self):
        if self.socket:
            self.socket.close()
            self.socket = None
            if self.mode == config.mode_uds:
                # Remove the socket file if it is an UDS
                try:
                    os.unlink(self.addr)
                except:
                    pass

    def Join(self):
        if self.thread:
            self.thread.join()
