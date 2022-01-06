"""Support for Lutron HVAC devices."""
import logging

from pylutron import HVAC

from homeassistant.const import (
    ATTR_TEMPERATURE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT
)

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_DRY,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    FAN_AUTO,
    FAN_ON,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE
)

from . import LUTRON_CONTROLLER, LUTRON_DEVICES, LutronDevice

_LOGGER = logging.getLogger(__name__)

OP_MODE_L2H_CFG = {
    "Heat": HVAC_MODE_HEAT,
    "Cool": HVAC_MODE_COOL,
    "Auto": HVAC_MODE_HEAT_COOL,
}

FAN_MODE_L2H_CFG = {
    "Auto": FAN_AUTO,
    "On": FAN_ON
}

OP_MODE_L2H = {
    HVAC.MODE_OFF: HVAC_MODE_OFF,
    HVAC.MODE_HEAT: HVAC_MODE_HEAT,
    HVAC.MODE_COOL: HVAC_MODE_COOL,
    HVAC.MODE_AUTO: HVAC_MODE_HEAT_COOL,
    HVAC.MODE_FAN: HVAC_MODE_FAN_ONLY,
    HVAC.MODE_DRY: HVAC_MODE_DRY
}

OP_MODE_H2L = {
    HVAC_MODE_OFF: HVAC.MODE_OFF,
    HVAC_MODE_HEAT: HVAC.MODE_HEAT,
    HVAC_MODE_COOL: HVAC.MODE_COOL,
    HVAC_MODE_HEAT_COOL: HVAC.MODE_AUTO,
    HVAC_MODE_FAN_ONLY: HVAC.MODE_FAN,
    HVAC_MODE_DRY: HVAC.MODE_DRY
}

FAN_MODE_L2H = {
    HVAC.FAN_AUTO: FAN_AUTO,
    HVAC.FAN_ON: FAN_ON,
    HVAC.FAN_NONE: FAN_OFF,
    HVAC.FAN_HIGH: FAN_HIGH,
    HVAC.FAN_MEDIUM: FAN_MEDIUM,
    HVAC.FAN_LOW: FAN_LOW
}

FAN_MODE_H2L = {
    FAN_AUTO: HVAC.FAN_AUTO,
    FAN_ON: HVAC.FAN_ON,
    FAN_HIGH: HVAC.FAN_HIGH,
    FAN_MEDIUM: HVAC.FAN_MEDIUM,
    FAN_LOW: HVAC.FAN_LOW
}

STATUS_L2H = {
    HVAC.STATUS_HEAT_1: CURRENT_HVAC_HEAT,
    HVAC.STATUS_HEAT_1_2: CURRENT_HVAC_HEAT,
    HVAC.STATUS_HEAT_1_2_3: CURRENT_HVAC_HEAT,
    HVAC.STATUS_HEAT_3: CURRENT_HVAC_HEAT,
    HVAC.STATUS_COOL_IDLE: CURRENT_HVAC_IDLE,
    HVAC.STATUS_COOL_1: CURRENT_HVAC_COOL,
    HVAC.STATUS_COOL_1_2: CURRENT_HVAC_COOL,
    HVAC.STATUS_OFF: CURRENT_HVAC_OFF,
    HVAC.STATUS_EM_HEAT: CURRENT_HVAC_HEAT,
    HVAC.STATUS_DRY: CURRENT_HVAC_DRY
}

def setup_platform(hass, config, add_entities, discovery_info=None):
    temp_unit = hass.config.units.temperature_unit
    hvacs = []
    for (name, hvac) in hass.data[LUTRON_DEVICES]["climate"]:
        hvacs.append(LutronClimate(name, hvac, hass.data[LUTRON_CONTROLLER], temp_unit))

    add_entities(hvacs, True)

