---
title: "Pyscheduler lesson learn"
date: 2025-01-15
description: "experiment of pyschduler"
tags:
    - tech sharing
    - python 
categories: 'Tech blogs'
featured_image: "notebook2.jpeg"
---
I encountered an issue at work.




```python
import time
def schedule_tasks():
    import pyscheduler

    # Create a scheduler instance
    scheduler = pyscheduler.Scheduler()

    # Define a sample task
    def sample_task():
        time.sleep(10)
        print("Task executed")

    # Schedule the task to run every 10 seconds
    scheduler.every(10).seconds.do(sample_task)

    scheduler.start()

    while True:
        pass
```
### Using Pyscheduler with ThreadPool

Pyscheduler is a powerful library for scheduling tasks in Python. However, when dealing with multiple tasks, it can be beneficial to use a thread pool to manage concurrent execution. This can help improve performance and ensure that tasks are executed efficiently.

Here's an example of how to use Pyscheduler with a ThreadPool:
```python
import time
from concurrent.futures import ThreadPoolExecutor
import pyscheduler

# Create a scheduler instance
scheduler = pyscheduler.Scheduler()

# Define a sample task
def sample_task():
    time.sleep(10)
    print("Task executed")

# Create a ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=5)

# Schedule the task to run every 10 seconds using the thread pool
scheduler.every(10).seconds.do(lambda: executor.submit(sample_task))

scheduler.start()

while True:
    pass
```

In this example, we use `ThreadPoolExecutor` from the `concurrent.futures` module to create a pool of threads. The `max_workers` parameter specifies the maximum number of threads that can be used to execute tasks concurrently. We then schedule the `sample_task` to run every 10 seconds using the thread pool by submitting it to the executor.

By using a thread pool, we can ensure that multiple tasks can be executed concurrently without blocking the main thread, leading to better performance and responsiveness in our applications.