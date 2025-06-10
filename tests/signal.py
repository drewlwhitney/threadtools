# import threading
# from threading import Thread

from threading import Thread

from src.threadtools import Signal, process_events
from src.threadtools.connection import ConnectionType


class DummyObject:
    def __init__(self, data: int):
        self.data = data

    def method(self, x: int):
        pass

    def set_data(self, data: int):
        self.data = data


def test_emit_single_thread():
    signal = Signal[int]()
    test_object = DummyObject(2)

    # verify calling emit() in the same thread instantly calls the function
    signal.connect(test_object.set_data)
    assert test_object.data == 2
    signal.emit(47)
    assert test_object.data == 47


def test_emit_multi_thread():
    signal = Signal[int]()
    test_object = DummyObject(2)

    signal.connect(test_object.set_data)
    thread = Thread(target=signal.emit, args=(50,))
    assert test_object.data == 2

    # verify calling emit() from another thread schedules the callback
    thread.start()
    thread.join()

    # we haven't processed events, so it should still be 2
    assert test_object.data == 2

    # when we process events, the callback should run
    process_events()
    assert test_object.data == 50


def test_disconnect():
    signal = Signal[int]()

    def temp_func(x: int):
        pass

    # callbacks
    callback_id = signal.connect(temp_func)
    assert len(signal.callbacks.get()) == 1
    signal.disconnect(callback_id)
    assert len(signal.callbacks.get()) == 0
    # methods
    test_object = DummyObject(2)
    method_id = signal.connect(test_object.method)
    assert len(signal.methods.get()) == 1
    signal.disconnect(method_id)
    assert len(signal.methods.get()) == 0


def test_callbacks() -> None:
    signal = Signal[int, float, str]()

    test_object = DummyObject(4)

    def temp_func(x: int, y: float, z: str):
        test_object.set_data(x)

    # verify regular functions work
    callback_id = signal.connect(temp_func)
    assert signal.callbacks.get()[callback_id][0] == temp_func
    # verify that calling `emit()` causes the callback to run
    assert test_object.data == 4
    signal.emit(2, 3.0, "")
    assert test_object.data == 2


def test_methods():
    signal = Signal[int]()
    test_object = DummyObject(23489)

    # verify methods work
    method_id = signal.connect(test_object.method)
    assert signal.methods.get()[method_id][0]() == test_object.method
    # verify that deleting an object causes it's method to get removed from the signal
    del test_object
    signal.emit(5)
    assert len(signal.methods.get()) == 0


def test_connection_type():
    direct_signal = Signal[int]()
    queued_signal = Signal[int]()
    auto_signal_same_thread = Signal[int]()
    auto_signal_different_thread = Signal[int]()

    test_object = DummyObject(11)

    # direct connection; the callback should run immediately
    direct_signal.connect(test_object.set_data, ConnectionType.Direct)
    direct_signal.emit(50)
    assert test_object.data == 50
    test_object.data = 11  # reset

    # queued connection; the callback should be queued
    queued_signal.connect(test_object.set_data, ConnectionType.Queued)
    queued_signal.emit(40)
    assert test_object.data == 11  # should not have changed yet
    process_events()
    assert test_object.data == 40  # now it should have changed
    test_object.data = 11  # reset

    # auto connection: same thread; the callback should run immediately
    auto_signal_same_thread.connect(test_object.set_data)
    auto_signal_same_thread.emit(60)
    assert test_object.data == 60
    test_object.data = 11  # reset

    # auto connection: different thread; the callback should be queued
    auto_signal_different_thread.connect(test_object.set_data)
    thread = Thread(target=auto_signal_different_thread.emit, args=(20,))
    thread.start()
    thread.join()
    assert test_object.data == 11  # should not have changed yet
    process_events()
    assert test_object.data == 20  # now it should have changed


def test_remove_on_thread_death():
    signal = Signal()

    thread = Thread(target=signal.connect, args=(lambda: None,))
    thread.start()
    thread.join()
    del thread  # simulate the thread being garbage collected

    assert len(signal.callbacks.get()) == 1
    signal.emit(5)
    # the thread was destroyed, so calling `emit()` should have removed the connection
    assert len(signal.callbacks.get()) == 0
