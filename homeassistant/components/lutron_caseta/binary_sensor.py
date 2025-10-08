"""Support for Lutron Caseta Occupancy/Vacancy Sensors and Button LEDs."""

from __future__ import annotations

import logging
from typing import Any

from typing import Any

from pylutron_caseta import OCCUPANCY_GROUP_OCCUPIED

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import ATTR_SUGGESTED_AREA
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN
from .const import CONFIG_URL, MANUFACTURER, UNASSIGNED_AREA
from .device_trigger import LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP
from .entity import LutronCasetaEntity
from .models import LutronCasetaConfigEntry, LutronCasetaData
from .util import area_name_from_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LutronCasetaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron Caseta binary_sensor platform.

    Adds occupancy groups from the Caseta bridge associated with the
    config_entry as binary_sensor entities.
    """
    data = config_entry.runtime_data
    bridge = data.bridge
    occupancy_groups = bridge.occupancy_groups
    async_add_entities(
        LutronOccupancySensor(occupancy_group, data)
        for occupancy_group in occupancy_groups.values()
    )

    button_devices = bridge.get_buttons()
    all_devices = data.bridge.get_devices()
    keypads = data.keypad_data.keypads
    entities: list[LutronButtonLEDSensor] = []

    for button in button_devices.values():
        button_led = button["button_led"]
        if button_led is None:
            continue
        device = all_devices[button_led]
        parent_keypad = keypads[device["parent_device"]]
        parent_device_info = parent_keypad["device_info"]

        enabled_default = False
        if not (device_name := device.get("device_name")):
            # device name (button name) is missing, probably a caseta pico
            # try to get the name using the button number from the triggers
            # disable the button by default
            enabled_default = False
            keypad_device = all_devices[device["parent_device"]]
            button_numbers = LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP.get(
                keypad_device["type"],
                {},
            )
            device_name = (
                button_numbers.get(
                    int(device["button_number"]),
                    f"button {device['button_number']} led",
                )
                .replace("_", " ")
                .title()
            )

        # Append the child device name to the end of the parent keypad
        # name to create the entity name
        full_name = f"{parent_device_info.get('name')} {device_name} Status"
        # Set the device_info to the same as the Parent Keypad
        # The entities will be nested inside the keypad device
        entities.append(
            LutronButtonLEDSensor(
                device, data, full_name, enabled_default, parent_device_info
            ),
        )

    async_add_entities(entities)


class LutronOccupancySensor(LutronCasetaEntity, BinarySensorEntity):
    """Representation of a Lutron occupancy group."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, device, data):
        """Init an occupancy sensor."""
        super().__init__(device, data)
        area = area_name_from_id(self._smartbridge.areas, device["area"])
        name = f"{area} {device['device_name']}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer=MANUFACTURER,
            model="Lutron Occupancy",
            name=self.name,
            via_device=(DOMAIN, self._bridge_device["serial"]),
            configuration_url=CONFIG_URL,
            entry_type=DeviceEntryType.SERVICE,
        )
        if area != UNASSIGNED_AREA:
            self._attr_device_info[ATTR_SUGGESTED_AREA] = area

    @property
    def is_on(self) -> bool:
        """Return the brightness of the light."""
        return self._device["status"] == OCCUPANCY_GROUP_OCCUPIED

    # pylint: disable-next=hass-missing-super-call
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._smartbridge.add_occupancy_subscriber(
            self.device_id, self.async_write_ha_state
        )

    @property
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["occupancy_group_id"]

    @property
    def unique_id(self):
        """Return a unique identifier."""
        return f"occupancygroup_{self._bridge_unique_id}_{self.device_id}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {"device_id": self.device_id}


class LutronButtonLEDSensor(LutronCasetaEntity, BinarySensorEntity):
    """Representation of a Lutron Button LED."""

    def __init__(
        self,
        device: dict[str, Any],
        data: LutronCasetaData,
        full_name: str,
        enabled_default: bool,
        device_info: DeviceInfo,
    ) -> None:
        """Init a button entity."""
        super().__init__(device, data)
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_name = full_name
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool:
        """Return LED on/off."""
        return self._device["current_state"] == 100

    @property
    def serial(self):
        """Buttons shouldn't have serial numbers, Return None."""
        return None

    # pylint: disable-next=hass-missing-super-call
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await self._smartbridge.async_add_subscriber(
            self.device_id, self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Remove callback."""
        self._smartbridge.del_subscriber(self.device_id)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attr = super().extra_state_attributes
        attr["button_device_id"] = self._device["button_id"]
        return attr
