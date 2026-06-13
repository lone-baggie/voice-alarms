"""Services for the Alarm and Reminders application."""
import logging
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .alarm_manager import async_create_alarm, async_delete_alarm

_LOGGER = logging.getLogger(__name__)

# --- Service Handler Functions ---

async def handle_create_alarm(call: ServiceCall):
    """Create an alarm using centralized manager."""
    time_str = call.data["time"]
    name = call.data.get("name")
    reoccurring = call.data.get("reoccurring", "once")
    device_id = call.data.get("device_id", "")
    
    success, message = await async_create_alarm(call.hass, time_str, reoccurring, name, device_id)
    if not success:
        _LOGGER.warning(f"Failed to create alarm: {message}")
    else:
        _LOGGER.info(message)

async def handle_alarm_on_off(call: ServiceCall):
    """Toggle an existing alarm switch."""
    name = call.data.get("name")
    time = call.data.get("time")
    state = call.data.get("state").lower()
    
    db = call.hass.data[DOMAIN]["alarms"]
    switches = call.hass.data[DOMAIN]["switches"]
    target_idx = next((idx for idx, a in db.items() if (name and a.get("name") == name) or (time and a.get("time") == time)), None)
    
    if target_idx and target_idx in switches:
        if state == "on":
            await switches[target_idx].async_turn_on()
        else:
            await switches[target_idx].async_turn_off()
        _LOGGER.info(f"Alarm {target_idx} turned {state}.")
    else:
        _LOGGER.warning(f"Could not find active alarm switch for: {name or time}")

async def handle_cancel_alarm(call: ServiceCall):
    """Cancel current alarms."""
    from .helpers import async_cancel_alarm_logic
    await async_cancel_alarm_logic(call.hass)
        
async def handle_delete_alarm(call: ServiceCall):
    """Delete an alarm using centralized manager."""
    name = call.data.get("name")
    time = call.data.get("time")
    if await async_delete_alarm(call.hass, name=name, time=time):
        _LOGGER.info("Alarm deleted.")
    else:
        _LOGGER.warning("Could not find alarm to delete.")
            
async def handle_list_alarms(call: ServiceCall) -> ServiceResponse:
    """List all alarms."""
    db = call.hass.data[DOMAIN]["alarms"]
    return {"alarms": list(db.values())}

async def handle_delete_all_alarms(call: ServiceCall):
    """Delete all alarms and clean up state."""
    db = call.hass.data[DOMAIN]["alarms"]
    switches = call.hass.data[DOMAIN].get("switches", {})
    
    for idx in list(switches.keys()):
        await switches[idx].async_remove()
    
    switches.clear()
    db.clear()
    
    from . import save_alarms_to_disk
    await call.hass.async_add_executor_job(save_alarms_to_disk, call.hass)
    
    if list_sensor := call.hass.data[DOMAIN].get("list_sensor"):
        await list_sensor.async_update_ha_state()
    _LOGGER.info("All alarms deleted.")

# --- Registration Function ---

async def async_setup_services(hass: HomeAssistant) -> None:
    """Register core platform orchestration actions."""
    
    hass.services.async_register(DOMAIN, "create_alarm", handle_create_alarm,
        schema=vol.Schema({
            vol.Required("time"): cv.string,
            vol.Optional("name"): cv.string,
            vol.Optional("reoccurring"): cv.string,
            vol.Optional("device_id"): cv.string,
        }))

    hass.services.async_register(DOMAIN, "alarm_on_off", handle_alarm_on_off,
        schema=vol.Schema({
            vol.Required("state"): vol.In(["on", "off"]),
            vol.Optional("name"): cv.string,
            vol.Optional("time"): cv.string,
        }))

    hass.services.async_register(DOMAIN, "cancel_alarm", handle_cancel_alarm)
    
    hass.services.async_register(DOMAIN, "delete_alarm", handle_delete_alarm,
        schema=vol.Schema({
            vol.Optional("name"): cv.string,
            vol.Optional("time"): cv.string,
        }))
        
    hass.services.async_register(DOMAIN, "list_alarms", handle_list_alarms,
        supports_response=SupportsResponse.ONLY)
        
    hass.services.async_register(DOMAIN, "delete_all_alarms", handle_delete_all_alarms)