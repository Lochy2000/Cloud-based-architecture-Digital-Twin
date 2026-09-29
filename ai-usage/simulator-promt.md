Write one pytest unit test for simulate().

The test must verify that a boiler with a 20-minute cycle and
on_fraction=0.5 is ON from the cycle start up to but not including the
10-minute boundary, OFF from the 10-minute boundary up to but not including
the 20-minute boundary, and ON again exactly at 20 minutes.

Structure the test using Arrange–Act–Assert:
- Arrange: use the existing valid boiler configuration and fixed,
  timezone-aware UTC timestamps.
- Act: call simulate() exactly once for each parameterized case, passing an
  ambient temperature of 15.0.
- Assert: compare power_draw_kw with the exact expected value: 5.0 when ON
  and 0.0 when OFF.

Use pytest.mark.parametrize with cases at 06:00:00, 06:09:59, 06:10:00,
06:19:59, and 06:20:00. Give every case a descriptive ID. Follow the
existing test style and reuse the existing boiler_config fixture and
_timestamp() helper.

Use no mocks because simulate() is a pure function.
