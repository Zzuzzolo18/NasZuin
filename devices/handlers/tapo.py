import asyncio
import logging
from . import DeviceHandler

logger = logging.getLogger('devices')


class TapoHandler(DeviceHandler):
    def __init__(self, ip_address, config):
        super().__init__(ip_address, config)
        self.username = config.get('username', '')
        self.password = config.get('password', '')

    def _get_device(self):
        """Creates and returns a connected Tapo device client (async internal)."""
        async def _connect():
            from tapo import ApiClient
            client = ApiClient(self.username, self.password)
            return await client.p110(self.ip_address)
        return asyncio.run(_connect())

    def turn_on(self):
        async def _action():
            from tapo import ApiClient
            client = ApiClient(self.username, self.password)
            device = await client.p110(self.ip_address)
            await device.on()
        asyncio.run(_action())
        logger.info(f"Tapo device at {self.ip_address} turned ON")

    def turn_off(self):
        async def _action():
            from tapo import ApiClient
            client = ApiClient(self.username, self.password)
            device = await client.p110(self.ip_address)
            await device.off()
        asyncio.run(_action())
        logger.info(f"Tapo device at {self.ip_address} turned OFF")

    def get_status(self):
        async def _action():
            from tapo import ApiClient
            client = ApiClient(self.username, self.password)
            device = await client.p110(self.ip_address)
            info = await device.get_device_info()
            return info.to_dict()
        try:
            result = asyncio.run(_action())
            logger.info(f"Tapo device at {self.ip_address} status retrieved")
            return {"online": True, "info": result}
        except Exception as e:
            logger.warning(f"Tapo device at {self.ip_address} unreachable: {e}")
            return {"online": False, "error": str(e)}
