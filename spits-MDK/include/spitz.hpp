/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2015 Caian Benedicto <caian@ggaunicamp.com>
 * Copyright (c) 2014 Ian Liu Rodrigues <ian.liu@ggaunicamp.com>
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy 
 * of this software and associated documentation files (the "Software"), to 
 * deal in the Software without restriction, including without limitation the 
 * rights to use, copy, modify, merge, publish, distribute, sublicense, 
 * and/or sell copies of the Software, and to permit persons to whom the 
 * Software is furnished to do so, subject to the following conditions:
 * 
 * The above copyright notice and this permission notice shall be included in 
 * all copies or substantial portions of the Software.
 * 
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL 
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS 
 * IN THE SOFTWARE.
 */

#ifndef __SPITZ_CPP__
#define __SPITZ_CPP__

#include "spitz.h"
#include "stream.hpp"

namespace spitz {
    
    class pusher
    {
    private:
        spitspush_t pushf;
        spitsctx_t ctx;
        
    public:
        pusher(spitspush_t pushf, spitsctx_t ctx) : 
            pushf(pushf), ctx(ctx)
        {
        }
        
        void push(const ostream& p) const
        {
            this->pushf(p.data(), p.pos(), this->ctx);
        }
        
        void push(const void* p, spitssize_t s) const
        {
            this->pushf(p, s, this->ctx);
        }
    };
    
    class runner
    {
    private:
        spitzrun_t runf;
        
    public:
        runner(spitzrun_t runf) : runf(runf)
        {
        }
        
        int run(int argc, const char** argv) const
        {
            ostream j;
            istream r;
            return run(argc, argv, j, r);
        }
        
        int run(int argc, const char** argv, istream& final_result) const
        {
            ostream j;
            return run(argc, argv, j, final_result);
        }
        
        int run(int argc, const char** argv, ostream& jobinfo) const
        {
            istream r;
            return run(argc, argv, jobinfo, r);
        }

        int run(int argc, const char** argv, ostream& jobinfo, 
            istream& final_result) const
        {
            const void* pfinal_result;
            spitssize_t pfinal_result_size;
            const void* pjobinfo = jobinfo.data();
            spitssize_t pjobinfo_size = jobinfo.pos();
            int r = this->runf(argc, argv, pjobinfo, pjobinfo_size, 
                &pfinal_result, &pfinal_result_size);
            final_result = istream(pfinal_result, pfinal_result_size);
            return r;
        }
    };
    
    class spitz_main
    {
    public:
        virtual int main(int argc, const char* argv[], const runner& runner)
        {
            return runner.run(argc, argv);
        }
        virtual ~spitz_main(){ }
    };
    
    class job_manager
    {
    public:
        virtual bool next_task(const pusher& task) = 0;
        virtual ~job_manager() { }
    };

    class worker
    {
    public:
        virtual int run(istream& task, const pusher& result) = 0;
        virtual ~worker() { }
    };

    class committer
    {
    public:
        virtual int commit_task(istream& result) = 0;
        virtual int commit_job(const pusher& final_result) {
            final_result.push(NULL, 0);
            return 0;
        }
        virtual ~committer() { }
    };

    class factory
    {
    public:
        virtual spitz_main *create_spitz_main() { return new spitz_main(); }
        virtual job_manager *create_job_manager(int, const char *[], istream&) = 0;
        virtual worker *create_worker(int, const char *[]) = 0;
        virtual committer *create_committer(int, const char *[], istream&) = 0;
    };
};

extern spitz::factory *spitz_factory;

#ifdef SPITZ_ENTRY_POINT

extern "C" int spits_main(int argc, const char* argv[], spitzrun_t run)
{
    spitz::spitz_main *sm = spitz_factory->create_spitz_main();
    spitz::runner runner(run);
    
    int r = sm->main(argc, argv, runner);
    
    delete sm;
    
    return r;
}

