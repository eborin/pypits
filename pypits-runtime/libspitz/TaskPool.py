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

import threading, sys, logging

try:
    import Queue as queue # Python 2
except:
    import queue # Python 3

class TaskPool(object):
    """description of class"""

    def __init__(self, max_threads, overfill, initializer, worker, user_args):
        self.max_threads = max_threads
        self.user_args = user_args
        self.initializer = initializer
        self.worker = worker
        self.maxsize=max_threads+overfill
        self.tasks = queue.Queue(maxsize=self.maxsize)
        self.threads = [threading.Thread(target=self.runner) for
            i in range(max_threads)]

        for t in self.threads:
            t.start()

    def runner(self):
        state = None
        try:
            # Initialize the module worker
            state = self.initializer(*self.user_args)
        except:
            # TODO better exception handling
            pass
        while True:
            # Pick a task from the queue and execute it
            # TODO better tm kill
            taskid, task = self.tasks.get()
            try:
                self.worker(state, taskid, task, *self.user_args)
            except:
                logging.error('The worker crashed while processing ' +
                    'the task %d', taskid)

    def Put(self, taskid, task):
        try:
            self.tasks.put_nowait((taskid, task))
        except queue.Full:
            return False
        return True

    def Free(self):
        return self.maxsize-self.tasks.qsize()

    def Full(self):
        return self.tasks.full()
