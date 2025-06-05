from src.threadtools import SignalReceiver


class DummyReceiver(SignalReceiver):
    def __init__(self, data: int):
        super().__init__()
        self.data = data
