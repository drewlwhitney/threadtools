from threading import RLock


class DataLock[DataType]:
    """Thread-safe data container with context manager support."""

    def __init__(self, data: DataType):
        # do not access these manually from outside the class
        self.data = data
        self.lock = RLock()

    def set(self, value: DataType):
        """Set the contained data to `value`."""
        with self.lock:
            self.data = value

    def get(self) -> DataType:
        """
        Get the contained data. The value returned by this function should not be used to mutate the
        inner data; that is not thread-safe.
        """
        with self.lock:
            return self.data

    # context manager stuff
    def __enter__(self) -> DataType:
        self.lock.acquire()
        return self.data

    def __exit__(self, *args):  # exceptions probably don't matter here (right?)
        self.lock.release()
