import inspect
import threading
import uuid
from threading import Thread
from typing import Any, Callable, Generic, ParamSpec
from weakref import WeakMethod

from .lock import DataLock
from .receiver import SignalReceiver

# variable arguments, takes no arguments by default
CallbackArguments = ParamSpec("CallbackArguments", default=[])


class Signal(Generic[CallbackArguments]):  # generic class based on the callback inputs
    """A signal that can be emitted to run or schedule a callback. Signals are thread-safe."""

    def __init__(self) -> None:
        # regular functions
        self.callbacks: DataLock[
            dict[int, tuple[Callable[CallbackArguments, Any], SignalReceiver]]
        ] = DataLock({})
        # class/instance methods
        self.methods: DataLock[
            dict[int, tuple[WeakMethod[Callable[CallbackArguments, Any]], SignalReceiver]]
        ] = DataLock({})

    def emit(self, *args: CallbackArguments.args, **kwargs: CallbackArguments.kwargs):
        """
        Emit the signal to all receivers. If the current thread and the receiver's thread are the
        same, the callback is run immediately.
        """
        current_thread = threading.current_thread()
        self.process_callbacks(current_thread, *args, **kwargs)
        self.process_methods(current_thread, *args, **kwargs)

    def process_callbacks(
        self,
        current_thread: Thread,
        *args: CallbackArguments.args,
        **kwargs: CallbackArguments.kwargs,
    ):
        """(protected) Called by `emit()` to process callbacks."""
        with self.callbacks as callbacks:
            for callback, receiver in callbacks.values():
                self.run_or_post_callback(callback, receiver, current_thread, *args, **kwargs)

    def process_methods(
        self,
        current_thread: Thread,
        *args: CallbackArguments.args,
        **kwargs: CallbackArguments.kwargs,
    ):
        """(protected) Called by `emit()` to process methods."""
        ids_to_remove: list[int] = []

        with self.methods as methods:
            for method_id, (method_ref, receiver) in methods.items():
                method = method_ref()
                # if the method hasn't been deleted
                if method is not None:
                    self.run_or_post_callback(method, receiver, current_thread, *args, **kwargs)
                else:
                    # the method has been deleted, remove it's entry
                    ids_to_remove.append(method_id)
            # remove any deleted methods
            for method_id in ids_to_remove:
                methods.pop(method_id)

    def run_or_post_callback(
        self,
        callback: Callable[CallbackArguments, Any],
        receiver: SignalReceiver,
        current_thread: Thread,
        *args: CallbackArguments.args,
        **kwargs: CallbackArguments.kwargs,
    ):
        """Run or post a callback, depending on the current and receiver thread."""

        # this is a wrapper for the outer callback so that the function posted on the
        # signal queue takes no arguments and returns nothing
        def inner():
            callback(*args, **kwargs)

        # if the current thread is the same as the receiving thread, it is safe to
        # immediately process the callback
        with receiver.get_thread_lock() as receiver_thread:
            if current_thread is receiver_thread:
                inner()
            else:
                # this actually posts the callback to the callback queue
                receiver.post_callback(inner)

    def connect(self, receiver: SignalReceiver, callback: Callable[CallbackArguments, Any]) -> int:
        """
        Calling `emit()` on this signal will cause `callback` to be posted on `receiver`'s callback
        queue.
        # Returns
        - A unique `int` that can be used with `disconnect()`.
        """
        callback_id = uuid.uuid4().int  # random, unique number
        # add the callback or method to the collection so they get processed by `emit()`
        if inspect.ismethod(callback):  # if it's a class method
            method_ref: WeakMethod[Callable[CallbackArguments, Any]] = WeakMethod(callback)
            with self.methods as methods:
                methods[callback_id] = (method_ref, receiver)
        else:  # it's just a normal function/lambda/partial, we don't need a weakref
            with self.callbacks as callbacks:
                callbacks[callback_id] = (callback, receiver)
        return callback_id

    def disconnect(self, callback_id: int):
        """
        Disconnect a previously connected callback using it's `callback_id`, as returned by
        `connect()`.
        """
        try:
            with self.methods as methods:  # first try to remove from the methods dict
                methods.pop(callback_id)
        except KeyError:
            # if we get here it was probably already removed because the callback was garbage
            # collected
            with self.callbacks as callbacks:  # now try the callbacks dict
                callbacks.pop(callback_id)
            # if an error is thrown now, it's a user mistake
