# Changelog

## 2026.5.0b2 - 2026-05-04

- Added a Home Assistant reconfigure flow for connection settings and moved polling/display defaults to the options flow.
- Added config-entry migration that splits legacy mixed connection and runtime option values into `data` and `options`.
- Switched coordinator storage to `entry.runtime_data` and added typed config-entry helpers.
- Added tests for config data migration, config flow setup, options, and reconfiguration.
- Added GitHub Actions validation for tests, Ruff, HACS, and hassfest.
- Updated README documentation with a model feature matrix, troubleshooting notes, validation badge, and Apache 2.0 license badge.
- Changed the project license from MIT to Apache License 2.0.