extern "C" void *spits_job_manager_new(int argc, const char *argv[],
    const void* jobinfo, spitssize_t jobinfosz)
{
    spitz::istream ji(jobinfo, jobinfosz);
    spitz::job_manager *jm = spitz_factory->create_job_manager(argc, argv, ji);
    return reinterpret_cast<void*>(jm);
}

extern "C" int spits_job_manager_next_task(void *user_data, 
    spitspush_t push_task, spitsctx_t jmctx)
{
    class spitz::job_manager *jm = reinterpret_cast
        <spitz::job_manager*>(user_data);
    
    spitz::pusher task(push_task, jmctx);
    return jm->next_task(task) ? 1 : 0;
}

extern "C" void spits_job_manager_finalize(void *user_data)
{
    class spitz::job_manager *jm = reinterpret_cast
        <spitz::job_manager*>(user_data);
    
    delete jm;
}

extern "C" void *spits_worker_new(int argc, const char **argv)
{
    spitz::worker *w = spitz_factory->create_worker(argc, argv);
    return reinterpret_cast<void*>(w);
}

extern "C" int spits_worker_run(void *user_data, const void* task, 
    spitssize_t tasksz, spitspush_t push_result, 
    spitsctx_t taskctx)
{
    spitz::worker *w = reinterpret_cast
        <spitz::worker*>(user_data);
    
    spitz::istream stask(task, tasksz);
    spitz::pusher result(push_result, taskctx);
    
    return w->run(stask, result);
}

extern "C" void spits_worker_finalize(void *user_data)
{
    spitz::worker *w = reinterpret_cast
        <spitz::worker*>(user_data);
    
    delete w;
}

extern "C" void *spits_committer_new(int argc, const char *argv[],
    const void* jobinfo, spitssize_t jobinfosz)
{
    spitz::istream ji(jobinfo, jobinfosz);
    spitz::committer *co = spitz_factory->create_committer(argc, argv, ji);
    return reinterpret_cast<void*>(co);
}

extern "C" int spits_committer_commit_pit(void *user_data,
    const void* result, spitssize_t resultsz)
{
    spitz::committer *co = reinterpret_cast
        <spitz::committer*>(user_data);
    
    spitz::istream sresult(result, resultsz);
    return co->commit_task(sresult);
}

extern "C" int spits_committer_commit_job(void *user_data,
    spitspush_t push_final_result, spitsctx_t jobctx)
{
    spitz::committer *co = reinterpret_cast
        <spitz::committer*>(user_data);
    
    spitz::pusher final_result(push_final_result, jobctx);
    return co->commit_job(final_result);
}

extern "C" void spits_committer_finalize(void *user_data)
{
    spitz::committer *co = reinterpret_cast
        <spitz::committer*>(user_data);
    
    delete co;
}

#ifdef SPITZ_SERIAL_DEBUG
#include <vector>
#include <algorithm>
#include <iostream>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <stdint.h>

static void spitz_debug_pusher(const void* pdata, 
    spitssize_t size, spitsctx_t ctx)
{
    std::vector<uint8_t>* v = reinterpret_cast<std::vector<uint8_t>*>
      (const_cast<void*>(ctx));

    if (v->size() != 0) {
        std::cerr << "[SPITZ] Push called more than once!" << std::endl;
    }

    v->push_back(1);

    std::copy(reinterpret_cast<const uint8_t*>(pdata), 
        reinterpret_cast<const uint8_t*>(pdata) + size, 
        std::back_inserter(*v));
}

