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

from libspitz import JobBinary, SimpleEndpoint
from libspitz import messaging, config

import Args
import sys, threading, os, time, ctypes, logging, struct, threading, traceback

###############################################################################
# Parse global configuration
###############################################################################
def parse_global_config(argdict):
    pass

###############################################################################
# Configure the log output format
###############################################################################
def setup_log():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers = []
    ch = logging.StreamHandler(sys.stderr)
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
# Run routine
###############################################################################
def run(argv, job):
    jm = job.spits_job_manager_new(argv)
    co = job.spits_committer_new(argv)
    wk = job.spits_worker_new(argv)
    taskid = 0

    while True:
        taskid += 1

        r1, task = job.spits_job_manager_next_task(jm)
        
        if r1 == 0:
            break

        logging.debug('Generated task %d.', taskid)

        logging.info('Processing task %d...', taskid)

        r2, res, ctx = job.spits_worker_run(wk, task, taskid)

        logging.info('Task %d processed.', taskid)

        if res == None:
            logging.error('Task %d did not push any result!', taskid)
            continue

        if ctx != taskid:
            logging.error('Context verification failed for task %d!', taskid)
            continue

        r3 = job.spits_committer_commit_pit(co, res[0])

        if r3 != 0:
            logging.error('The task %d was not successfully committed, ' +
                'committer returned %d', taskid, r3)
            continue

    job.spits_job_manager_finalize(jm)

    logging.info('Committing Job...')
    r, res, ctx = job.spits_committer_commit_job(co, 0x12345678)

    job.spits_worker_finalize(wk)

    if res == None:
        logging.error('Job did not push any result!')
        return messaging.res_module_noans, None

    if ctx != 0x12345678:
        logging.error('Context verification failed for job!')
        return messaging.res_module_ctxer, None

    return r, res[0]

###############################################################################
# Main routine
###############################################################################
def main(argv):
    # Setup logging
    setup_log()
    logging.debug('Hello!')

    # Print usage
    if len(argv) <= 1:
        abort('USAGE: jm module [module args]')

    # Parse the arguments
    args = Args.Args(argv)
    parse_global_config(args.args)

    # Load the module
    module = args.margs[0]
    job = JobBinary(module)

    # Remove JM arguments when passing to the module
    margv = args.margs

    # Wrapper to include job module
    def run_wrapper(argv):
        return run(argv, job)

    # Run the module
    logging.info('Running module')
    r = job.spits_main(margv, run_wrapper)

    # Finalize
    logging.debug('Bye!')
    #exit(r)

###############################################################################
# Entry point
###############################################################################
if __name__ == '__main__':
    main(sys.argv)
