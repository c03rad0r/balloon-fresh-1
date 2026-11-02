# FIPS fork

- **Fork:** https://github.com/c03rad0r/fips.git
- **Branch:** `balloon-lr2021`
- **Event tag:** `event-2026-11`
- **Upstream:** https://github.com/jmcorgan/fips (read-only)

The upstream repository is context only. No PR, issue, comment or push is made
against it. `master` in the fork mirrors upstream; the transport lives on
`balloon-lr2021`.

The exact commit is pinned in `fips-pin.txt`. The vendored diff is
`patches/0001-lr2021-transport.patch`.

If the fork is unavailable, the patch applies cleanly to the recorded upstream
base:

```bash
git clone https://github.com/jmcorgan/fips.git fips-base
cd fips-base
git checkout <upstream_base from fips-pin.txt>
git apply ../fips/patches/0001-lr2021-transport.patch
```

That is a recovery path only; normal builds use the fork.
