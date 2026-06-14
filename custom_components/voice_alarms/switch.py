"""Switch entity platform mapping for the custom alarm entries."""
import logging
from homeassistant.components.switch import SwitchEntity # pyright: ignore[reportMissingImports]
from homeassistant.config_entries import ConfigEntry  # pyright: ignore[reportMissingImports]  
from homeassistant.core import HomeAssistant  # pyright: ignore[reportMissingImports]  
from homeassistant.helpers.entity import DeviceInfo    # pyright: ignore[reportMissingImports]
from homeassistant.helpers.entity_platform import AddEntitiesCallback # pyright: ignore[reportMissingImports] # pyright: ignore[reportMissingImports]
from homeassistant.helpers import entity_registry as er # pyright: ignore[reportMissingImports]
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the individual switch entities via the config entry."""
    hass.data[DOMAIN]["add_entities_callback"] = async_add_entities
    
    db = hass.data[DOMAIN]["alarms"]
    entities_to_build = []
    
    for idx in db.keys():
        if idx not in hass.data[DOMAIN]["switches"]:
            sw = AlarmAppSwitchEntity(hass, idx)
            hass.data[DOMAIN]["switches"][idx] = sw
            entities_to_build.append(sw)
            
    if entities_to_build:
        async_add_entities(entities_to_build, True)
    
    list_sensor = hass.data[DOMAIN].get("list_sensor")
    if list_sensor:
        await list_sensor.async_update_state()

async def async_register_new_switch(hass: HomeAssistant, idx: str):
    """Helper to dynamically register a new switch entity."""
    add_entities = hass.data.get(DOMAIN, {}).get("add_entities_callback")
    
    if not add_entities:
        _LOGGER.warning("Switch platform not fully initialized yet. Cannot register switch %s immediately.", idx)
        return

    new_sw = AlarmAppSwitchEntity(hass, idx)
    hass.data[DOMAIN]["switches"][idx] = new_sw
    
    add_entities([new_sw])
    
    list_sensor = hass.data[DOMAIN].get("list_sensor")
    if list_sensor:
        await list_sensor.async_update_state()

class AlarmAppSwitchEntity(SwitchEntity):
    """Representation of an isolated configurable alarm entry allocation instance slot."""

    def __init__(self, hass: HomeAssistant, idx: str):
        self.hass = hass
        self._idx = idx
        # We rely on the name property below for the display name
        self.entity_id = f"switch.{idx}"
        self._attr_unique_id = f"voice_alarm_switch_registry_slot_{idx}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, "voice_alarm_core")},
            name="Alarm Application Workflow",
            manufacturer="Lone baggie",
            model="Voice Intent Engine",
        )

    @property
    def data_record(self) -> dict:
        if self._idx not in self.hass.data[DOMAIN]["alarms"]:
            self.hass.data[DOMAIN]["alarms"][self._idx] = {
                "alarm_id": str(int(self._idx)),
                "device_id": "",
                "name": "",
                "time": "00:00",
                "persistent": False,
                "reoccurring": "once",
                "ringing": False,
                "enabled": False
            }
        return self.hass.data[DOMAIN]["alarms"][self._idx]

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        record = self.data_record
        if record.get("name"):
            return str(record.get("name"))
        # Return just the ID (e.g., '01')
        return self._idx

    @property
    def is_on(self) -> bool:
        return self.data_record.get("enabled", False)

    @property
    def extra_state_attributes(self) -> dict:
        record = self.data_record
        return {
            "alarm_id": str(record.get("alarm_id", str(int(self._idx)))),
            "device_id": record.get("device_id", ""),
            "name": record.get("name", ""),
            "time": record.get("time"),
            "persistent": record.get("persistent"),
            "target_day": record.get("target_day", "none"),
            "reoccurring": record.get("reoccurring"),
            "ringing": record.get("ringing")
        }

    async def async_added_to_hass(self) -> None:
        """Run when entity is added."""
        await super().async_added_to_hass()
        # Removed the forced registry update so the UI can respect our dynamic name property

    async def async_turn_on(self, **kwargs) -> None:
        db = self.hass.data[DOMAIN]["alarms"]
        db[self._idx]["enabled"] = True
        db[self._idx]["ringing"] = False
        self.async_write_ha_state()
        list_sensor = self.hass.data[DOMAIN].get("list_sensor")
        if list_sensor:
            await list_sensor.async_update_state()

    async def async_turn_off(self, **kwargs) -> None:
        db = self.hass.data[DOMAIN]["alarms"]
        db[self._idx]["enabled"] = False
        db[self._idx]["ringing"] = False
        self.async_write_ha_state()
        list_sensor = self.hass.data[DOMAIN].get("list_sensor")
        if list_sensor:
            await list_sensor.async_update_state()

    async def async_remove(self, force_remove: bool = False) -> None:
        """Fully remove entity from HA registry and memory."""
        registry = er.async_get(self.hass)
        if registry.async_get(self.entity_id):
            registry.async_remove(self.entity_id)
        
        await super().async_remove(force_remove=force_remove)