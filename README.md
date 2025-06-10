# threadtools
Support for signals and better locks in native Python.

# Inspiration
PyQt lets you "emit" signals that have function callbacks tied to them. Why shouldn't we have that in native Python?

# Typical Usage
## Signals
```python
import time
from threading import Thread

from threadtools import Signal, process_events


class ThreadedProcess:
    """Mimics a long-running process that updates its progress."""

    def __init__(self):
        self.somethingHappened = Signal[str]()
        self.countChanged = Signal[int]()
        self.finished = Signal()  # no typing implies no arguments to `emit()`

    def run(self):
        for i in range(1, 6):
            time.sleep(1)
            self.countChanged.emit(i)
            if i == 3:
                self.somethingHappened.emit("Something happened!")
        self.finished.emit()


threaded_process = ThreadedProcess()
thread = Thread(target=threaded_process.run)
# connect signals
threaded_process.countChanged.connect(print)
threaded_process.somethingHappened.connect(print)
threaded_process.finished.connect(lambda: print("Done!"))
# run the thread
thread.start()
# you must call `process_events()` to receive signals from other threads
# `emit()` was called from a different thread than `connect()`, so the callbacks are queued
while thread.is_alive():
    process_events()

# prints:
# 1
# 2
# 3
# Something happened!
# 4
# 5
# Done!
```
## DataLock
```python
from threading import Thread

from threadtools import DataLock

# DataLocks are generic; they support any type
LOCKED_INTEGER = DataLock(0)
LOCKED_STRING = DataLock("Hello, World!")


class DataAccessor:
    """Accesses and mutates data that is behind a lock."""

    def __init__(self, int_value: int):
        self.int_value = int_value

    def run(self):
        # using a context manager locks the lock and returns the stored data
        with LOCKED_INTEGER as locked_int:
            # reading data
            print(locked_int)

            # writing data
            
            # BAD!!
            # this does not change the value inside the lock
            # (Python references don't work that way)
            locked_int = self.int_value
            
            # good
            # DataLocks are reentrant; this will not cause a deadlock
            LOCKED_INTEGER.set(self.int_value)

            # you can also get the data inside the lock using `get()`
            print(LOCKED_INTEGER.get())
        # the lock is unlocked here, at the end of the context


first_accessor = DataAccessor(1)
first_thread = Thread(target=first_accessor.run)

second_accessor = DataAccessor(2)
second_thread = Thread(target=second_accessor.run)

first_thread.start()
second_thread.start()

first_thread.join()
second_thread.join()

# if `first_thread` is started first, prints:
# 0
# 1
# 1
# 2
```

# Thread Safety
`Signal`s are thread-safe as long as they are connected correctly. See the `connect()` method for more details.
