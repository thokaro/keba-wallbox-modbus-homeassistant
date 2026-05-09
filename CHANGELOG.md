# Changelog

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
