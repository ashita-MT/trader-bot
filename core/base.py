from abc import ABC, abstractmethod
from typing import Dict, Callable


class BasePlugin(ABC):
    name: str = ""
    version: str = ""
    description: str = ""

    @abstractmethod
    async def setup(self, bot):
        pass

    @abstractmethod
    async def teardown(self):
        pass

    @abstractmethod
    def get_commands(self) -> Dict[str, Callable]:
        pass
