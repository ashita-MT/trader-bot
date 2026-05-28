import os
import importlib
import sys
from typing import List
from .base import BasePlugin


class PluginLoader:
    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins_dir = plugins_dir
        self.plugins: List[BasePlugin] = []

    async def load_all(self, bot):
        if not os.path.isdir(self.plugins_dir):
            print(f"[PluginLoader] 插件目录不存在: {self.plugins_dir}")
            return

        sys.path.insert(0, os.getcwd())

        for name in os.listdir(self.plugins_dir):
            plugin_path = os.path.join(self.plugins_dir, name, "plugin.py")
            if not os.path.isfile(plugin_path):
                continue

            try:
                module_name = f"{self.plugins_dir.replace('/', '.').replace(chr(92), '.')}.{name}.plugin"
                module = importlib.import_module(module_name)
                plugin_class = getattr(module, "Plugin")
                plugin = plugin_class()
                await plugin.setup(bot)
                self.plugins.append(plugin)
                print(f"[PluginLoader] 已加载插件: {plugin.name} v{plugin.version}")
            except Exception as e:
                print(f"[PluginLoader] 加载插件 {name} 失败: {e}")

    async def unload_all(self):
        for plugin in self.plugins:
            try:
                await plugin.teardown()
            except Exception as e:
                print(f"[PluginLoader] 卸载插件 {plugin.name} 失败: {e}")
        self.plugins.clear()

    def get_all_commands(self) -> dict:
        commands = {}
        for plugin in self.plugins:
            for cmd, handler in plugin.get_commands().items():
                commands[cmd] = handler
        return commands
