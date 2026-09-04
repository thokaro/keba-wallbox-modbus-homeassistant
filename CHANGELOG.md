# Changelog

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
