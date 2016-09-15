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

#ifndef __SPITZ_H__
#define __SPITZ_H__

#ifdef __cplusplus
extern "C" {
#endif

 /* Python version of spits uses cdecl calling convention */

/* The size used to pass messages is 64 bit */

typedef long long int spitssize_t;

typedef const void* spitsctx_t;

/* Runner callback that executes the task distribution and committing */

typedef int (*spitzrun_t)(int, const char**, const void*, spitssize_t, 
    const void**, spitssize_t*);

/* Pusher callback that performs result submission from a worker */

typedef void (*spitspush_t)(const void*, spitssize_t, spitsctx_t);

/* Spits main */

int spits_main(int argc, const char* argv[], spitzrun_t run);

/* Job Manager */

void* spits_job_manager_new(int argc, const char *argv[],
    const void* jobinfo, spitssize_t jobinfosz);

int spits_job_manager_next_task(void *user_data, 
    spitspush_t push_task, spitsctx_t jmctx);

void spits_job_manager_finalize(void *user_data);

/* Worker */

void* spits_worker_new(int argc, const char *argv[]);

int spits_worker_run(void *user_data, const void* task, 
    spitssize_t tasksz, spitspush_t push_result, 
    spitsctx_t taskctx);

void spits_worker_finalize(void *user_data);

/* Committer */

void* spits_committer_new(int argc, const char *argv[],
    const void* jobinfo, spitssize_t jobinfosz);

int spits_committer_commit_pit(void *user_data,
    const void* result, spitssize_t resultsz);

int spits_committer_commit_job(void *user_data,
    spitspush_t push_final_result, spitsctx_t jobctx);

void spits_committer_finalize(void *user_data);

#ifdef __cplusplus
}
#endif

#endif /* __SPITZ_H__ */
