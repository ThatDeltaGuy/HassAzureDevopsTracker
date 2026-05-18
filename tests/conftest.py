"""Test shims for running local unit tests without Home Assistant installed."""

from __future__ import annotations

import sys
import types


def _install_homeassistant_stubs() -> None:
    if "homeassistant" in sys.modules:
        return

    homeassistant = types.ModuleType("homeassistant")

    config_entries = types.ModuleType("homeassistant.config_entries")

    class ConfigEntry:
        """Minimal ConfigEntry stub."""

        @classmethod
        def __class_getitem__(cls, _item):
            return cls

    config_entries.ConfigEntry = ConfigEntry

    core = types.ModuleType("homeassistant.core")

    class HomeAssistant:
        """Minimal HomeAssistant stub."""

    def callback(func):
        return func

    core.HomeAssistant = HomeAssistant
    core.callback = callback

    exceptions = types.ModuleType("homeassistant.exceptions")

    class ConfigEntryAuthFailed(Exception):
        """Minimal auth exception stub."""

    exceptions.ConfigEntryAuthFailed = ConfigEntryAuthFailed

    const = types.ModuleType("homeassistant.const")

    class Platform:
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"
        EVENT = "event"

    const.Platform = Platform

    helpers = types.ModuleType("homeassistant.helpers")
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    storage = types.ModuleType("homeassistant.helpers.storage")
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")

    def async_get_clientsession(_hass):
        return None

    class Store:
        """Minimal Store stub."""

        @classmethod
        def __class_getitem__(cls, _item):
            return cls

        def __init__(self, *_args, **_kwargs):
            pass

        async def async_load(self):
            return None

        async def async_save(self, _data):
            return None

    class DataUpdateCoordinator:
        """Minimal coordinator stub."""

        @classmethod
        def __class_getitem__(cls, _item):
            return cls

        def __init__(self, hass=None, logger=None, config_entry=None, name=None, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.config_entry = config_entry
            self.name = name
            self.update_interval = update_interval
            self._listeners = []

        def async_add_listener(self, listener):
            self._listeners.append(listener)

            def remove_listener():
                self._listeners.remove(listener)

            return remove_listener

    class UpdateFailed(Exception):
        """Minimal update exception stub."""

    aiohttp_client.async_get_clientsession = async_get_clientsession
    storage.Store = Store
    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.UpdateFailed = UpdateFailed

    homeassistant.config_entries = config_entries
    homeassistant.core = core
    homeassistant.exceptions = exceptions
    homeassistant.const = const
    homeassistant.helpers = helpers

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.exceptions"] = exceptions
    sys.modules["homeassistant.const"] = const
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
    sys.modules["homeassistant.helpers.storage"] = storage
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator


_install_homeassistant_stubs()
