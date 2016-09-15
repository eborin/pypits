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
from libspitz import messaging, config
import traceback
import Args
import sys, threading, os, time, ctypes, logging, struct, threading, traceback

# Global configuration parameters
jm_killtms = None # Kill task managers after execution
jm_log_file = None # Output file for logging
jm_conn_timeout = None # Socket connect timeout
jm_recv_timeout = None # Socket receive timeout
jm_send_timeout = None # Socket send timeout
jm_send_backoff = None # Job Manager delay between sending tasks
jm_recv_backoff = None # Job Manager delay between sending tasks

###############################################################################
# Parse global configuration
###############################################################################
def parse_global_config(argdict):
    global jm_killtms, jm_log_file, jm_conn_timeout, jm_recv_timeout, \
        jm_send_timeout, jm_send_backoff, jm_recv_backoff

    def as_int(v):
        if v == None:
            return None
        return int(v)

    def as_float(v):
        if v == None:
            return None
        return int(v)

    def as_bool(v):
        if v == None:
            return None
        return bool(v)

    jm_killtms = as_bool(argdict.get('killtms', True))
    jm_log_file = argdict.get('log', None)
    jm_conn_timeout = as_float(argdict.get('ctimeout', config.conn_timeout))
    jm_recv_timeout = as_float(argdict.get('rtimeout', config.recv_timeout))
    jm_send_timeout = as_float(argdict.get('stimeout', config.send_timeout))
    jm_recv_backoff = as_float(argdict.get('rbackoff', config.recv_backoff))
    jm_send_backoff = as_float(argdict.get('sbackoff', config.send_backoff))

###############################################################################
# Configure the log output format
###############################################################################
def setup_log():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers = []
    if jm_log_file == None:
        ch = logging.StreamHandler(sys.stderr)
    else:
        ch = logging.StreamHandler(open(jm_log_file, 'wt'))
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
# Parse the definition of a proxy
###############################################################################
def parse_proxy(cmd):
    cmd = cmd.split()

    if len(cmd) != 3:
        raise Exception()

    logging.debug('Proxy %s.' % (cmd[1]))

    name = cmd[1]
    gate = cmd[2].split(':')
    prot = gate[0]
    addr = gate[1]
    port = int(gate[2])

    return (name, { 'protocol' : prot, 'address' : addr, 'port' : port })

###############################################################################
# Parse the definition of a compute node
###############################################################################
def parse_node(cmd, proxies):
    cmd = cmd.split()

    if len(cmd) < 2:
        raise Exception()

    logging.debug('Node %s.' % (cmd[1]))

    name = cmd[1]
    host = name.split(':')
    addr = host[0]
    port = int(host[1])

    # Simple endpoint
    if len(cmd) == 2:
        return (name, SimpleEndpoint(addr, port))

    # Endpoint behind a proxy
    elif len(cmd) == 4:
        if cmd[2] != 'through':
            raise Exception()

        proxy = proxies.get(cmd[3], None)
        if proxy == None:
            raise Exception()

        # Proxies are not supported yet...
        logging.info('Node %s is behind a proxy and will be ignored.' %
            (cmd[1]))
        return None

    # Unknow command format
    raise Exception()

###############################################################################
# Load the list of task managers from a file
###############################################################################
def load_tm_list(filename = None):
    # Override the filename if it is empty
    if filename == None:
        nodefile = 'nodes.txt'
        filename = os.path.join('.', nodefile)

    logging.debug('Loading task manager list from %s...' % (nodefile,))

    # Read all lines
    try:
        with open(filename, 'rt') as file:
            lines = file.readlines()
    except:
        logging.warning('Could not load the list of task managers!')
        return {}

    lproxies = [parse_proxy(x.strip()) for x in lines if x[0:5] == 'proxy']
    proxies = {}

    for p in lproxies:
        if p != None:
            proxies[p[0]] = p[1]

    ltms = [parse_node(x.strip(), proxies) for x in lines if x[0:4] == 'node']
    tms = {}
    for t in ltms:
        if t != None:
            tms[t[0]] = t[1]

    logging.debug('Loaded %d task managers.' % (len(tms),))

    return tms