static int spitz_debug_runner(int argc, const char** argv, 
    const void* pjobinfo, spitssize_t jobinfosz, 
    const void** pfinal_result, spitssize_t* pfinal_resultsz)
{
    void* jm = spits_job_manager_new(argc, argv, pjobinfo, jobinfosz);
    void* co = spits_committer_new(argc, argv, pjobinfo, jobinfosz);
    void* wk = spits_worker_new(argc, argv);
    
    static int64_t jid = 0;
    int64_t tid = 0;
    
    int r1 = 0, r2 = 0, r3 = 0;
    
    std::vector<int8_t> task;
    std::vector<int8_t> result;
    std::vector<int8_t>* final_result = new std::vector<int8_t>();
    
    while(true) {
        task.clear();
        std::cerr << "[SPITZ] Generating task " << tid << "..." << std::endl;
        if(!spits_job_manager_next_task(jm, spitz_debug_pusher, &task))
            break;
        
        if (task.size() == 0) {
            std::cerr << "[SPITZ] Task manager didn't push a task!"
                << std::endl;
            exit(1);
        }
        
        result.clear();
        std::cerr << "[SPITZ] Executing task " << tid << "..." << std::endl;
        r1 = spits_worker_run(wk, task.data()+1, task.size()-1, 
            spitz_debug_pusher, &result);
        
        if (r1 != 0) {
            std::cerr << "[SPITZ] Task " << tid << "failed to execute!" 
                << std::endl;
            goto dump_task_and_exit;
        }
        
        if (task.size() == 0) {
            std::cerr << "[SPITZ] Worker didn't push a result!"
                << std::endl;
            goto dump_task_and_exit;
        }
        
        std::cerr << "[SPITZ] Committing task " << tid << "..." << std::endl;
        r2 = spits_committer_commit_pit(co, result.data()+1, result.size()-1);
        
        if (r2 != 0) {
            std::cerr << "[SPITZ] Task " << tid << "failed to commit!" 
                << std::endl;
            goto dump_result_and_exit;
        }
        tid++;
    }
    std::cerr << "[SPITZ] Finished processing tasks." << std::endl;
    
    final_result->clear();
    std::cerr << "[SPITZ] Committing job " << jid << "..." << std::endl;
    r3 = spits_committer_commit_job(co, spitz_debug_pusher, final_result);
    
    if (r3 != 0) {
        std::cerr << "[SPITZ] Job " << jid << "failed to commit!" 
            << std::endl;
        exit(1);
    }
    
    if (final_result->size() <= 1) {
        *pfinal_result = NULL;
        *pfinal_resultsz = 0;
    } else {
        *pfinal_result = final_result->data()+1;
        *pfinal_resultsz = final_result->size()-1;
    }
    
    std::cerr << "[SPITZ] Finalizing task manager..." << std::endl;
    spits_job_manager_finalize(jm);
    
    std::cerr << "[SPITZ] Finalizing committer..." << std::endl;
    spits_committer_finalize(co);
    
    std::cerr << "[SPITZ] Finalizing worker..." << std::endl;
    spits_worker_finalize(wk);
    
    std::cerr << "[SPITZ] Job " << jid << " completed." << std::endl;
    jid++;
    
    return 0;
    
dump_result_and_exit:
    {
        std::cerr << "[SPITZ] Generating result dump for task " 
            << tid << "..." << std::endl;
        std::stringstream ss;
        ss << "result-" << tid << ".dump";
        std::ofstream resfile(ss.str().c_str(), std::ofstream::binary);
        resfile.write(reinterpret_cast<const char*>(result.data()+1), 
            result.size()-1);
        resfile.close();
        std::cerr << "[SPITZ] Result dump generated as " << ss.str() << 
            " [" << result.size() << " bytes]. " << std::endl;
    }
dump_task_and_exit:
    {
        std::cerr << "[SPITZ] Generating task dump for task " 
            << tid << "..." << std::endl;
        std::stringstream ss;
        ss << "task-" << tid << ".dump";
        std::ofstream taskfile(ss.str().c_str(), std::ofstream::binary);
        taskfile.write(reinterpret_cast<const char*>(task.data()+1), 
            task.size()-1);
        taskfile.close();
        std::cerr << "[SPITZ] Task dump generated as " << ss.str() << 
            " [" << task.size()-1 << " bytes]. " << std::endl;
    }
    exit(1);
}

int main(int argc, const char** argv)
{
    std::cerr << "[SPITZ] Entering debug mode..." << std::endl;
    spits_main(argc, argv, spitz_debug_runner);
    std::cerr << "[SPITZ] Spitz finished." << std::endl;
}
#endif

#endif

#endif /* __SPITZ_CPP__ */

// vim:ft=cpp:sw=2:et:sta
