# import threading
# from threading import Thread

from threading import Thread

from src.threadtools import Signal, process_events

from .common import DummyReceiver


class DummyObject:
    def __init__(self, data: int):
        self.data = data

    def method(self, x: int):
        pass

    def set_data(self, data: int):
        self.data = data


def test_emit_single_thread():
    signal = Signal[int]()
    receiver = DummyReceiver(234)
    test_object = DummyObject(2)

    # verify calling emit() in the same thread instantly calls the function
    signal.connect(receiver, test_object.set_data)
    assert test_object.data == 2
    signal.emit(47)
    assert test_object.data == 47
    assert receiver.callback_queue.get().empty() is True


def test_emit_multi_thread():
    signal = Signal[int]()
    receiver = DummyReceiver(234)
    test_object = DummyObject(2)

    # verify calling emit() from a different thread schedules the function
    signal.connect(receiver, test_object.set_data)
    thread = Thread(target=process_events)
    receiver.move_to_thread(thread)
    assert test_object.data == 2
    signal.emit(50)
    assert test_object.data == 2  # should still be 2
    assert receiver.callback_queue.get().empty() is False  # there should be a callback there now
    # this is in the wrong thread so nothing should change yet
    process_events()
    assert test_object.data == 2
    # after running `process_events()` in the correct thread, the callback should run
    thread.start()
    thread.join()
    assert test_object.data == 50


def test_disconnect():
    signal = Signal[int]()
    receiver = DummyReceiver(54)

    def temp_func(x: int):
        pass

    # callbacks
    callback_id = signal.connect(receiver, temp_func)
    assert len(signal.callbacks.get()) == 1
    signal.disconnect(callback_id)
    assert len(signal.callbacks.get()) == 0
    # methods
    test_object = DummyObject(2)
    method_id = signal.connect(receiver, test_object.method)
    assert len(signal.methods.get()) == 1
    signal.disconnect(method_id)
    assert len(signal.methods.get()) == 0


def test_callbacks():
    signal = Signal[int, float, str]()
    receiver = DummyReceiver(4)

    def temp_func(x: int, y: float, z: str):
        pass

    # verify regular functions work
    callback_id = signal.connect(receiver, temp_func)
    assert signal.callbacks.get()[callback_id][0]() == temp_func
    # verify that deleting the function causes it to get removed from the signal
    del temp_func
    signal.emit(2, 3.0, "")
    assert len(signal.callbacks.get()) == 0


def test_methods():
    signal = Signal[int]()
    receiver = DummyReceiver(1)
    test_object = DummyObject(23489)

    # verify methods work
    method_id = signal.connect(receiver, test_object.method)
    assert signal.methods.get()[method_id][0]() == test_object.method
    # verify that deleting an object causes it's method to get removed from the signal
    del test_object
    signal.emit(5)
    assert len(signal.methods.get()) == 0
