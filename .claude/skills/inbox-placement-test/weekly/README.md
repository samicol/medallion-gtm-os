# Weekly placement run helper

Optional helper for teams that run a placement test every week across several Bison workspaces.

- `discover.py <label> <KEY_ENV_NAME> <outdir>`: lists the workspace's active campaigns with their attached senders (vendor, provider type, batch tags, other tags) plus every sender in the workspace, writes `<label>-discovery.json` to `<outdir>` and prints a summary. Use it before Step 2 to decide how to split pools and which segment each pool serves.

It reads the API key named `<KEY_ENV_NAME>` and `EMAILBISON_BASE_URL` from the environment, or from the `.env` in `PLACEMENT_RUN_DIR` if set. Edit the `VENDORS` map at the top so it matches the inbox vendors your tags use.

Each pool's run still uses the skill scripts (`../scripts/0_token_audit.py` to `../scripts/8_write_sheet.py`) with `PLACEMENT_RUN_DIR`.
