"""Binary sensor platform for the custom alarm master status."""
import logging
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the master alarm ringing binary sensor via Config Entry."""
    master_sensor = AlarmMasterBinarySensor(hass)
    hass.data[DOMAIN]["master_sensor"] = master_sensor
    async_add_entities([master_sensor], True)


class AlarmMasterBinarySensor(BinarySensorEntity):
    """Representation of the master alarm ringing status entity."""

    def __init__(self, hass):
        self.hass = hass
        self._attr_name = "Active Alarm"
        self.entity_id = "binary_sensor.active_alarm" 
        self._attr_unique_id = "voice_alarm_master_siren_registry_core"
        self._attr_device_class = BinarySensorDeviceClass.SOUND
        self._state = False
        self._attr_extra_state_attributes = {
            "device_id": "",
            "id": "",
            "name": "",
            "media_player": ""
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Link this master sensor entity directly to the parent integration card structure."""
        return DeviceInfo(
            identifiers={(DOMAIN, "voice_alarm_core")},
            name="Alarm Application Workflow",
            manufacturer="Lone baggie",
            model="Voice Engine List Matrix",
        )

    @property
    def is_on(self) -> bool:
        """Return True if an alarm is ringing."""
        return self._state

# Change 'def' to 'async def'
    async def async_update_state(self) -> None:
        """Logic to calculate if any alarm is ringing and update the sensor."""
        if DOMAIN not in self.hass.data:
            return

        db = self.hass.data[DOMAIN].get("alarms", {})
        switches = self.hass.data[DOMAIN].get("switches", {})
        
        ringing_alarm_idx = None
        for idx, alarm in db.items():
            if alarm.get("ringing", False):
                ringing_alarm_idx = idx
                break
        
        if ringing_alarm_idx:
            self._state = True
            target_alarm = db[ringing_alarm_idx]
            
            friendly_name = f"Alarm {int(ringing_alarm_idx)}"
            if ringing_alarm_idx in switches:
                friendly_name = switches[ringing_alarm_idx].name
            
            device_id = target_alarm.get("device_id", "")
            media_player_entity = ""
            
            if device_id:
                # IMPORTANT: You must 'await' this async call
                ent_reg = er.async_get(self.hass)
                entries = er.async_entries_for_device(ent_reg, device_id)
                for entry in entries:
                    if entry.domain == "media_player":
                        media_player_entity = entry.entity_id
                        break
            
            self._attr_extra_state_attributes = {
                "device_id": device_id,
                "id": int(ringing_alarm_idx),
                "name": friendly_name,
                "media_player": media_player_entity
            }
        else:
            self._state = False
            self._attr_extra_state_attributes = {
                "device_id": "",
                "id": "",
                "name": "",
                "media_player": ""
            }
            
        # IMPORTANT: Force Home Assistant to refresh the UI with these new attributes
        self.async_write_ha_state()