###############################################################################
# Exchange messages with an endpoint to begin pushing tasks
###############################################################################
def setup_endpoint_for_pushing(e):
    try:
        # Try to connect to a task manager
        e.Open(jm_conn_timeout)

        # Ask if it is possible to send tasks
        e.WriteInt64(messaging.msg_send_task)

        # Wait for a response
        response = e.ReadInt64(jm_recv_timeout)

        if response == 0:
            # Task mananger is full
            logging.debug('Task manager at %s:%d is full.',
                e.address, e.port)
            e.Close()
            return 0

        elif response < 0:
            # The task manager is not replying as expected
            logging.error('Unknown response from the task manager!')
            e.Close()
            return 0

        return response

    except:
        traceback.print_exc()
        # Problem connecting to the task manager
        logging.warning('Error connecting to task manager at %s:%d!',
            e.address, e.port)

    e.Close()
    return 0

###############################################################################
# Exchange messages with an endpoint to begin reading results
###############################################################################
def setup_endpoint_for_pulling(e):
    try:
        # Try to connect to a task manager
        e.Open(jm_conn_timeout)

        # Ask if it is possible to send tasks
        e.WriteInt64(messaging.msg_read_result)

        # Wait for a response
        response = e.ReadInt64(jm_recv_timeout)

        if response == 0:
            # Task mananger is empty
            logging.debug('Task manager at %s:%d is empty.',
                e.address, e.port)
            e.Close()
            return 0

        elif response < 0:
            # The task manager is not replying as expected
            logging.error('Unknown response from the task manager!')
            e.Close()
            return 0

        return response

    except:
        # Problem connecting to the task manager
        logging.warning('Error connecting to task manager at %s:%d!',
            e.address, e.port)

    e.Close()
    return False

###############################################################################
# Push tasks while the task manager is not full
###############################################################################
def push_tasks(job, jm, tm, taskid, task, taskms, tasklist, tosend, machineid):
    # Keep pushing until finished or the task manager is full
    sent = []
    while tosend > 0:
        if task == None:
            # Only get a task if the last one was already sent
            newtaskid = taskid + 1
            r1, newtask, ctx = job.spits_job_manager_next_task(jm, newtaskid)
            
            # Exit if done
            if r1 == 0:
                return (True, 0, None, set(), sent)
            
            if newtask == None:
                logging.error('Task %d was not pushed!', newtaskid)
                return (False, taskid, task, taskms, sent)

            if ctx != newtaskid:
                logging.error('Context verification failed for task %d!', 
                    newtaskid)
                return (False, taskid, task, taskms, sent)

            # Add the generated task to the tasklist
            taskid = newtaskid
            task = newtask[0]
            taskms = set()
            tasklist[taskid] = (0, task)

            logging.debug('Generated task %d with payload size of %d bytes.', 
                taskid, len(task) if task != None else 0)

        try:
            logging.debug('Pushing task %d...', taskid)

            # Push the task to the active task manager
            tm.WriteInt64(taskid)
            if task == None:
                tm.WriteInt64(0)
            else:
                tm.WriteInt64(len(task))
                tm.Write(task)

            # Continue pushing tasks
            taskms.add(machineid)
            sent.append((taskid, task, taskms))
            task = None
            tosend = tosend - 1

        except:
            # Something went wrong with the connection,
            # try with another task manager
            break

    return (False, taskid, task, taskms, sent)

