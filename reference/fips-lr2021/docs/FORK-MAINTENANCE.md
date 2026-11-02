# Fork maintenance

## Policy

- Upstream `jmcorgan/fips` is **read-only context**.
- No PR, issue, comment or push goes upstream.
- All FIPS work lives on `c03rad0r/fips`, branch `balloon-lr2021`.
- Fork `master` is a clean mirror of upstream `master`.
- The event build is pinned by tag `event-2026-11` and `fips/fips-pin.txt`.

## One-time sync

```bash
git remote add upstream https://github.com/jmcorgan/fips.git   # fetch only
git fetch upstream master
git checkout master
git merge --ff-only upstream/master
git push origin master

git checkout -b balloon-lr2021
```

The fork was last observed 0 ahead / 1,399 behind before this branch was made.
The sync script handles the same operation later.

## Ongoing sync

From this directory:

```bash
./scripts/sync-fips-fork.sh --repo ~/repos/fips-fork
```

It:

1. fetches upstream,
2. fast-forwards fork `master`,
3. rebases `balloon-lr2021`,
4. runs the host tests,
5. regenerates the vendored patch,
6. updates `fips/fips-pin.txt`,
7. pushes `master` and `balloon-lr2021` to the fork.

On conflict or test failure it stops and leaves `event-2026-11` untouched.

## Conflict rule

If upstream changed a file the transport touches:

- do not force-push over `event-2026-11`;
- create `sync/YYYYMMDD` and resolve there;
- run `cargo test -p fips-lr2021` and `cargo check -p fips-mesh`;
- only then move `balloon-lr2021` and the pin.

## Cadence

Run the sync before each build session and before opening the balloon-fresh PR.
For long-lived use, a daily or weekly timer is enough; the event pin protects the
demo from a bad upstream day.

The example units are in `scripts/fips-fork-sync.service` and
`scripts/fips-fork-sync.timer`. Adjust the `FIPS_DIR` path and install them with:

```bash
mkdir -p ~/.config/systemd/user
cp scripts/fips-fork-sync.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now fips-fork-sync.timer
```

The service only pushes to `c03rad0r/fips`; upstream remains fetch-only.
