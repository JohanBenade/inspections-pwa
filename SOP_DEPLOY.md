# SOP: Code Deploy (api_deploy.sh -> PR -> merge)

**Status:** BINDING. This is the standard flow for every change to `main`.

**Why this method:** `git fetch` / `git pull` / `git push` HANG PERMANENTLY on this
network (pack-data transfer stalls; confirmed unfixable, 21 Jun 2026 — not a config
issue, not a credentials issue, the transport itself never completes). All git
*transport* is therefore banned. We deploy over the GitHub REST API (plain HTTPS,
~0.4s) and read files over the raw CDN. No local git clone is used or needed.

**Branch protection:** the `protect-main` ruleset blocks direct writes to `main`.
Every change must pass the `invariants` CI check before it can merge. The API
deploy script enforces this by always opening a PR — it never writes to `main`
directly.

---

## NEVER do these (they hang this network — no exceptions)

- `git push`  /  `git push -u origin <branch>`
- `git pull`  /  `git fetch`
- `git clone`
- any command that moves pack data to/from GitHub over git transport

If a future thread or reader proposes any of the above: STOP. It will hang. Use
`api_deploy.sh` for writes and `raw.githubusercontent.com` for reads instead.

---

## The flow (every deploy, no exceptions)

### 1. On Mac terminal -- read the current file (so the patch matches live)
Read the *currently deployed* file over the raw CDN before patching, so the
assert-guarded patch matches byte-for-byte:

```
curl -s https://raw.githubusercontent.com/JohanBenade/inspections-pwa/main/<repo_path> -o ~/Downloads/<file>
```

Example:
```
curl -s https://raw.githubusercontent.com/JohanBenade/inspections-pwa/main/app/routes/inspection.py -o ~/Downloads/inspection.py
```

### 2. On Mac terminal -- run the patch script Claude provides
Claude supplies an assert-guarded Python find/replace script (it aborts before
writing if the target text is not found verbatim). Run it against the file you
just downloaded:

```
python3 ~/Downloads/patch_<name>.py ~/Downloads/<file>
```

Expect a clear success line (e.g. `OK: both edits applied to ...`).
If you see `AssertionError` or any `EDIT ... FAILED` line: STOP, paste it back to
Claude. The live file changed since it was read; do not proceed.

### 3. On Mac terminal -- deploy via api_deploy.sh
One command commits the patched file to a NEW branch and opens a PR:

```
bash ~/Documents/GitHub/inspections-pwa/api_deploy.sh <owner/repo> <local_file> <repo_path> <branch> "<commit msg>"
```

Example:
```
bash ~/Documents/GitHub/inspections-pwa/api_deploy.sh JohanBenade/inspections-pwa ~/Downloads/inspection.py app/routes/inspection.py fix/short-name "fix(scope): short description"
```

The script prints progress and ends with a PR URL like:
`https://github.com/JohanBenade/inspections-pwa/pull/NN`
Paste that URL back to Claude.

Notes on the script:
- It works regardless of which directory you run it from (all targets are passed
  as arguments). The `~/Documents/GitHub/inspections-pwa/` path is only the
  location of the script file itself.
- It reads the PAT from `~/.gh_deploy_token` (chmod 600, expires ~21 Sep 2026).
- It always creates a branch + PR; it never writes to `main`.

### 4. In browser -- wait for the check, then merge
- Open the PR URL.
- Wait for **`invariants`** ("DB Invariants / invariants (pull_request)") to go
  green (~5-15s). It is **Required** — Merge stays disabled until it passes.
- If RED: the change tripped an invariant (R1-R5). STOP, drill the failure with
  Claude, do NOT force or bypass.
- Green -> **Merge pull request** -> **Confirm merge**.
- Render auto-deploys `main` after merge (~2-3 min).

There is no local-sync / branch-delete step. Nothing lives in a local git clone,
so there is nothing to pull or prune on the Mac. Merged branches can be deleted
in the browser if desired (cosmetic only).

### 5. On Render Shell -- verify deploy (read-only)
After Render finishes redeploying:

```
python3 /app/scripts/diagnostics/check_invariants_live.py
```

Expect **ALL PASS**:
- R1 CEI skip pollution residual: count=0 baseline=0
- R2 Inactive templates in use: count=1 baseline=1 (ghost `1161cc67`)
- R3 Link-copy gap: count=0 baseline=0
- R4 Cycle-number sequence gap: count=0 baseline=0
- R5 Clearance atomicity: count=0 baseline=0

A new pod hostname vs the prior run confirms the redeploy landed.
If any number moved unexpectedly: drill read-only with Claude, do NOT auto-fix.

---

## Reading files without deploying

To inspect any committed file (for review, diffing, or building a patch) without
a deploy, fetch it over the raw CDN:

```
curl -s https://raw.githubusercontent.com/<owner>/<repo>/main/<path>
```

Unauthenticated raw reads share a CDN rate limit; if a read returns empty or a
rate-limit response, wait and retry. (The sandbox's GitHub API limit is 60/hr on
a shared IP — a separate limit from the Mac's raw reads.)

---

## Repo paths (do not confuse)

- `inspections-pwa` -> repo `JohanBenade/inspections-pwa`; deploy script at
  `~/Documents/GitHub/inspections-pwa/api_deploy.sh`
- `schools-pwa` -> deploy script in its own repo root; local at `~/dev/schools-pwa`
  (NOT `~/Documents/GitHub`)

Both repos carry an identical `api_deploy.sh` and share the same `~/.gh_deploy_token`.

---

## Commit message convention

`type(scope): description` -- e.g. `fix(af017): carry prior NTS comment forward`.
Types: `fix`, `feat`, `refactor`, `chore`, `docs`. One logical change per commit.

---

## Rollback

Each merged PR has a one-click **Revert** button in the browser, which opens a
revert PR through the same `invariants`-gated flow. That is the safe rollback
path. Do not attempt a git-transport revert from the Mac (it will hang).

---

*Corrected 22 Jun 2026: replaced the dead git-transport flow (which hangs on this
network) with the api_deploy.sh + raw-CDN method. Verification updated to R1-R5
(was R1-R3). Supersedes the 14 Jun 2026 version.*