###############################################################################
# Read and commit tasks while the task manager is not empty
###############################################################################
def commit_tasks(job, co, tm, tasklist, completed, torecv, total):
    # Keep pulling until finished or the task manager is full
    while torecv > 0:
        try:
            # Pull the task from the active task manager
            taskid = tm.ReadInt64(jm_recv_timeout)

            if taskid == messaging.msg_read_empty:
                # No more task to receive
                return

            # Read the rest of the task
            r = tm.ReadInt64(jm_recv_timeout)
            ressz = tm.ReadInt64(jm_recv_timeout)
            res = tm.Read(ressz, jm_recv_timeout)
            torecv = torecv-1

            # Warning, exceptions after this line may cause task loss
            # if not handled properly!!

            if r == messaging.res_module_error:
                logging.error('The remote worker crashed while ' +
                    'executing task %d!', r)
            elif r != 0:
                logging.error('The task %d was not successfully executed, ' +
                    'worker returned %d!', taskid, r)

            # Validated completed task
            c = completed.get(taskid, (None, None))

            if c[0] != None:
                # This may happen with the fault tolerance system. This may
                # lead to tasks being put in the tasklist by the job manager
                # while being committed. The tasklist must be constantly
                # sanitized.
                logging.warning('The task %d was received more than once ' +
                    'and will not be committed again!',
                    taskid)
                # Removed the completed task from the tasklist
                tasklist.pop(taskid, (None, None))
                continue

            # Remove it from the tasklist

            p = tasklist.pop(taskid, (None, None))
            if p[0] == None and c[0] == None:
                # The task was not already completed and was not scheduled
                # to be executed, this is serious problem!
                logging.error('The task %d was not in the working list!',
                    taskid)

            r2 = job.spits_committer_commit_pit(co, res)
            total = total + 1

            if r2 != 0:
                logging.error('The task %d was not successfully committed, ' +
                    'committer returned %d', taskid, r2)

            # Add completed task to list
            completed[taskid] = (r, r2)
            logging.debug('Task %d successfully committed.', taskid)
            logging.debug('%d tasks committed.', total)
        except:
            # Something went wrong with the connection,
            # try with another task manager
            break
    return total

###############################################################################
# Job Manager routine
###############################################################################
def jobmanager(argv, job, jm, tasklist, completed):
    logging.info('Job manager running...')

    # Load the list of nodes to connect to
    tmlist = load_tm_list()

    # Store some metadata
    submissions = [] # (taskid, submission time, [sent to])

    # Task generation loop

    taskid = 0
    task = None
    taskms = set()
    finished = False

    while True:
        # Reload the list of task managers at each
        # run so new tms can be added on the fly
        try:
            newtmlist = load_tm_list()
            if len(newtmlist) > 0:
                tmlist = newtmlist
            else:
                logging.warning('New list of task managers is ' +
                    'empty and will not be updated!')
        except:
            logging.error('Failed parsing task manager list!')

        for name, tm in tmlist.items():
            logging.debug('Connecting to %s:%d...', tm.address, tm.port)

            machineid = '%s:%d' % (tm.address, tm.port)
            if task != None and machineid in taskms:
                logging.debug('The task %d will not be submitted to the same tm %s:%d again!', taskid, tm.address, tm.port)

                # Exit the job manager when done
                if len(tasklist) == 0 and completed[0] == 1:
                    return

                continue

            # Open the connection to the task manager and query if it is
            # possible to send data
            tosend = setup_endpoint_for_pushing(tm)
            if tosend == 0:
                continue

            logging.debug('Pushing %d tasks to %s:%d...', tosend, tm.address, tm.port)

            # Task pushing loop
            finished, taskid, task, taskms, sent = push_tasks(job, jm, tm,
                taskid, task, taskms, tasklist, tosend, machineid)

            # Add the sent tasks to the sumission list
            submissions = submissions + sent

            # Close the connection with the task manager
            tm.Close()

            logging.debug('Finished pushing tasks to %s:%d.',
                tm.address, tm.port)

            if finished and completed[0] == 0:
                # Tell everyone the task generation was completed
                logging.info('All tasks generated.')
                completed[0] = 1

            # Exit the job manager when done
            if len(tasklist) == 0 and completed[0] == 1:
                return

            # Keep sending the uncommitted tasks
            # TODO: WARNING this will flood the system
            # with repeated tasks
            if finished and len(tasklist) > 0:
                if len(submissions) == 0:
                    logging.critical('The submission list is empty but '
                        'the task list is not! Some tasks were lost!')

                # Select the oldest task that is not already completed
                while True:
                    taskid, task, taskms = submissions.pop(0)
                    # TODO: Add replication threshold
                    if taskid in tasklist:
                        break

        # Add task back to submissions
        if task != None:
            submissions = submissions + [(taskid, task, taskms)]
            taskid, task, taskms = submissions.pop(0)

        # Remove the committed tasks from the submission list
        submissions = [x for x in submissions if x[0] in tasklist]

        time.sleep(jm_send_backoff)

