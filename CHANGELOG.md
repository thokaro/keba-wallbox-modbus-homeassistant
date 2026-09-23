# Changelog

## 2026.9.2 - 2026-09-23

### ✨ Improvements

- Moved Modbus communication to Home Assistant's shared connection manager. Running entries and temporary setup/reconfiguration probes can share a connection, which is released when its last consumer unloads.
- Replaced direct pymodbus access with a bundled, backend-neutral KEBA device module. KEBA's 0.6-second request spacing, 5-second write interval and coalescing of pending writes are retained.
- Grouped optional P30 UDP display settings in an initially collapsed **P30: UDP display** section during setup, reconfiguration and option changes.

### 🐛 Fixes

- Cancel queued and in-flight writes cleanly during shutdown without closing another consumer's connection.
- Prefill the display duration fields inside the collapsed section: **2 seconds minimum** and **10 seconds maximum** by default. Existing configured values, including zero, are preserved.

### 📖 Documentation

- Documented shared connection ownership, the bundled device module, version-specific timeout behavior and the P30 UDP display section.
- Added regression coverage for connection sharing, probe failures, shutdown, timeout handling and serialized form defaults.

### ⬆️ Upgrade notes

- **Home Assistant 2026.9.0 or newer is required.** Update Home Assistant before installing this release if you are running an older version.
- No configuration migration or Modbus YAML hub is required. Existing entries, entity IDs, P30/P40 model settings, polling intervals and UDP display settings are retained. Restart Home Assistant after updating.
- On Home Assistant 2026.9's bundled Modbus library, the configured timeout bounds the entire operation, including waiting for the shared connection; the backend's 10-second response timeout also applies. With the newer shared timeout API, the largest timeout requirement among consumers applies.
- The write queue coordinates this integration's commands. Other integrations or external controllers writing to the same wallbox must also respect KEBA's write interval.

### ✅ Validation

- 90 tests passed locally, including shared-connection lifecycle and P30 display configuration regression tests.
- Ruff passed.
- No live wallbox test was performed.

## 2026.9.1 - 2026-09-23

- Added an `Automatic` / `P30` / `P40` model selection during setup and in integration options. Existing installations continue to use automatic detection by default.
- Added a workaround for P40 wallboxes reporting `0` in product register `1016` (issue #5): selecting `P40` applies the P40 register profile, firmware decoding, model-specific functions and charging-power calculations.
- Kept product-dependent equipment details unknown when the product register is missing or does not match the selected model.
- Added English and German model-selection labels and updated configuration documentation.
- Added regression coverage for the reported P40 firmware value, profile selection, capabilities, polling and switching back to automatic detection.

For affected P40 installations, select **P40** in the integration options after updating and restarting Home Assistant. Saving the options reloads the integration. This is an integration-side workaround; the empty product register still requires clarification from KEBA.

## 2026.9.0 - 2026-09-04

- Released the integration as stable and removed the beta notices from the documentation.
- Added a diagnostic phase-switch state sensor exposing the numeric states `1` and `3`.
- Moved phase-switch state polling to the regular update interval so state changes are reflected promptly.
- Changed enum sensors to become unavailable for unknown raw values instead of exposing synthetic `unknown (<value>)` states.
- Updated the English and German polling descriptions and added focused tests for phase-switch state polling and sensor behavior.

## 2026.6.0b1 - 2026-06-15

- Added a configurable slow runtime polling interval for slower runtime/configuration values such as total energy, maximum supported current, phase-switch source and failsafe settings. The default remains 300 seconds.
- Updated options flow labels and descriptions for the slow runtime polling interval in English and German.
- Changed the phase-switch state select to expose numeric states `1` and `3` for better compatibility with external consumers such as evcc.
- Kept legacy phase-switch write labels `1 phase` and `3 phases` as accepted aliases.
- Added focused tests for slow runtime polling options and numeric phase-switch select states.

## 2026.5.0b5 - 2026-05-11

- Improved Modbus timing behavior to better follow KEBA recommendations: writes are throttled to at least 5 seconds, the first pending write is sent immediately when possible, and repeated writes to the same register are coalesced to the newest value.
- Added targeted readback handling after writable entity changes. Home Assistant now publishes the requested value immediately, ignores short-lived stale readbacks for the affected register, and falls back to the real wallbox value if the requested value is not confirmed within 30 seconds.
- Reduced regular Modbus load with tiered runtime polling: fast-changing runtime values are read every update interval, while slower runtime/configuration values are read on startup and then every 300 seconds.
- Increased the minimum update interval to 10 seconds while keeping the default at 15 seconds.
- Refactored constants, register definitions, profile metadata, and centralized write/readback coordination for a leaner integration structure.
- Updated README documentation for Modbus prerequisites, P30/P40 feature requirements, update intervals, and readback behavior.
- Updated German translations to use real umlauts.
- Added and updated focused tests for Modbus write coalescing, targeted readback behavior, polling tiers, writable entities, configuration data, and entity descriptions.

## 2026.5.0b4 - 2026-05-09

- Added a diagnostic `Charger status` sensor exposing evcc-compatible `A`, `B`, and `C` states derived from KEBA charging and cable state.
- Added the optimistic `Charging power` number as a kW target that writes the calculated charging-current limit to register `5004`.
- Changed writable charging-current values, failsafe current values, and internal current calculations to 0.1 A steps.
- Improved Home Assistant service responsiveness by returning from number and switch writes after the Modbus write and refreshing coordinator data in the background.
- Reduced write delays during polling by letting Modbus writes run between individual register reads instead of waiting for a full polling cycle to finish.
- Kept charging-current regulation internals in place but stopped exposing the unfinished `Charging current regulation` switch in Home Assistant.
- Kept the last valid charging-current limit when KEBA reports `0` while the wallbox is disabled.
- Updated entity documentation and translations for the new sensor and writable current behavior.
- Added focused tests for power control, coordinator behavior, writable entity descriptions, number writes, switch writes, and charger status mapping.

## 2026.5.0b3 - 2026-05-04

- Fixed hassfest validation by adding the config-entry-only config schema.
- Fixed hassfest service validation by adding `services.yaml` for the display message service.
- Fixed manifest key ordering required by hassfest.
- Opted the GitHub Actions workflow into Node.js 24 action execution.

## 2026.5.0b2 - 2026-05-04

- Added a Home Assistant reconfigure flow for connection settings and moved polling/display defaults to the options flow.
- Added config-entry migration that splits legacy mixed connection and runtime option values into `data` and `options`.
- Switched coordinator storage to `entry.runtime_data` and added typed config-entry helpers.
- Added tests for config data migration, config flow setup, options, and reconfiguration.
- Added GitHub Actions validation for tests, Ruff, HACS, and hassfest.
- Updated README documentation with a model feature matrix, troubleshooting notes, validation badge, and Apache 2.0 license badge.
- Changed the project license from MIT to Apache License 2.0.
