# Hardware tests

These scripts assume the patched FIPS fork is built and both bridges answer
`fips-lr2021ctl hello`.

```bash
export SERIAL_A=/dev/ttyACM0
export SERIAL_B=/dev/ttyACM1
export BAND=us915
./configure.sh
./per.sh 100 64
./soak.sh 1800
```

For a relay, set `SERIAL_RELAY` and run `scripts/demo-relay.sh`.

Record only measured results in `../../docs/RESULTS.md`.
