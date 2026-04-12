[![Version](https://img.shields.io/github/v/release/thokaro/keba-wallbox-modbus-homeassistant)](https://github.com/thokaro/keba-wallbox-modbus-homeassistant/releases)
[![HACS Category](https://img.shields.io/badge/HACS-Integration-41BDF5.svg)](https://hacs.xyz/docs/categories/integration/)
[![Platform](https://img.shields.io/badge/Platform-Home%20Assistant-41BDF5.svg)](https://www.home-assistant.io/)
[![Donate via PayPal](https://img.shields.io/badge/Donate-PayPal-00457C?logo=paypal&logoColor=white)](https://paypal.me/thokaro)
[![Support via Buy Me a Coffee](https://img.shields.io/badge/Support-Buy%20Me%20a%20Coffee-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/thokaro)

# KEBA Wallbox Modbus – Home Assistant Integration

This custom integration connects **KEBA KeContact P30 and P40** wallboxes to **Home Assistant** via **Modbus TCP**.

---

## ✨ Features

- 🔎 Automatic `P30` / `P40` detection via Modbus register `1016`
- 🧠 Model-specific register handling for both wallbox families
- 📊 Sensors for state, currents, voltages, power, energy and diagnostics
- 🎛️ Writable entities for charging current, charging power, selected configuration registers and wallbox actions
- 🏷️ Decoded product type and feature attributes on the diagnostic serial sensor
- 🖥️ Optional UDP display support for `P30` wallboxes with display
- ⚙️ UI-based setup via Home Assistant config flow

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
- `Update interval`: polling interval in seconds, default `30`, minimum `5`

The integration validates the wallbox during setup by reading the serial number and product register.

---

## 🖥️ Notify Service

If display support is detected, Home Assistant also creates a `notify` service for the wallbox display. This is mainly relevant for `P30` wallboxes with display.

- The service name is derived from the wallbox or device name, for example `notify.keba_wallbox`.
- `message` contains the text shown on the display.
- `data.min_time` defines the minimum display duration in seconds.
- `data.max_time` defines the maximum display duration in seconds.
- `min_time` defaults to `2` seconds and `max_time` defaults to `10` seconds.
- Both values must be numeric and are sent as rounded whole seconds.

Example:

```yaml
action: notify.send_message
target:
  entity_id: notify.keba_wallbox
data:
  message: "PV charging active"
  data:
    min_time: 5
    max_time: 20
```

---

## 📊 Exposed Entities

### Sensors

- `Charging state`
- `Cable state`
- `Error code`
- `Phase 1 current`
- `Phase 2 current`
- `Phase 3 current`
- `Active power`
- `Total energy`
- `Session energy`
- `Phase 1 voltage`
- `Phase 2 voltage`
- `Phase 3 voltage`
- `Power factor`
- `Charging current limit`
- `Maximum supported current`
- `Fast charging state` (`P40`)
- `Serial number`
- `Firmware version`
- `Hardware revision device` (`P40`)
- `Hardware revision MS10` (`P40`)

### Numbers

- `Charging current limit`
- `Charging power`
- `Session energy limit`
- `Failsafe current`
- `Failsafe timeout`

### Switches

- `Charger enable`

### Selects

- `Phase switch source`
- `Phase switch state`

### Buttons

- `Unlock plug`
- `Persist failsafe settings` (`P30`)
- `Activate fast charging` (`P40`)

---

## 📝 Important Notes

- Some KEBA registers depend on wallbox model, firmware and licensed feature set.
- The integration selects the correct register profile automatically for `P30` and `P40`.
- Decoded product details from register `1016` are exposed as attributes on the diagnostic sensor `Serial number`.
- `Phase switch source` uses model-specific option sets. `UDP` is only offered on `P30`.
- `Persist failsafe settings` exists only on `P30`. `Activate fast charging` exists only on `P40`.
- `Unlock plug` is only exposed for `socket` variants. On `P30`, KEBA documents that unlocking is only possible in `suspended` state and the charging process must be stopped beforehand, for example via register `5014`.
- `Failsafe current` accepts `0` A or `6` to `32` A. `0` A suspends charging when failsafe mode becomes active.
- `Failsafe timeout` accepts `0` s or `5` to `600` s. `0` deactivates failsafe mode.
- `Persist failsafe settings` exists only on `P30` and writes the current failsafe configuration to the wallbox EEPROM.
- `Failsafe` activates only after a timeout value greater than `0` is written. Every received Modbus command resets the internal timeout timer.
- On `P30`, disabling a previously persisted failsafe requires writing timeout `0` and then persisting again with `5020 = 1`.
- `Charging power` is a convenience slider that maps to the same current register `5004` using voltage registers `1040`, `1042` and `1044`. If phase or voltage data is missing, nominal device assumptions are used as fallback.
- The integration allows `0` as a charging-current target on both `P30` and `P40`, so charging can be suspended directly via the writable current and power entities.
- When the wallbox is disabled, KEBA may report `0` via read register `1100` even though writable current limits still follow the documented minimum values. The integration therefore keeps the last valid `Charging current limit` and `Charging power` value instead of showing `0`.
- For `P40` firmware versions below `1.2.1`, KEBA documents a bug where registers `1036` and `1502` report `Wh` instead of `0.1 Wh`; the integration compensates for that automatically.
- Runtime values are treated as optional. If the wallbox or a Modbus proxy does not expose individual registers, the related entities may stay unavailable instead of failing the whole update.
- `Charger enable` and `Session energy limit` currently use optimistic state handling because there is no direct readback implemented for those command registers.
- The display `notify` service is only loaded when display support is detected.

---

## 💡 Community Notes

The following points are **community findings** and not part of the official KEBA Modbus documentation:

- For `P30` phase switching via register `5052`, users report that the wallbox only accepts a new phase-switch command roughly every **5 minutes**.
- A successful phase switch may briefly interrupt charging before the relay state changes and charging resumes.
- If a new `5052` command is sent during that cooldown, it may simply be ignored instead of being queued for later execution.
- Re-sending the desired phase-switch command periodically can therefore be more reliable than sending it only once.

---

## 🚧 Known Limitations

- No YAML setup. Configuration is UI-only.
- No full error code decoding table yet. The raw error value is exposed together with a hexadecimal attribute.
- No runtime test against a real wallbox is included in this repository.

---

## ❤️ Support

- [GitHub Issues](https://github.com/thokaro/keba-wallbox-modbus-homeassistant/issues)
- [Repository](https://github.com/thokaro/keba-wallbox-modbus-homeassistant)
