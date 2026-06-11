"""Sensor platform providing detailed list indexes for alarms."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the list tracking sensor via config entry."""
    list_sensor = AlarmListSensor(hass)
    hass.data[DOMAIN]["list_sensor"] = list_sensor
    async_add_entities([list_sensor], True)

class AlarmListSensor(SensorEntity):
    """Exposes structured listings of configured alarms."""
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "List Alarms"
        self.entity_id = "sensor.list_alarms"
        self._attr_unique_id = "voice_alarm_list_sensor_entity"
        self._state = 0
        self._attr_extra_state_attributes = {"alarms": []}

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, "voice_alarm_core")},
            name="Alarm Application Workflow",
            manufacturer="Lone baggie",
            model="Voice Engine List Matrix",
        )

    @property
    def native_value(self):
        return self._state

    def update_state(self) -> None:
        """
        Synchronous wrapper for backward compatibility.
        Schedules the async update on the event loop.
        """
        self.hass.create_task(self.async_update_state())

    async def async_update_state(self) -> None:
        """Triggered from intents to refresh the sensor safely."""
        # Process the data in an executor thread
        await self.hass.async_add_executor_job(self._process_data)
        # Update the state on the event loop
        self.async_write_ha_state()

    def _process_data(self) -> None:
        """Internal method to build the list of alarms."""
        db = self.hass.data[DOMAIN]["alarms"]
        switches = self.hass.data[DOMAIN]["switches"]
        compiled_list = []
        
        for idx, alarm in db.items():
            if not alarm.get("enabled", True):
                continue
            try:
                num_id = int(idx)
            except ValueError:
                num_id = 0
            
            friendly_name = f"Alarm {num_id}"
            if idx in switches:
                friendly_name = switches[idx].name
                
            compiled_list.append({
                "alarm_id": num_id,
                "Friendly name": friendly_name,
                "time": alarm.get("time", "00:00"),
                "Reoccurring": alarm.get("reoccurring", "once"),
                "persistant": alarm.get("persistent", False)
            })
            
        compiled_list.sort(key=lambda x: x["alarm_id"])
        self._state = len(compiled_list)
        self._attr_extra_state_attributes = {"alarms": compiled_list}

    def update(self) -> None:
        """Synchronous update for polling."""
        self._process_data()