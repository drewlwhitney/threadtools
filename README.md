# threadtools
Support for signals and better locks in native Python.

# Inspiration
PyQt lets you "emit" signals that have function callbacks tied to them. Why shouldn't we have that in native Python?

# Basic Usage
```python
import time
from threading import Thread

from threadtools import Signal, SignalReceiver, process_events


class ThreadedProcess:
    def __init__(self):
        self.somethingHappened = Signal[str]()
        self.countChanged = Signal[int]()
        self.finished = Signal()  # no typing implies no arguments to `emit()`

    def run(self):
        """Mimics a long-running process that updates its progress."""
        for i in range(1, 6):
            time.sleep(1)
            self.countChanged.emit(i)
            if i == 3:
                self.somethingHappened.emit("something happened!")
        self.finished.emit()


receiver = SignalReceiver()
threaded_process = ThreadedProcess()
thread = Thread(target=threaded_process.run)
# connect signals
threaded_process.countChanged.connect(receiver, print)
threaded_process.somethingHappened.connect(receiver, print)
threaded_process.finished.connect(receiver, lambda: print("done!"))
# run the thread
thread.start()
# you must call `process_events()` to receive signals from other threads
# `receiver` was created in a different thread than `thread`, so signal
# callbacks are queued rather than being run immediately
while thread.is_alive():
    process_events()

# prints:
# 1
# 2
# 3
# something happened!
# 4
# 5
# done!
```

# Thread Safety
`threadtools` is designed to be thread-safe as long as signals are connected to the correct recipient. Recipients must be `SignalObject`s. `SignalObject`s can be associated with a different thread using their `move_to_thread()` method.