###############################################################################
# Committer routine
###############################################################################
def committer(argv, job, co, tasklist, completed):
    logging.info('Committer running...')

    # Load the list of nodes to connect to
    tmlist = load_tm_list()
    total = 0

    # Result pulling loop
    while True:
        # Reload the list of task managers at each
        # run so new tms can be added on the fly
        try:
            newtmlist = load_tm_list()
            if len(newtmlist) > 0:
                tmlist = newtmlist
            else:
                logging.warning('New list of task managers is ' +
                    'empty and will not be updated!')
        except:
            logging.error('Failed parsing task manager list!')

        for name, tm in tmlist.items():
            logging.debug('Connecting to %s:%d...', tm.address, tm.port)

            # Open the connection to the task manager and query if it is
            # possible to send data
            torecv = setup_endpoint_for_pulling(tm)
            if torecv == 0:
                continue

            logging.debug('Pulling %d tasks from %s:%d...', torecv, tm.address, tm.port)

            # Task pulling loop
            total = commit_tasks(job, co, tm, tasklist, completed, torecv, total)

            # Close the connection with the task manager
            tm.Close()

            logging.debug('Finished pulling tasks from %s:%d.',
                tm.address, tm.port)

            if len(tasklist) == 0 and completed[0] == 1:
                logging.info('All tasks committed.')
                return

        # Refresh the tasklist
        for taskid in completed:
            tasklist.pop(taskid, 0)

        time.sleep(jm_recv_backoff)

###############################################################################
# Kill all task managers
###############################################################################
def killtms():
    logging.info('Killing task managers...')

    # Load the list of nodes to connect to
    tmlist = load_tm_list()

    for name, tm in tmlist.items():
        try:
            logging.debug('Connecting to %s:%d...', tm.address, tm.port)

            tm.Open(jm_conn_timeout)
            tm.WriteInt64(messaging.msg_terminate)
            tm.Close()
        except:
            # Problem connecting to the task manager
            logging.warning('Error connecting to task manager at %s:%d!',
                tm.address, tm.port)

###############################################################################
# Run routine
###############################################################################
def run(argv, jobinfo, job):
    # List of pending tasks
    tasklist = {}

    # Keep an extra list of completed tasks
    completed = {0: 0}

    # Start the job manager
    logging.info('Starting job manager...')

    # Create the job manager from the job module
    jm = job.spits_job_manager_new(argv, jobinfo)

    jmthread = threading.Thread(target=jobmanager,
        args=(argv, job, jm, tasklist, completed))
    jmthread.start()

    # Start the committer
    logging.info('Starting committer...')

    # Create the job manager from the job module
    co = job.spits_committer_new(argv, jobinfo)

    cothread = threading.Thread(target=committer,
        args=(argv, job, co, tasklist, completed))
    cothread.start()

    # Wait for both threads
    jmthread.join()
    cothread.join()

    # Commit the job
    logging.info('Committing Job...')
    r, res, ctx = job.spits_committer_commit_job(co, 0x12345678)
    logging.debug('Job committed.')

    # Finalize the job manager
    logging.debug('Finalizing Job Manager...')
    job.spits_job_manager_finalize(jm)

    # Finalize the committer
    logging.debug('Finalizing Committer...')
    job.spits_committer_finalize(co)

    if res == None:
        logging.error('Job did not push any result!')
        return messaging.res_module_noans, None

    if ctx != 0x12345678:
        logging.error('Context verification failed for job!')
        return messaging.res_module_ctxer, None

    logging.debug('Job finished successfully.')
    return r, res[0]

###############################################################################
# Main routine
###############################################################################
def main(argv):
    # Print usage
    if len(argv) <= 1:
        abort('USAGE: jm module [module args]')

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

    # Wrapper to include job module
    def run_wrapper(argv, jobinfo):
        return run(argv, jobinfo, job)

    # Run the module
    logging.info('Running module')
    r = job.spits_main(margv, run_wrapper)

    # Kill the workers
    if jm_killtms:
        killtms()

    # Finalize
    logging.debug('Bye!')
    #exit(r)

###############################################################################
# Entry point
###############################################################################
if __name__ == '__main__':
    main(sys.argv)
