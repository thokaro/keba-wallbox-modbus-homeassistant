# KEBA Modbus device access

This bundled Python module talks to KEBA wallboxes through a caller-supplied
`modbus_connection.ModbusUnit`. It has no dependency on an application framework
or a particular Modbus backend. The caller owns the connection and its lifetime.

`KebaModbusHub(unit, timeout=5)` sets KEBA's per-unit message spacing to 0.6 seconds.
`async_read_named_registers(mapping, optional_keys=...)` reads each named address
as a big-endian UINT32 using two holding registers. Optional failed reads produce
`None`; required failures and a poll with no successful reads raise
`KebaModbusError`.

`async_write_uint16(address, value)` sends a single-register FC06 write. Successful
writes are spaced by at least 5 seconds. Pending values for one address are
coalesced, and all their callers finish when the latest value is written.
`async_close()` cancels pending/in-flight writes and prevents new writes; it never
closes or disconnects the supplied unit's connection.

Requires Python 3.12+ and `modbus-connection>=4.10,<5`. With the newer
`require_timeout` API, the timeout becomes a shared connection requirement. On
4.10, it is a local deadline around the whole operation (including waiting for
access to the connection), in addition to the backend's own response timeout.
Register maps and polling schedules are supplied by the consumer.
