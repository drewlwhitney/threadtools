import inspect
import threading
import uuid
from queue import Queue
from threading import Thread
from typing import Any, Callable, Generic, ParamSpec
from weakref import WeakMethod, ref as WeakRef

from .connection import ConnectionType
from .globals import CALLBACK_QUEUES
from .lock import DataLock

# variable arguments, takes no arguments by default
CallbackArguments = ParamSpec("CallbackArguments", default=[])


class Signal(Generic[CallbackArguments]):  # generic class based on the callback inputs
    """A signal that can be emitted to run or schedule a callback. Signals are thread-safe."""

    def __init__(self) -> None:
        # regular functions
        self.callbacks: DataLock[
            dict[
                int,
                tuple[
                    Callable[CallbackArguments, Any],
                    WeakRef[Thread],
                    Queue[Callable[[], None]],
                    ConnectionType,
                ],
            ]
        ] = DataLock({})
        # class/instance methods
        self.methods: DataLock[
            dict[
                int,
                tuple[
                    WeakMethod[Callable[CallbackArguments, Any]],
                    WeakRef[Thread],
                    Queue[Callable[[], None]],
                    ConnectionType,
                ],
            ]
        ] = DataLock({})

    def emit(self, *args: CallbackArguments.args, **kwargs: CallbackArguments.kwargs):
        """Emit the signal to all receivers."""
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
        ids_to_remove: list[int] = []

        with self.callbacks as callbacks:
            for callback_id, (
                callback,
                receiver_thread_ref,
                callback_queue,
                connection_type,
            ) in callbacks.items():
                # run or post the callback
                if not self.run_or_post_callback(
                    current_thread,
                    callback,
                    receiver_thread_ref,
                    callback_queue,
                    connection_type,
                    *args,
                    **kwargs,
                ):
                    # if the connection is invalid remove it
                    ids_to_remove.append(callback_id)
            # remove any invalid callbacks
            for callback_id in ids_to_remove:
                callbacks.pop(callback_id)

    def process_methods(
        self,
        current_thread: Thread,
        *args: CallbackArguments.args,
        **kwargs: CallbackArguments.kwargs,
    ):
        """(protected) Called by `emit()` to process methods."""
        ids_to_remove: list[int] = []

        with self.methods as methods:
            for method_id, (
                method_ref,
                receiver_thread_ref,
                callback_queue,
                connection_type,
            ) in methods.items():
                method = method_ref()
                if method is not None:  # if the method hasn't been deleted
                    if not self.run_or_post_callback(
                        current_thread,
                        method,
                        receiver_thread_ref,
                        callback_queue,
                        connection_type,
                        *args,
                        **kwargs,
                    ):
                        # if the connection is invalid remove it
                        ids_to_remove.append(method_id)
                else:
                    # the method's owner has been deleted, remove it's entry
                    ids_to_remove.append(method_id)
            # remove any invalid methods
            for method_id in ids_to_remove:
                methods.pop(method_id)

    def run_or_post_callback(
        self,
        current_thread: Thread,
        callback: Callable[CallbackArguments, Any],
        receiver_thread_ref: WeakRef[Thread],
        callback_queue: Queue[Callable[[], None]],
        connection_type: ConnectionType,
        *callback_args: CallbackArguments.args,
        **callback_kwargs: CallbackArguments.kwargs,
    ) -> bool:
        """
        Run or post a callback, depending on the current and receiver thread.
        # Returns
        Whether the provided callback is still valid. Invalid callbacks should be removed.
        """
        # if the receiver thread has died, don't run the callback
        receiver_thread = receiver_thread_ref()
        if receiver_thread is None:
            return False

        # this is a wrapper for the outer callback so that the function posted on the
        # signal queue takes no arguments and returns nothing
        def inner():
            # callbacks should not fail
            # if the callback fails it is not the signal's problem and is silently ignored
            try:
                callback(*callback_args, **callback_kwargs)
            except Exception:
                pass

        # determine how to run the callback based on the connection type
        if connection_type == ConnectionType.Auto:
            if current_thread is receiver_thread:
                # the current thread is the same as the receiver; call immediately
                connection_type = ConnectionType.Direct
            else:
                connection_type = ConnectionType.Queued

        match connection_type:
            case ConnectionType.Direct:  # run immediately
                inner()
            case ConnectionType.Queued:  # queue
                callback_queue.put(inner)

        return True

    def connect(
        self,
        callback: Callable[CallbackArguments, Any],
        connection_type: ConnectionType = ConnectionType.Auto,
    ) -> int:
        """
        Calling `emit()` on this signal will cause `callback` to run.
        # Parameters
        - `callback` - The callback to run when the signal is emitted.
        - `connection_type` - How the callback should be run. If `Auto` is used, the connection type
        will be determined automatically when `emit()` is called. If you are unsure which connection
        type to use, use `Auto`.
        # Returns
        - A unique `int` that can be used with `disconnect()`.
        # Notes
        - The thread calling `connect()` is used as the "receiver thread". This means you should
        only connect signals from the thread the `callback` can be safely run from. If you need to
        connect signals from the "wrong thread", you should use `Queued` for the connection type.
        """
        callback_id = uuid.uuid4().int  # random, unique number
        receiver_thread = threading.current_thread()
        receiver_thread_ref = WeakRef(receiver_thread)
        queue = CALLBACK_QUEUES.get_callback_queue(receiver_thread)
        # add the callback or method to the collection so they get processed by `emit()`
        if inspect.ismethod(callback):  # if it's a class method
            method_ref: WeakMethod[Callable[CallbackArguments, Any]] = WeakMethod(callback)
            with self.methods as methods:
                methods[callback_id] = (method_ref, receiver_thread_ref, queue, connection_type)
        else:  # it's just a normal function/lambda/partial, we don't need a weakref on the callback
            with self.callbacks as callbacks:
                callbacks[callback_id] = (callback, receiver_thread_ref, queue, connection_type)
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
            # if we get here it was probably already removed because the method was garbage
            # collected
            with self.callbacks as callbacks:  # now try the callbacks dict
                callbacks.pop(callback_id)
            # if an error is thrown now, it's a user mistake
