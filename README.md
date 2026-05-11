[![Version](https://img.shields.io/github/v/release/thokaro/keba-wallbox-modbus-homeassistant)](https://github.com/thokaro/keba-wallbox-modbus-homeassistant/releases)
[![Validate](https://github.com/thokaro/keba-wallbox-modbus-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/thokaro/keba-wallbox-modbus-homeassistant/actions/workflows/validate.yml)
[![HACS Category](https://img.shields.io/badge/HACS-Integration-41BDF5.svg)](https://hacs.xyz/docs/categories/integration/)
[![Platform](https://img.shields.io/badge/Platform-Home%20Assistant-41BDF5.svg)](https://www.home-assistant.io/)
[![Donate via PayPal](https://img.shields.io/badge/Donate-PayPal-00457C?logo=paypal&logoColor=white)](https://paypal.me/thokaro)
[![Support via Buy Me a Coffee](https://img.shields.io/badge/Support-Buy%20Me%20a%20Coffee-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/thokaro)

# KEBA Wallbox Modbus – Home Assistant Integration

This custom integration connects **KEBA KeContact P30 and P40** wallboxes to **Home Assistant** via **Modbus TCP**.

> [!NOTE]
> This integration is currently in **beta**. `P40` support is implemented, but I could not test it with a real `P40` wallbox yet. Feedback, test results and issue reports are very welcome.

---

## ✨ Features

- 🔎 Automatic `P30` / `P40` detection via Modbus register `1016`
- 🧠 Model-specific register handling for both wallbox families
- 📊 Sensors for state, currents, voltages, power, energy and diagnostics
- 🎛️ Writable entities for charging current, charging power, selected configuration registers and wallbox actions
- 🏷️ Decoded product type and feature attributes on the diagnostic serial sensor
- 🖥️ Optional UDP display support for `P30` wallboxes with display via a Home Assistant `notify` entity
- ⚙️ UI-based setup via Home Assistant config flow

### Model Feature Matrix

| Feature | P30 | P40 |
| --- | --- | --- |
| Automatic model detection | ✅ | ✅ |
| Runtime sensors for state, current, voltage, power and energy | ✅ | ✅ |
| Writable charging current and charging power | ✅ | ✅ |
| Phase switch source and state | ✅ | ✅ |
| UDP display notification entity | ✅, display variants only | ❌ |
| Persist failsafe settings button | ✅ | ❌ |
| Fast charging state and activation button | ❌ | ✅ |
| Hardware revision sensors | ❌ | ✅ |
| P40 pre-`1.2.1` energy scaling compensation | ❌ | ✅ |

---

## 📦 Installation

### Option 1: One-click repository add via My Home Assistant (HACS)

1. Make sure **HACS** is installed in your Home Assistant instance.
2. Click the button below and follow the prompts. This adds the repository to HACS; installation is still done in HACS.

[![Open your Home Assistant instance and add this repository.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=thokaro&repository=keba-wallbox-modbus-homeassistant&category=integration)

3. In **HACS → Integrations**, search for **KEBA Wallbox Modbus** and install it.
4. Restart Home Assistant.

---

### Option 2: Installation via HACS (manual)

1. Make sure **HACS** is installed in your Home Assistant instance.
2. Go to **HACS → Integrations**.
3. Open the menu in the top right corner and select **Custom repositories**.
4. Add this repository URL:

```text
https://github.com/thokaro/keba-wallbox-modbus-homeassistant
```

5. Select **Integration** as the category.
6. Click **Add**.
7. Search for **KEBA Wallbox Modbus** in HACS and install it.
8. Restart Home Assistant.

---

### Option 3: Manual Installation

1. Download or clone this repository.
2. Copy the folder:

```text
custom_components/keba_wallbox_modbus
```

into your Home Assistant configuration directory:

```text
config/custom_components/
```

3. Restart Home Assistant.

---

## ⚙️ Configuration

After restarting Home Assistant:

1. Go to **Settings → Devices & Services**.
2. Click **Add Integration**.
3. Search for **KEBA Wallbox Modbus**.
4. Enter the required connection details:

- `Host`: IP address or DNS name of the wallbox
- `Display UDP host`: optional separate IP address or DNS name for UDP display commands and display detection; mainly relevant for `P30` wallboxes with display or when Modbus is routed differently
- `Modbus unit ID`: default `255`; direct KEBA access usually uses `255`, but a Modbus proxy may require a different value
- `Port`: default `502`
- `Timeout`: Modbus TCP timeout in seconds
- `Update interval`: polling interval in seconds, default `15`, minimum `10`
- `Default display minimum duration`: default `2` seconds, minimum `0`, maximum `10`
- `Default display maximum duration`: default `10` seconds, minimum `0`, maximum `10`

The integration validates the wallbox during setup by reading the serial number and product register.
The display duration defaults can be changed later from the integration options.

KEBA wallboxes allow only one active Modbus TCP client connection. If the wallbox should be controlled by multiple systems, for example Home Assistant and another energy manager, place a Modbus TCP proxy in front of the wallbox and connect all clients to that proxy. The built-in Modbus proxy in `evcc` can be used for this setup.

---

## 📊 Exposed Entities

### Sensors

- Charging state
- Charger status (`A` ready, `B` connected, `C` charging)
- Cable state
- Error code
- Phase 1 current
- Phase 2 current
- Phase 3 current
- Active power
- Total energy
- Session energy
- Phase 1 voltage
- Phase 2 voltage
- Phase 3 voltage
- Power factor
- Charging current limit
- Maximum supported current
- Fast charging state (`P40`)
- Serial number
- Firmware version
- Hardware revision device (`P40`)
- Hardware revision MS10 (`P40`)

### Numbers

- Charging current limit
- Charging power
- Session energy limit
- Failsafe current
- Failsafe timeout

### Switches

- Charger enable

### Selects

- Phase switch source
- Phase switch state

### Buttons

- Unlock plug
- Persist failsafe settings (`P30`)
- Activate fast charging (`P40`)

### Notify

- Wallbox display notification entity (`P30` with detected display support)

---

## 🖥️ Display Notifications

If display support is detected, Home Assistant creates a `notify` entity for the wallbox display. This is mainly relevant for `P30` wallboxes with display.

- The entity ID is derived from the wallbox or device name, for example `notify.keba_p30`.
- `notify.send_message` uses Home Assistant's current notify entity action.
- `message` contains the text shown on the wallbox display.
- `notify.send_message` automatically uses the configured default display duration, so no timing data is needed in the action YAML. The factory defaults are `2` to `10` seconds.
- Use the device-specific `display_message` action when the display duration should be configurable. The action domain matches the notify entity object ID, for example `keba_p30.display_message` for `notify.keba_p30`.
- `data.min_time` defines the minimum display duration in seconds. The factory default is `2`.
- `data.max_time` defines the maximum display duration in seconds. The factory default is `10`.
- Both duration values must be numeric values between `0` and `10`, and `min_time` must not be greater than `max_time`. They are sent to the wallbox as rounded whole seconds.

Send a display message with the default duration:

```yaml
action: notify.send_message
target:
  entity_id: notify.keba_p30
data:
  message: "PV charging active"
```

Send a display message with custom duration. If `min_time` or `max_time` is omitted, the configured default is used for the missing value:

```yaml
action: keba_p30.display_message
data:
  message: "PV charging active"
  data:
    min_time: 5
    max_time: 10
```

When migrating automations from the old notify service behavior, move custom display timing out of `notify.send_message` and call the device-specific `display_message` action instead.

---

## 🔌 Wallbox Modbus And Feature Requirements

Modbus TCP must be enabled on the wallbox before this integration can connect to it. The default Modbus TCP port is `502`, and direct KEBA access usually uses Modbus unit ID `255`.

### P30

For phase switching, the KEBA phase switch (`KeContact S10`) is required. Switching control via Modbus must also be enabled in the wallbox settings.

### P40

The following settings must be enabled with the KEBA eMobility App:

- Enable Modbus: The `Enable` and `Enable RFID` options must be activated in the `Modbus` settings.
- To use RFID cards, enable `Authorization` under `Device`.
- For phase switching, firmware version `1.3.0` or newer is required. In the `Photovoltaic Optimized Charging` settings, phase switching must be enabled and `Communication channel` must be set to `Modbus`.

---

## 📝 Important Notes

- Some KEBA registers depend on wallbox model, firmware and licensed feature set.
- KEBA wallboxes allow only one active Modbus TCP client. Use a Modbus TCP proxy, for example the built-in proxy in `evcc`, when multiple systems should access or control the wallbox.
- The integration selects the correct register profile automatically for `P30` and `P40`.
- Decoded product details from register `1016` (`Product type and features`) are exposed as attributes on the diagnostic sensor `Serial number`.
- `Phase switch source` uses model-specific option sets. `UDP` is only offered on `P30`.
- `Persist failsafe settings` exists only on `P30`. `Activate fast charging` exists only on `P40`.
- `Unlock plug` is only exposed for `socket` variants. On `P30`, KEBA documents that unlocking is only possible in `suspended` state and the charging process must be stopped beforehand, for example via register `5014` (`Enable/Disable charging station`).
- `Failsafe current` accepts `0` A or `6` to `32` A in 0.1 A steps. `0` A suspends charging when failsafe mode becomes active.
- `Failsafe timeout` accepts `0` s or `5` to `600` s. `0` deactivates failsafe mode.
- `Persist failsafe settings` exists only on `P30` and writes the current failsafe configuration to the wallbox EEPROM.
- `Failsafe` activates only after a timeout value greater than `0` is written. Every received Modbus command resets the internal timeout timer, so a timeout at or below the configured `Update interval` may never elapse while Home Assistant is polling the wallbox. Use a timeout clearly above the update interval if Home Assistant should keep polling.
- On `P30`, disabling a previously persisted failsafe requires writing timeout `0` to register `5018` (`Failsafe timeout`) and then persisting again with register `5020` (`Failsafe Persist`) set to `1`.
- `Charging power` is the desired active charging power in kW. It is stored as an optimistic target and immediately writes one calculated charging-current limit to register `5004` (`Set charging current`).
- Writing `Charging current limit` manually is treated as a direct current override. Writable current values are adjustable only in 0.1 A steps.
- After writing a value with a matching read register, the integration publishes the requested value immediately and then performs a targeted readback of only the affected register. This keeps the Home Assistant UI responsive without waiting for the next full update cycle.
- KEBA wallboxes may briefly return the previous value after a successful write. During this readback window, stale values from targeted readbacks or normal polling are ignored for the affected register until the wallbox confirms the requested value.
- If the wallbox does not confirm the requested value within 30 seconds, the protection expires and the next real readback is shown. This avoids hiding rejected commands, unsupported values or wallbox-side rounding permanently.
- The integration allows `0` as a charging-current target on both `P30` and `P40`, so charging can be suspended directly via `Charging current limit`.
- When the wallbox is disabled, KEBA may report `0` via read register `1100` (`Max charging current`) even though writable current limits still follow the documented minimum values. The integration therefore keeps the last valid `Charging current limit` value instead of showing `0`.
- Runtime polling is tiered: fast-changing values are read every configured `Update interval`, while slower runtime/configuration values such as total energy, maximum supported current, phase-switch state/source and failsafe settings are read on startup and then every 300 seconds.
- For `P40` firmware versions below `1.2.1`, KEBA documents a bug where registers `1036` (`Total energy`) and `1502` (`Charged energy`) report `Wh` instead of `0.1 Wh`; the integration compensates for that automatically.
- Runtime values are treated as optional. If the wallbox or a Modbus proxy does not expose individual registers, the related entities may stay unavailable instead of failing the whole update.
- The display `notify` entity and its device-specific `display_message` action are only usable when display support is detected.

---

## 💡 Community Notes

The following points are **community findings** and not part of the official KEBA Modbus documentation:

- For `P30` phase switching via register `5052`, users report that the wallbox only accepts a new phase-switch command roughly every **5 minutes**.
- A successful phase switch may briefly interrupt charging before the relay state changes and charging resumes.
- If a new `5052` command is sent during that cooldown, it may simply be ignored instead of being queued for later execution.
- Re-sending the desired phase-switch command periodically can therefore be more reliable than sending it only once.

---

## 🔧 Troubleshooting

### Setup Fails With `cannot_connect`

- Check that Modbus TCP is enabled on the wallbox.
- Verify the wallbox IP address or DNS name and the configured port. The default Modbus TCP port is `502`.
- Keep `Modbus unit ID` at `255` for direct KEBA access unless a Modbus proxy requires a different value.
- Make sure the wallbox is reachable from the Home Assistant host and no firewall blocks TCP traffic to the Modbus port.
- Temporarily increase `Timeout` if the network path is slow or goes through a proxy.

### Entities Become Unavailable Or Updates Stop

- KEBA wallboxes allow only one active Modbus TCP client connection. Disconnect other Modbus clients or place a Modbus TCP proxy in front of the wallbox.
- If a proxy is used, confirm that it exposes all registers used by the integration. Missing optional runtime registers can make individual entities unavailable.
- Increase `Update interval` if the wallbox or proxy becomes unstable under frequent polling.

### Display Notification Entity Is Missing

- Display support is detected via UDP and is mainly relevant for `P30` wallboxes with display.
- Check `Display UDP host` if Modbus and UDP display commands need to use different addresses.
- Confirm that UDP traffic to the wallbox is allowed on the network.
- `P40` display notifications are not exposed by this integration.

### P40 Feedback And Diagnostics

`P40` support is implemented but still marked beta. If behavior differs from the expected register data, open an issue and include:

- Wallbox model and firmware version
- Home Assistant version
- Integration version
- A diagnostics download from the integration page
- A short description of which entity or action behaves unexpectedly

---

## 🚧 Known Limitations

- No YAML setup. Configuration is UI-only.
- No full error code decoding table yet. The raw error value is exposed together with a hexadecimal attribute.
- No runtime test against a real wallbox is included in this repository.

---

## ❤️ Support

- [GitHub Issues](https://github.com/thokaro/keba-wallbox-modbus-homeassistant/issues)
- [Repository](https://github.com/thokaro/keba-wallbox-modbus-homeassistant)