class LutronClimate(LutronDevice, ClimateEntity):
    def __init__(self, name, lutron_device, controller, temp_unit):
        super().__init__("", lutron_device, controller)
	
        self._attr_hvac_modes = []
        for l_mode in self._lutron_device.op_modes:
            if l_mode in OP_MODE_L2H_CFG:
                self._attr_hvac_modes.append(OP_MODE_L2H_CFG[l_mode])
        
        self._attr_fan_modes = []
        for l_mode in self._lutron_device.fan_modes:
            if l_mode in FAN_MODE_L2H_CFG:
                self._attr_fan_modes.append(FAN_MODE_L2H_CFG[l_mode])
        self._attr_supported_features = 0
        if len(self._attr_fan_modes) > 0:
            self._attr_supported_features |= SUPPORT_FAN_MODE

        self._attr_temperature_unit = temp_unit
        if temp_unit == TEMP_CELSIUS:
            self._lutron_device.temp_unit = HVAC.TEMP_UNIT_C
        elif temp_unit == TEMP_FAHRENHEIT:
            self._lutron_device.temp_unit = HVAC.TEMP_UNIT_F
        self.update()

    def set_hvac_mode(self, hvac_mode):
        self._lutron_device.op_mode = OP_MODE_H2L[hvac_mode]

    def set_fan_mode(self, fan_mode):
        self._lutron_device.fan_mode = FAN_MODE_H2L[fan_mode]

    def set_temperature(self, **kwargs) -> None:
        if temp := kwargs.get(ATTR_TEMPERATURE):
            mode = self._lutron_device.last_op_mode
            if mode == HVAC.MODE_HEAT or mode == HVAC.MODE_AUTO:
              self._lutron_device.heat_setpoint = temp
            elif mode == HVAC.MODE_COOL:
              self._lutron_device.cool_setpoint = temp
        else:
          if low_temp := kwargs.get(ATTR_TARGET_TEMP_LOW):
              self._lutron_device.heat_setpoint = low_temp
          if high_temp := kwargs.get(ATTR_TARGET_TEMP_HIGH):
              self._lutron_device.cool_setpoint = high_temp

    @property
    def current_temperature(self):
      self._attr_current_temperature = self._lutron_device.last_current_temp
      return self._attr_current_temperature

    @property
    def hvac_mode(self):
        mode = self._lutron_device.last_op_mode
        if mode in OP_MODE_L2H:
            self._attr_hvac_mode = OP_MODE_L2H[mode]
            self._attr_supported_features &= ~(SUPPORT_TARGET_TEMPERATURE_RANGE|SUPPORT_TARGET_TEMPERATURE)
            if self._attr_hvac_mode == HVAC_MODE_HEAT_COOL:
                self._attr_supported_features = SUPPORT_TARGET_TEMPERATURE_RANGE
            else:
                self._attr_supported_features = SUPPORT_TARGET_TEMPERATURE
            return self._attr_hvac_mode
        else:
            return None

    @property
    def target_temperature(self):
        if self._attr_hvac_mode == HVAC_MODE_HEAT:
            self._attr_target_temperature = self._lutron_device.last_heat_setpoint
        elif mode == HVAC.MODE_COOL:
            self._attr_target_temperature = self._lutron_device.last_cool_setpoint
        else:
            self._attr_target_temperature = None
        return self._attr_target_temperature

    @property
    def target_temperature_high(self):
        self._attr_target_temperature_high = self._lutron_device.last_cool_setpoint
        return self._attr_target_temperature_high

    @property
    def target_temperature_low(self):
        self._attr_target_temperature_low = self._lutron_device.last_heat_setpoint
        return self._attr_target_temperature_low

    @property
    def fan_mode(self):
        fan_mode = self._lutron_device.last_fan_mode
        if fan_mode in FAN_MODE_L2H:
            self._attr_fan_mode = FAN_MODE_L2H[fan_mode]
        else:
            self._attr_fan_mode = None
        return self._attr_fan_mode

    @property
    def hvac_action(self):
        status = self._lutron_device.last_status
        if status in STATUS_L2H:
            self._attr_hvac_action = STATUS_L2H[status]
        else:
            self._attr_hvac_action = None
        return self._attr_hvac_action

    def update(self):
        _attr_current_temperature = self._lutron_device.current_temp
        m = self._lutron_device.op_mode
        m = self.hvac_mode
        _attr_target_temperature_high = self._lutron_device.cool_setpoint
        t = self.target_temperature
        tl = self.target_temperature_low
        fm = self._lutron_device.fan_mode
        fm = self.fan_mode
        s = self._lutron_device.status
        s = self.hvac_action

