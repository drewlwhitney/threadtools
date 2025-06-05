import threading
from threading import Thread

from src.threadtools.globals import CALLBACK_QUEUES

from .common import DummyReceiver


def test_receiver():
    receiver = DummyReceiver(5)
    # should start with the thread affinity of the current thread
    assert receiver.get_thread() is threading.current_thread()
    assert receiver.callback_queue.get() is CALLBACK_QUEUES.get_callback_queue(
        threading.current_thread()
    )

    new_thread = Thread()
    # moving to a thread should change the thread affinity
    receiver.move_to_thread(new_thread)
    assert receiver.get_thread() is new_thread
    # moving to a thread should change the queue
    assert receiver.callback_queue.get() is CALLBACK_QUEUES.get_callback_queue(new_thread)

    def temp_func():
        pass

    receiver.post_callback(temp_func)
    assert receiver.callback_queue.get().get() == temp_func
