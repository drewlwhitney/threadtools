from enum import Enum, auto


class ConnectionType(Enum):
    Auto = auto()
    """The connection type is determined when `emit()` is called."""
    Direct = auto()
    """The callback is run immediately (by the calling thread) when `emit()` is called."""
    Queued = auto()
    """The callback is run when the receiver thread calls `process_events()`."""
