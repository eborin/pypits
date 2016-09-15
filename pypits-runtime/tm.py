#!/usr/bin/env python

# The MIT License (MIT)
#
# Copyright (c) 2015 Caian Benedicto <caian@ggaunicamp.com>
# Copyright (c) 2016 Edson Borin <edson@ic.unicamp.br>
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

from libspitz import JobBinary, SimpleEndpoint
from libspitz import Listener, TaskPool
from libspitz import messaging, config

import Args
import sys, os, datetime, logging, multiprocessing, struct, time
import traceback

try:
    import Queue as queue # Python 2
except:
    import queue # Python 3

# Global configuration parameters
tm_mode = None # Addressing mode
tm_addr = None # Bind address
tm_port = None # Bind port
tm_nw = None # Maximum number of workers
tm_overfill = 0 # Extra space in the task queue 
tm_announce = None # Mechanism used to broadcast TM address
tm_log_file = None # Output file for logging
tm_conn_timeout = None # Socket connect timeout
tm_recv_timeout = None # Socket receive timeout
tm_send_timeout = None # Socket send timeout

###############################################################################
# Parse global configuration
###############################################################################
def parse_global_config(argdict):
    global tm_mode, tm_addr, tm_port, tm_nw, tm_log_file, tm_overfill, \
        tm_announce, tm_conn_timeout, tm_recv_timeout, tm_send_timeout

    def as_int(v):
        if v == None:
            return None
        return int(v)

    def as_float(v):
        if v == None:
            return None
        return int(v)

    tm_mode = argdict.get('tmmode', config.mode_tcp)
    tm_addr = argdict.get('tmaddr', '0.0.0.0')
    tm_port = int(argdict.get('tmport', config.spitz_tm_port))
    tm_nw = int(argdict.get('nw', multiprocessing.cpu_count()))
    if tm_nw <= 0:
        tm_nw = multiprocessing.cpu_count()
    tm_overfill = max(int(argdict.get('overfill', 0)), 0)
    tm_announce = argdict.get('announce', 'none')
    tm_log_file = argdict.get('log', None)
    tm_conn_timeout = as_float(argdict.get('ctimeout', config.conn_timeout))
    tm_recv_timeout = as_float(argdict.get('rtimeout', config.recv_timeout))
    tm_send_timeout = as_float(argdict.get('stimeout', config.send_timeout))

###############################################################################
# Configure the log output format
###############################################################################
def setup_log():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers = []
    if tm_log_file == None:
        ch = logging.StreamHandler(sys.stderr)
    else:
        ch = logging.StreamHandler(open(tm_log_file, 'wt'))
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(threadName)s - '+
        '%(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)

###############################################################################
# Abort the aplication with message
###############################################################################
def abort(error):
    logging.critical(error)
    exit(1)
    
###############################################################################
# Append the node address to the nodes list
###############################################################################
def announce_cat(addr, filename = None):
    # Override the filename if it is empty
    if filename == None:
        nodefile = 'nodes.txt'
        filename = os.path.join('.', nodefile)

    logging.debug('Appending node %s to file %s...' % (addr, nodefile))
    
    try:
        f = open(filename, "a")
        f.write("node %s\n" % addr)
        f.close()
    except:
        logging.warning('Failed to write to %s!' % (nodefile,))

