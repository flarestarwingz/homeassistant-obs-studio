# OBS WebSocket Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

[OBS Studio](https://obsproject.com/) is a free, open-source application for video recording and live streaming. It is widely used by content creators, gamers, and professionals for streaming to platforms such as Twitch, YouTube, and Facebook Live.

This custom Home Assistant integration connects to OBS Studio via the [WebSocket v5 protocol](https://github.com/obsproject/obs-websocket). It exposes stream, recording, and virtual camera status as sensors, buttons to control streaming/recording/virtual cam, a select entity to switch scenes, and switches to show or hide scene items. It uses a persistent connection with event-driven updates for near-instant state changes.

This is a fork of [brianegge/homeassistant-obs-studio](https://github.com/brianegge/homeassistant-obs-studio) extended with scene switching, scene item visibility control, recording and virtual camera control, and configurable entity naming.

## Requirements

- Home Assistant 2024.1+
- OBS Studio 28+ (ships with WebSocket v5)
- WebSocket server enabled in OBS (Tools > WebSocket Server Settings)
- Network connectivity between Home Assistant and the OBS machine

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** > three-dot menu > **Custom repositories**
3. Add this repository URL and select **Integration** as the category
4. Search for and install **OBS WebSocket**
5. Restart Home Assistant

### Manual

1. Copy the `obs_websocket` folder to your Home Assistant `custom_components` directory:

   ```
   custom_components/
   └── obs_websocket/
       ├── __init__.py
       ├── button.py
       ├── config_flow.py
       ├── const.py
       ├── icons.json
       ├── manifest.json
       ├── select.py
       ├── sensor.py
       ├── strings.json
       ├── switch.py
       └── ...
   ```

2. Restart Home Assistant.

3. Go to **Settings > Devices & Services > Add Integration** and search for **OBS WebSocket**.

4. Enter your OBS machine's hostname/IP, port (default `4455`), and password (if authentication is enabled in OBS).

## Removal

1. Go to **Settings > Devices & Services**.
2. Find the **OBS WebSocket** integration entry.
3. Click the three-dot menu and select **Delete**.
4. Optionally remove the `obs_websocket` folder from `custom_components` and restart Home Assistant.

> **Note:** After upgrading from an older version of this integration, delete and re-add the integration once. Older versions used different entity IDs, and the leftover (orphaned) entities otherwise remain in the entity registry.

## OBS Setup

1. Open OBS Studio.
2. Go to **Tools > WebSocket Server Settings**.
3. Check **Enable WebSocket server**.
4. Note the port (default `4455`).
5. If **Enable Authentication** is checked, copy the password for the HA config flow. You can also uncheck it if your network is trusted.

## Supported Devices

This integration supports any instance of **OBS Studio 28 or newer** running on Windows, macOS, or Linux. Older versions of OBS that do not include the built-in WebSocket v5 server are not supported.

## Supported Functions

### Sensors

#### Stream Status

Reports the current streaming state of OBS.

| State | Description |
|-------|-------------|
| `streaming` | OBS is actively streaming |
| `reconnecting` | Stream is reconnecting |
| `idle` | Not streaming |

**Attributes:**

| Attribute | Description |
|-----------|-------------|
| `output_bytes` | Total bytes sent |
| `output_duration` | Stream duration in milliseconds |
| `output_timecode` | Stream timecode (HH:MM:SS.mmm) |
| `output_skipped_frames` | Number of skipped frames |
| `output_total_frames` | Total frames transmitted |
| `output_congestion` | Network congestion value (0.0 - 1.0) |

#### Stream Service (Diagnostic)

Reports the configured streaming service. State is the service type (e.g. `rtmp_common`). Disabled by default; enable it in the entity registry.

**Attributes:**

| Attribute | Description |
|-----------|-------------|
| `stream_service_settings` | Dict containing `server`, `key`, and other service-specific fields |

#### Recording

Reports whether OBS is currently recording.

| State | Description |
|-------|-------------|
| `recording` | Recording is active |
| `idle` | Not recording |

#### Virtual Camera

Reports whether the OBS virtual camera output is active.

| State | Description |
|-------|-------------|
| `active` | Virtual camera is running |
| `idle` | Virtual camera is stopped |

### Buttons

#### Start Stream

Press to start streaming in OBS. Raises an error if OBS is unreachable or the stream cannot be started (e.g. already streaming).

#### Stop Stream

Press to stop streaming in OBS. Raises an error if OBS is unreachable or the stream cannot be stopped (e.g. not currently streaming).

#### Toggle Recording

Press to start or stop recording. The **Recording** sensor reflects the resulting state.

#### Toggle Virtual Camera

Press to start or stop the virtual camera output. The **Virtual Camera** sensor reflects the resulting state.

### Select

#### Scene

A dropdown listing all OBS scenes. Selecting an option switches OBS to that scene (calls `SetCurrentProgramScene`). The current scene is shown as the select's current option and updates automatically when the scene changes.

### Switches (Scene Items)

Scene item switches control the visibility (enable/disable) of sources within scenes. How many switches are created and how they are named depends on the **Options** (see below).

**Important:** switches are only created for items that exist in OBS at integration setup time. If you add or remove sources in OBS, reload the integration (or delete/re-add it) to refresh the switch set.

## Configuration

### Initial Setup

| Field | Default | Description |
|-------|---------|-------------|
| Host | `localhost` | Hostname or IP of the OBS machine |
| Port | `4455` | WebSocket server port |
| Password | *(empty)* | WebSocket password (leave blank if auth is disabled) |

After initial setup, you can reconfigure the connection (host, port, password) via the integration's three-dot menu > **Reconfigure**. If the password changes on the OBS side, use **Re-authenticate**.

### Options

Open **Settings > Devices & Services > OBS WebSocket > Options** to customize entity creation. Changing options reloads the integration automatically.

> **Note on labels:** the option fields are shown with the internal option keys (`device_name`, `scene_item_mode`, `scene_item_scenes`, `include_scene_sources`) when the integration's translations have not been applied by Home Assistant. See [Troubleshooting](#troubleshooting) for the fix.

| Option | Description |
|--------|-------------|
| `device_name` | Friendly name for the OBS device and the prefix shown on its entities. Defaults to `OBS Studio`. Useful when you have more than one OBS instance. |
| `scene_item_mode` | How scene item switches are created. |
| `scene_item_scenes` | Whitelist of scenes whose items become switches. Leave empty to include **all** scenes. Only affects switches, not the scene switcher select. |
| `include_scene_sources` | Whether to also create switches for scene items that are themselves scenes (nested scenes) or groups. Disable to expose only individual inputs. |

#### `scene_item_mode`

| Mode | Behavior | Naming |
|------|----------|--------|
| `sources` (default) | One switch per **unique source name** across the included scenes. Each switch controls that source's visibility in the **currently active scene**. | Just the source name, e.g. `Webcam`, `Jeopardy`. |
| `all` | One switch per **scene item** (source occurrence within a scene). | `Scene - Source`, e.g. `A Work - ITS Blue - Whiteboard`. |

**Behavior details for `sources` mode:**

- The switch is always available. `on` means the source is visible in the active scene; `off` means it is either hidden or not present in the active scene.
- Toggling a source that is not present in the active scene raises an error.
- Because the switch operates on the active scene, an automation referencing it controls whichever scene is current at the time. If you need per-scene precision, use `all` mode.

**Behavior details for `all` mode:**

- Each switch controls one specific scene item in a fixed scene, so automations are unambiguous.
- Names include the scene, which can produce long names for setups with many scenes.

Both modes create entities **once at setup** and never remove them, so entity IDs are stable for automations and dashboards. To change the set of switches (after editing `scene_item_scenes` or adding/removing OBS sources), reload the integration or delete and re-add it.

#### Example: trimming a large scene collection

A setup with many scenes (e.g. 24 scenes, including `JUNK*`/`TEST*`/`OFF`) can create a lot of switches. To reduce them:

1. Set `scene_item_scenes` to only your real scenes (e.g. `Webcam Only`, `A Work - ITS Blue`, `3D Printer`).
2. Disable `include_scene_sources` to skip nested-scene references.
3. Choose `sources` mode for one switch per source, or `all` mode for per-scene control.
4. Delete and re-add the integration to apply a clean entity set.

## Data Updates

The integration maintains a persistent WebSocket connection to OBS with two update mechanisms:

- **Event-driven (primary):** The `EventClient` listens for OBS events (stream/record/virtual cam state changes, scene changes, scene item enable/disable, scene list changes) and triggers an immediate refresh.
- **Heartbeat poll (fallback):** A `DataUpdateCoordinator` polls OBS every **60 seconds** to sync state in case an event is missed or the connection was briefly interrupted.

If the connection to OBS drops, entities are marked **unavailable** and the coordinator reconnects on the next poll cycle. Stream, recording, and virtual camera state degrades gracefully — a failure in one area does not take down the other entities.

## Automation Examples

**Notify when streaming starts:**

```yaml
automation:
  - alias: "Notify stream started"
    trigger:
      - platform: state
        entity_id: sensor.obs_stream_status
        to: "streaming"
    action:
      - service: notify.mobile_app
        data:
          message: "OBS is now streaming!"
```

**Switch scene on a schedule:**

```yaml
automation:
  - alias: "Switch to work scene at 9am"
    trigger:
      - platform: time
        at: "09:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.obs_scene
        data:
          option: "A Work - ITS Blue"
```

**Show the webcam in the current scene when a person enters:**

```yaml
automation:
  - alias: "Show webcam on presence"
    trigger:
      - platform: state
        entity_id: binary_sensor.presence
        to: "on"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.obs_webcam
```

> In `sources` mode, `switch.obs_webcam` enables the webcam in whichever scene is active. Use the `all` mode naming (`switch.obs_<scene>_webcam`) for scene-specific control.

**Record when streaming starts:**

```yaml
automation:
  - alias: "Record while streaming"
    trigger:
      - platform: state
        entity_id: sensor.obs_stream_status
        to: "streaming"
    action:
      - service: button.press
        target:
          entity_id: button.obs_toggle_recording
```

**Alert on high frame skipping:**

```yaml
automation:
  - alias: "Alert frame drops"
    trigger:
      - platform: template
        value_template: >
          {{ state_attr('sensor.obs_stream_status', 'output_skipped_frames') | int > 100 }}
    action:
      - service: notify.mobile_app
        data:
          message: "OBS has skipped {{ state_attr('sensor.obs_stream_status', 'output_skipped_frames') }} frames"
```

## Use Cases

- **Stream monitoring dashboards** - Display stream status, uptime, frame statistics, recording, and virtual camera state on a Lovelace dashboard.
- **Scene control** - Switch scenes from a dashboard or automation, and show/hide individual sources.
- **Automated notifications** - Get alerts on your phone when a stream starts, stops, or experiences issues.
- **Smart home integration** - Trigger lights, cameras, or "on air" signs when you go live or change scenes.
- **Uptime tracking** - Log stream duration and stability over time using the recorder.

## Known Limitations

- **Synchronous library** - The underlying `obsws-python` library uses threads rather than asyncio, so all calls are wrapped with `async_add_executor_job`.
- **Scene items are fixed at setup** - Scene item switches are created from the scene structure present when the integration loads. Adding or removing sources in OBS requires a reload.
- **Single stream output** - Only the primary stream output is monitored.
- **No auto-discovery** - You must manually enter the OBS host and port; the integration cannot discover OBS instances on the network.
- **No device firmware version** - The OBS version is not currently reported in device info.

## Troubleshooting

| Symptom | Solution |
|---------|----------|
| "Failed to connect to OBS WebSocket" during setup | Verify OBS is running and the WebSocket server is enabled in Tools > WebSocket Server Settings. Check that the host, port, and password are correct. |
| Entities show "unavailable" | OBS may have been closed or the network connection was lost. The integration will automatically reconnect within 60 seconds when OBS becomes reachable. |
| Options fields show raw keys (e.g. `scene_item_mode`) instead of friendly labels, or entity names are missing | The integration's translations were not applied. Clear the translation cache and restart: stop Home Assistant, delete `config/.storage/translation_cache`, then start Home Assistant again. |
| Old entities remain after updating the integration | The old entities are orphaned. Delete the integration and re-add it to remove them. |
| Scene item switches missing after changing Options | Changing Options reloads the integration but does not remove previously created entities. Delete and re-add the integration to rebuild the switch set from the new settings. |
| "Scene item is not present in the current OBS scene" when toggling | In `sources` mode, that source is not in the currently active scene. Switch to a scene containing it, or use `all` mode for per-scene switches. |
| State doesn't update immediately | Verify OBS is version 28+. Older versions may not emit WebSocket v5 events. The fallback poll interval is 60 seconds. |
| Integration won't load after HA update | Check the Home Assistant logs for errors. You may need to update the `obsws-python` dependency or the integration code. |
| Password changed in OBS | Use **Settings > Devices & Services > OBS WebSocket > (three-dot menu) > Re-authenticate** to update the password. |

## Dependencies

- [`obsws-python==1.8.0`](https://pypi.org/project/obsws-python/) - OBS WebSocket v5 Python library
