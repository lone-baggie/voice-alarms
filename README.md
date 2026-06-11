# Voice Alarms

Voice Alarms is an intent-based alarm system for Home Assistant voice satellites, designed to replicate the convenience of commercial assistants like Amazon Alexa or Google Home.

Based on the [HA-Alarms-and-Reminders](https://github.com/omaramin-2000/HA-Alarms-and-Reminders) framework, this integration allows you to create, delete, and list alarms using simple voice commands or Home Assistant actions.

## Features
* **Flexible Scheduling:** Set one-off or recurring alarms (daily, workdays, or specific days of the week).
* **Named Alarms:** Create alarms with unique names or let the system assign them numerical identifiers.
* **Automation Ready:** A global boolean sensor tracks when *any* alarm triggers, exposing the alarm name, satellite device ID, and media player info for custom automations.
* **Dynamic Management:** Alarms are created as individual Home Assistant switches. Deleting an alarm removes the switch; disabling a switch disables the alarm.

## Voice Commands & Actions

| Intent | Description |
| :--- | :--- |
| **Create alarm [at \<time\>] [every \<reoccurs\>]** | Creates one-off or recurring alarms. |
| **Create alarm called \<name\> [at \<time\>]...** | Creates a named alarm. |
| **Delete alarm \<name\> / \<time\>** | Removes an alarm by name or time. |
| **List alarms / Cancel alarm** | Lists current alarms or cancels the current trigger. |

**Available Actions:** 
* `voice_alarms.create_alarm`
* `voice_alarms.delete_alarm`
* `voice_alarms.delete_all_alarms`
* `voice_alarms.cancel_alarm`

## Entity Details

### Switches (switch.1 - switch.99)
Each alarm is represented as a switch. Turning it **OFF** disables it; turning it **ON** enables it.
* **Attributes:** `state`, `alarm_id`, `device_id`, `name`, `time`, `persistent`, `reoccurring`, `ringing`.

### Binary Sensor (binary_sensor.active_alarm)
This sensor turns **ON** when an alarm triggers.
* **Attributes:** Matches the active alarm's attributes (Device ID, Name, Time, etc.).

### Sensor (sensor.list_alarms)
* **State:** Count of active alarms.
* **Attributes:** A detailed list of all active alarms by name and time.

## Setup Instructions

### 1. Installation
Install via **HACS** as a "Custom Repository" (`https://github.com/lone-baggie/voice-alarms`), or manually copy the `custom_components/voice_alarms` directory into your `/config/custom_components/` directory and restart.

### 2. Custom Sentences
This integration requires a custom intent file to process your speech:
1. Navigate to `/config/custom_sentences/en/` (create the directory if it doesn't exist).
2. Save the [voice-alarms.yaml](https://github.com/lone-baggie/voice-alarms/blob/main/assets/voice-alarms.yaml) file into this folder.
3. Reload your voice intents in Home Assistant.

> **Warning:** Intent syntax is sensitive. Any accidental space or character change may break functionality.

## Automations & Sirens
This integration does not contain built-in sounds. Use the `binary_sensor.active_alarm` to trigger your preferred response.

### Example: ESPHome Alarm Trigger
If using an ESPHome device (like an M5Stack Atom Echo), you can expose a local "alarm switch" via a [package](https://github.com/lone-baggie/voice-alarms/blob/main/assets/add_switch.yaml):

    packages:
      add_switch: !include packages/add_switch.yaml

Here is an example automation.

     alias: "Atom Alarm Trigger"
    trigger:
      - trigger: state
        entity_id: binary_sensor.active_alarm
        attribute: device_id
        to: "YOUR_DEVICE_ID_HERE"
    action:
      - action: switch.turn_on
        target:
          entity_id: switch.YOUR_ALARM_SWITCH_NAME

You can obtain the device ID from the alarm switch attributes.


## Notes
* **Switch Behavior:** When created, alarm switches are turned **ON** (active). Turning a switch off disables the alarm.
* **Reboot Recovery:** If Home Assistant is rebooted, all disabled alarm switches will be reset to **ON** (active).
* **Daily Alarms:** One-off alarms are automatically deleted 1 minute after being triggered.
