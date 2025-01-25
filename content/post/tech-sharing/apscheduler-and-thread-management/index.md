+++
author = "Meswsoul"
title = "Share an APScheduler's example and the issue caused by child processes"
date = "2025-01-25"
description = "Implementing Apscheduler with 2 thread management ways"
tags = [

    "Python",

]
categories = [

    "Tech-Notes",

]
series = ["Python"]
image = "default-cover.png"
+++

> AI is becoming more and more popular, and Python automation is more accessible than ever.
> When you need to perform tasks regularly, such as data backup or crawling API data, for such needs, 
> it's recommended to use Python's powerful scheduling framework:
> [APScheduler](https://apscheduler.readthedocs.io/en/3.x/)。

## Case: Client Countdown Program

At work, there is a Python App running on the client side, which polls our backend 
to get the latest task settings and saves them locally.
After that, it relys on APScheduler to execute offline tasks regularly. 
When the task is completed, the results are packaged and uploaded back to our backend.

The advantage of this design is that the backend is clean and simple, 
and the logic of processing timing is concentrated on the client side.
The disadvantage is that once a problem occurs, you can only rely on the 
offline log provided by the customer to debug, and often cannot obtain detailed information.

## Issue

I recently encountered a strange problem: 
the App suddenly stopped accessing the backend and stopped uploading the results files.
The log shows that the offline tasks are still being executed stably 
and the results are continuously packaged. It seems that the scheduler is also functional.
This problem has occurred on several clients. 
Once this happens, the only way to restore to normal is to restart the App.

I initially thought it was a connection issue with the backend, 
but after reading the issue log, I was blanky.
The main program is supposed to keep trying, but sometimes it will never try to connect to the backend again after a normal connection (like it disappeared after a date?).

## What goes wrong？

* **When the system crashes and the main process does not manage child processes/threads correctly, the child processes will remain, causing unpredictable behavior.**

Basically, the main program crashes, the subjobs abort.
When you execute a Python script, the Python interpreter starts a main process to run the code, and all threads are created and managed by the main process.

The APScheduler scheduler is also managed by the main process. 
When the main program crashes, the scheduler stops running, and all sub-jobs should be forced to terminate.
It just so happens that in my case, the subtask lasts for N hours, so that new logs continue to be generated after the main program crashes.

> Note: If you use multiprocessing (the multiprocessing module), 
> the main process will spawn child processes to perform work.
> Each subprocess has its own memory space and Python interpreter, 
> and is not restricted by the GIL. But it is still better to set it up so that 
> the main process manages these sub-processes, which will be mentioned later.

## Experiment

To reproduce the error, I simulate a small task and try to exit the main program before the child process/thread ends.

```python
def run(logger):
    """simulate a task"""
    logger.info('running from Func')
    time.sleep(5)
    logger.info('end of running from Func')
```

### Experiment 1 - ThreadPoolExecutor

For I/O bounded tasks, use `ThreadPoolExecutor` , which is also the default setting.

```python
    logger = create_logger()
    
    scheduler = BackgroundScheduler(
         executors={'default': ThreadPoolExecutor(1)}
    )

    scheduler.start()
    scheduler.add_job(run, 'interval', args=[logger], seconds=5, max_instances=5)

    try:
        logger.info("Scheduler is running. Press Ctrl+C to exit.")
        while True:
            for i in range(20):
                logger.info(f'main running {i} sec')
                time.sleep(1)
            exit(88)
    except (KeyboardInterrupt, SystemExit) as e:
        logger.error(f"Main program terminated {e}")
        scheduler.shutdown(wait=False)

```

As you can see, the thread continues to write logs after the main program reports an error exit code.

```
2025-01-15 15:52:57,207 - MyAppLogger - INFO - Scheduler is running. Press Ctrl+C to exit.
2025-01-15 15:52:57,207 - MyAppLogger - INFO - main running 0 sec
2025-01-15 15:52:58,208 - MyAppLogger - INFO - main running 1 sec
2025-01-15 15:52:59,210 - MyAppLogger - INFO - main running 2 sec
2025-01-15 15:53:00,211 - MyAppLogger - INFO - main running 3 sec
2025-01-15 15:53:01,212 - MyAppLogger - INFO - main running 4 sec
2025-01-15 15:53:02,207 - MyAppLogger - INFO - running from Func
2025-01-15 15:53:02,213 - MyAppLogger - INFO - main running 5 sec
2025-01-15 15:53:03,215 - MyAppLogger - INFO - main running 6 sec
2025-01-15 15:53:04,215 - MyAppLogger - INFO - main running 7 sec
2025-01-15 15:53:05,216 - MyAppLogger - INFO - main running 8 sec
2025-01-15 15:53:06,217 - MyAppLogger - INFO - main running 9 sec
2025-01-15 15:53:07,213 - MyAppLogger - INFO - end of running from Func
2025-01-15 15:53:07,213 - MyAppLogger - INFO - running from Func
2025-01-15 15:53:07,218 - MyAppLogger - INFO - main running 10 sec
...
2025-01-15 15:53:16,231 - MyAppLogger - INFO - main running 19 sec
2025-01-15 15:53:17,225 - MyAppLogger - INFO - end of running from Func
2025-01-15 15:53:17,225 - MyAppLogger - INFO - running from Func
2025-01-15 15:53:17,233 - MyAppLogger - ERROR - Main program terminated 88
2025-01-15 15:53:22,226 - MyAppLogger - INFO - end of running from Func

```

### Experiment 2 - ProcessPoolExecutor

Replace it with the following, the result is the same.
It waits for the child process to finish executing:

```python
    # Default False, non-daemon process
    # multiprocessing.current_process().daemon = True
    scheduler = BackgroundScheduler(
        executors={'default': ProcessPoolExecutor(1)}
    )
--
2025-01-15 15:56:43, 915 - MyAppLogger - INFO - main running 19 sec
2025-01-15 15:56:44, 917 - MyAppLogger - ERROR - Main program terminated 88
>>> Still waiting on run() for 5 seconds
# Because of process isolation, logger is not shared, stdout is not correctly piped to the main program,
# Need to reconfigure the logger in run to print. I didn't do it here.
```

If you modify to a daemon-process, it means that the current process will automatically end when the parent process terminates, without blocking or continuing execution, and an error will be obtained, 
`AssertionError: daemonic processes are not allowed to have children` , of course, this is not what we want.

## Conclusion, besides handling errors, what's other remedies?

After I solved a small bug that caused the main program to crash, the problem is solved.

But think further, is there any good solution?
The following are some common ways to better support main program crashes:
1. Set up a cron job or use systemd monitoring (Linux) to restart the main program once it crashes.
1. Use Celery or Redis Queue (RQ) to completely separate the job from the main program's scheduling.
APScheduler is only responsible for scheduling, and execution is handed over to independent job managers or workers.
Its additional benefit is that it supports **persistence**, and unfinished jobs can continue to execute after the main program is restarted.

In fact, our backend which deals the upload file is using RQ. Maybe write about it in the future. 

## Reference

* Use Event to manage, [Python Multiprocessing graceful shutdown in the proper order](https://www.peterspython.com/en/blog/python-multiprocessing-graceful-shutdown-in-the-proper-order)
* [Python 定时任务框架 APScheduler 详解](https://www.cnblogs.com/leffss/p/11912364.html)
