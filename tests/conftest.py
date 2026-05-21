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

    class ConfigFlow:
        """Minimal ConfigFlow stub."""

        def __init_subclass__(cls, **kwargs):
            return super().__init_subclass__()

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_create_entry(self, *, title, data, options=None):
            return {"type": "create_entry", "title": title, "data": data, "options": options or {}}

        async def async_set_unique_id(self, unique_id):
            self._test_unique_id = unique_id

        def _abort_if_unique_id_configured(self):
            return None

    class OptionsFlow:
        """Minimal OptionsFlow stub."""

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_create_entry(self, *, title, data):
            return {"type": "create_entry", "title": title, "data": data}

    config_entries.ConfigFlow = ConfigFlow
    config_entries.OptionsFlow = OptionsFlow

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
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    selector = types.ModuleType("homeassistant.helpers.selector")
    storage = types.ModuleType("homeassistant.helpers.storage")
    typing_mod = types.ModuleType("homeassistant.helpers.typing")
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    sensor_mod = types.ModuleType("homeassistant.components.sensor")
    binary_sensor_mod = types.ModuleType("homeassistant.components.binary_sensor")
    event_mod = types.ModuleType("homeassistant.components.event")

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

    class CoordinatorEntity:
        """Minimal coordinator entity stub."""

        @classmethod
        def __class_getitem__(cls, _item):
            return cls

        def __init__(self, coordinator):
            self.coordinator = coordinator

        @property
        def available(self):
            return True

        async def async_added_to_hass(self):
            return None

        async def async_will_remove_from_hass(self):
            return None

    class UpdateFailed(Exception):
        """Minimal update exception stub."""

    class DeviceEntryType:
        SERVICE = "service"

    class DeviceInfo(dict):
        """Minimal DeviceInfo stub."""

    class _EntityRegistry:
        def __init__(self):
            self.entities = {}

        def async_remove(self, entity_id):
            self.entities.pop(entity_id, None)

    class _SelectorBase:
        def __init__(self, config=None):
            self.config = config

        def __call__(self, value):
            return value

        def __voluptuous_compile__(self, _schema):
            def validate(_path, value):
                return value

            return validate

    class TextSelector(_SelectorBase):
        pass

    class TextSelectorConfig:
        def __init__(self, *, type=None):
            self.type = type

    class TextSelectorType:
        PASSWORD = "password"

    class BooleanSelector(_SelectorBase):
        pass

    class NumberSelector(_SelectorBase):
        pass

    class NumberSelectorConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class SelectSelector(_SelectorBase):
        pass

    class SelectSelectorConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class SelectSelectorMode:
        DROPDOWN = "dropdown"

    class SensorEntity:
        @property
        def name(self):
            return getattr(self, "_attr_name", None)

        def async_write_ha_state(self):
            return None

    class BinarySensorEntity:
        @property
        def name(self):
            return getattr(self, "_attr_name", None)

        def async_write_ha_state(self):
            return None

    class EventEntity:
        def __init__(self):
            self._last_event = None

        @property
        def name(self):
            return getattr(self, "_attr_name", None)

        async def async_added_to_hass(self):
            return None

        async def async_will_remove_from_hass(self):
            return None

        def _trigger_event(self, event_type, payload=None):
            self._last_event = (event_type, payload)

        def async_write_ha_state(self):
            return None

    entity_platform.AddConfigEntryEntitiesCallback = object
    typing_mod.StateType = object

    aiohttp_client.async_get_clientsession = async_get_clientsession
    device_registry.DeviceEntryType = DeviceEntryType
    device_registry.DeviceInfo = DeviceInfo
    entity_registry.async_get = lambda _hass: _EntityRegistry()
    selector.BooleanSelector = BooleanSelector
    selector.NumberSelector = NumberSelector
    selector.NumberSelectorConfig = NumberSelectorConfig
    selector.SelectSelector = SelectSelector
    selector.SelectSelectorConfig = SelectSelectorConfig
    selector.SelectSelectorMode = SelectSelectorMode
    selector.TextSelector = TextSelector
    selector.TextSelectorConfig = TextSelectorConfig
    selector.TextSelectorType = TextSelectorType
    storage.Store = Store
    update_coordinator.CoordinatorEntity = CoordinatorEntity
    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.UpdateFailed = UpdateFailed
    sensor_mod.SensorEntity = SensorEntity
    binary_sensor_mod.BinarySensorEntity = BinarySensorEntity
    event_mod.EventEntity = EventEntity

    homeassistant.config_entries = config_entries
    homeassistant.components = types.ModuleType("homeassistant.components")
    homeassistant.core = core
    homeassistant.exceptions = exceptions
    homeassistant.const = const
    homeassistant.helpers = helpers

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.components"] = homeassistant.components
    sys.modules["homeassistant.components.sensor"] = sensor_mod
    sys.modules["homeassistant.components.binary_sensor"] = binary_sensor_mod
    sys.modules["homeassistant.components.event"] = event_mod
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.exceptions"] = exceptions
    sys.modules["homeassistant.const"] = const
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
    sys.modules["homeassistant.helpers.device_registry"] = device_registry
    sys.modules["homeassistant.helpers.entity_registry"] = entity_registry
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform
    sys.modules["homeassistant.helpers.selector"] = selector
    sys.modules["homeassistant.helpers.storage"] = storage
    sys.modules["homeassistant.helpers.typing"] = typing_mod
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator


_install_homeassistant_stubs()
