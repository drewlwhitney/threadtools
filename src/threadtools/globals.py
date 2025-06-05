import threading
from queue import Empty, Queue
from threading import Thread
from typing import Callable
from weakref import WeakKeyDictionary

from .lock import DataLock


class CallbackQueueContainer:
    def __init__(self) -> None:
        self.callback_queues: DataLock[WeakKeyDictionary[Thread, Queue[Callable[[], None]]]] = (
            DataLock(WeakKeyDictionary())
        )

    def get_callback_queue(self, thread: Thread) -> Queue[Callable[[], None]]:
        """Get the callback queue associated with `thread`. This is thread-safe."""
        with self.callback_queues as callback_queues:
            try:  # if there is already a queue for `thread`, return it
                return callback_queues[thread]
            except KeyError:  # otherwise add a new queue and return it
                queue: Queue[Callable[[], None]] = Queue()
                with self.callback_queues as callback_queues:
                    callback_queues[thread] = queue
                return queue

    def process_events(self):
        """Process all events for the current thread."""
        queue = self.get_callback_queue(threading.current_thread())
        try:
            while True:
                callback = queue.get_nowait()
                callback()
        except Empty:
            pass


CALLBACK_QUEUES = CallbackQueueContainer()


def process_events():
    """Process all events for the current thread."""
    CALLBACK_QUEUES.process_events()
