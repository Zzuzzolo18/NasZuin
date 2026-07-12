from abc import ABC, abstractmethod


class DeviceHandler(ABC):
    def __init__(self, ip_address, config):
        self.ip_address = ip_address
        self.config = config

    @abstractmethod
    def turn_on(self):
        pass

    @abstractmethod
    def turn_off(self):
        pass

    @abstractmethod
    def get_status(self):
        """Returns dict with device info. Must not trigger power actions."""
        pass
