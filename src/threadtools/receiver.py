import threading
from queue import Queue
from threading import Thread
from typing import Callable

from .globals import CALLBACK_QUEUES
from .lock import DataLock


class SignalReceiver:
    """
    An object that supports receiving signals. For an object to support receiving signals, it must
    inherit from `SignalReceiver`.
    """

    def __init__(self) -> None:
        # the object's initial thread affinity is the thread it was created in
        current_thread = threading.current_thread()
        self.associated_thread: DataLock[Thread] = DataLock(current_thread)
        self.callback_queue: DataLock[Queue[Callable[[], None]]] = DataLock(
            CALLBACK_QUEUES.get_callback_queue(current_thread)
        )

    def post_callback(self, callback: Callable[[], None]):
        """Post a `callback` to the callback queue."""
        with self.callback_queue as callback_queue:
            callback_queue.put(callback)

    def get_thread(self) -> Thread:
        """Get the thread affinity for this object."""
        return self.get_thread_lock().get()

    def get_thread_lock(self) -> DataLock[Thread]:
        """Get the thread affinity for this object, protected by a lock."""
        return self.associated_thread

    def move_to_thread(self, thread: Thread):
        """Change this object's thread affinity `thread`."""
        self.associated_thread.set(thread)
        self.callback_queue.set(CALLBACK_QUEUES.get_callback_queue(thread))
