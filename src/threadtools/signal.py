import inspect
import threading
import uuid
from typing import Any, Callable, Generic, ParamSpec
from weakref import WeakMethod, ref

from .lock import DataLock
from .receiver import SignalReceiver

# variable arguments, takes no arguments by default
CallbackArguments = ParamSpec("CallbackArguments", default=[])


class Signal(Generic[CallbackArguments]):  # generic class based on the callback inputs
    """A signal that can be emitted to run or schedule a callback. Signals are thread-safe."""

    def __init__(self) -> None:
        self.callbacks: DataLock[
            dict[int, tuple[ref[Callable[CallbackArguments, Any]], SignalReceiver]]
        ] = DataLock({})

        self.methods: DataLock[
            dict[int, tuple[WeakMethod[Callable[CallbackArguments, Any]], SignalReceiver]]
        ] = DataLock({})

    def emit(self, *args: CallbackArguments.args, **kwargs: CallbackArguments.kwargs):
        """
        Emit the signal to all receivers. If the current thread and the receiver's thread are the
        same, the callback is run immediately.
        """
        for callback_dict_lock in (self.callbacks, self.methods):
            with callback_dict_lock as callback_dict:
                self.process_callbacks(callback_dict, *args, **kwargs)

    def process_callbacks(
        self,
        callback_dict: (
            dict[int, tuple[ref[Callable[CallbackArguments, Any]], SignalReceiver]]
            | dict[int, tuple[WeakMethod[Callable[CallbackArguments, Any]], SignalReceiver]]
        ),
        *args: CallbackArguments.args,
        **kwargs: CallbackArguments.kwargs,
    ):
        """(protected) Called by `emit()` to process callbacks."""
        current_thread = threading.current_thread()
        ids_to_remove: list[int] = []

        for callback_id, (callback_ref, receiver) in callback_dict.items():
            callback = callback_ref()
            # if the callback hasn't been deleted
            if callback is not None:
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
            else:
                # the callback has been deleted, remove it
                ids_to_remove.append(callback_id)
        # remove any deleted callbacks
        for callback_id in ids_to_remove:
            callback_dict.pop(callback_id)

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
        else:  # it's just a normal function
            callback_ref = ref(callback)
            with self.callbacks as callbacks:
                callbacks[callback_id] = (callback_ref, receiver)

        return callback_id

    def disconnect(self, callback_id: int):
        """
        Disconnect a previously connected callback using it's `callback_id`, as returned by
        `connect()`.
        """
        try:
            # first try to remove from the methods dict
            with self.methods as methods:
                methods.pop(callback_id)
        except KeyError:
            try:
                # then try the callbacks dict
                with self.callbacks as callbacks:
                    callbacks.pop(callback_id)
            except KeyError:
                # if we get here it was probably already removed because the callback was garbage
                # collected
                pass
