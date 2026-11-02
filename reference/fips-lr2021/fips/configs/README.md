# FIPS configs

`*.yaml` profiles are **transport snippets**: merge the `transports.lr2021`
block into your own `fips.yaml`.

`us915-node-a.yaml` and `us915-node-b.yaml` are complete two-node examples for
the bench. Replace `REPLACE_WITH_NSEC` with a real nsec, or use the identity
file form your deployment already uses.

Both ends must agree on `band`, `radio_payload`, `mtu` and `sync_word`, and must
use different `local_id` values.