###############################################################################
# Server callback
###############################################################################
def server_callback(conn, addr, port, job, tpool, cqueue):
    logging.info('Connected to %s:%d.', addr, port)

    try:
        # Read the type of message
        mtype = conn.ReadInt64(tm_recv_timeout)

        # Termination signal
        if mtype == messaging.msg_terminate:
            logging.info('Received a kill signal from %s:%d.',
                addr, port)
            os._exit(0)

        # Job manager is trying to send tasks to the task manager
        if mtype == messaging.msg_send_task:
            torecv = tpool.Free()
            logging.info('Capable of receiving %d tasks...', torecv)
            conn.WriteInt64(torecv)
            for i in range(torecv):
                taskid = conn.ReadInt64(tm_recv_timeout)
                tasksz = conn.ReadInt64(tm_recv_timeout)
                task = conn.Read(tasksz, tm_recv_timeout)
                logging.info('Received task %d from %s:%d.',
                    taskid, addr, port)

                # Try enqueue the received task
                if not tpool.Put(taskid, task):
                    # For some reason the pool got full in between
                    logging.warning('Ignoring just received task %d because ' +
                        'the pool is full! (Should not happen)', taskid)

        # Job manager is querying the results of the completed tasks
        elif mtype == messaging.msg_read_result:
            tosend = cqueue.qsize()
            conn.WriteInt64(tosend)
            taskid = None
            try:
                # Dequeue completed tasks until cqueue fires
                # an Empty exception
                for i in range(tosend):
                    # Pop the task
                    taskid, r, res = cqueue.get_nowait()

                    logging.info('Sending task %d to committer %s:%d...',
                        taskid, addr, port)

                    # Send the task
                    conn.WriteInt64(taskid)
                    conn.WriteInt64(r)
                    if res == None:
                        conn.WriteInt64(0)
                    else:
                        conn.WriteInt64(len(res))
                        conn.Write(res)

                    taskid = None

            except queue.Empty:
                logging.error('Reading beyond end of queue! (Should not happen)', taskid)

            except:
                # Something went wrong while sending, put
                # the last task back in the queue
                if taskid != None:
                    cqueue.put((taskid, r, res))
                    logging.info('Task %d put back in the queue.', taskid)
                pass

        # Unknow message received or a wrong sized packet could be trashing
        # the buffer, don't do anything
        else:
            logging.warning('Unknown message received \'%d\'!', mtype)

    except messaging.SocketClosed:
        logging.info('Connection to %s:%d closed from the other side.',
            addr, port)

    except messaging.TimeoutError:
        logging.warning('Connection to %s:%d timed out!', addr, port)

    except:
        logging.warning('Error occurred while reading request from %s:%d!',
            addr, port)
        traceback.print_exc()

    conn.Close()
    logging.info('Connection to %s:%d closed.', addr, port)

###############################################################################
# Initializer routine for the worker
###############################################################################
def initializer(cqueue, job, argv):
    logging.info('Initializing worker...')
    return job.spits_worker_new(argv)

###############################################################################
# Worker routine
###############################################################################
def worker(state, taskid, task, cqueue, job, argv):
    logging.info('Processing task %d...', taskid)

    # Execute the task using the job module
    r, res, ctx = job.spits_worker_run(state, task, taskid)

    logging.info('Task %d processed.', taskid)

    if res == None:
        logging.error('Task %d did not push any result!', taskid)
        return

    if ctx != taskid:
        logging.error('Context verification failed for task %d!', taskid)
        return

    # Enqueue the result
    cqueue.put((taskid, r, res[0]))

###############################################################################
# Run routine
###############################################################################
def run(argv, job):
    # Create a work pool and a commit queue
    cqueue = queue.Queue()
    tpool = TaskPool(tm_nw, tm_overfill, initializer, 
        worker, (cqueue, job, argv))

    # Create the server
    logging.info('Starting network listener...')
    l = Listener(tm_mode, tm_addr, tm_port, 
        server_callback, (job, tpool, cqueue))
        
        
    # Start the server^M
    l.Start()
    
    # Announce the worker
    logging.info('ANNOUNCE %s' % l.GetConnectableAddr())
    
    if tm_announce == config.announce_cat_nodes:
        announce_cat(l.GetConnectableAddr())

    # Wait for work^M
    logging.info('Waiting for work...')
    l.Join()

###############################################################################
# Main routine
###############################################################################
def main(argv):
    # Print usage
    if len(argv) <= 1:
        abort('USAGE: tm [args] module [module args]')

    # Parse the arguments
    args = Args.Args(argv)
    parse_global_config(args.args)
    
    # Setup logging
    setup_log()
    logging.debug('Hello!')

    # Load the module
    module = args.margs[0]
    job = JobBinary(module)

    # Remove JM arguments when passing to the module
    margv = args.margs

    # Start the tm
    run(margv, job)

    # Finalize
    logging.debug('Bye!')
    #exit(r)

###############################################################################
# Entry point
###############################################################################
if __name__ == '__main__':
    main(sys.argv)
