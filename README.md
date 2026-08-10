# wildlife-vision

Wildlife Vision is an offline-first CLI for ingesting, processing, reviewing,
and exporting trail-camera images. A workspace contains the SQLite database,
session inventory, image files, and model/export directories for one active
collection environment.

## Database-Linked Workflow

The normal workflow is database-backed:

```text
workspace -> area -> site -> SD metadata or folder ingest -> session -> pipeline -> review -> export
```

Use the managed commands in this guide for durable inventories, ordered process
state, recovery plans, and session status. The standalone `clean` and `detect`
commands are available for ad hoc filesystem work, but do not update a session
database.

## Install And Help

This project targets Python 3.12 and uses `uv`:

```bash
uv sync --group dev
uv run wv --help
```

All examples use `uv run wv`; installed console scripts may use `wv` or
`wildlife-vision` directly. Put the global `--verbose` option before the
command:

```bash
uv run wv --verbose pipeline run <SESSION_ID>
```

## 1. Create Or Activate A Workspace

Initialize an existing writable directory:

```bash
uv run wv workspace init ~/WildlifeVision
```

The command creates and activates one workspace with:

```text
<workspace>/
  .wv/database.sqlite
  .wv/config.yml
  sessions/
  models/
  exports/
```

Activate another initialized workspace without changing its contents:

```bash
uv run wv workspace activate ~/AnotherWildlifeWorkspace
```

Only one workspace is active globally for the current user, including across
terminals. Activation does not initialize, migrate, or rewrite the selected
workspace. An older supported workspace can be activated so it can be upgraded
with `uv run wv workspace migrate`. Do not switch workspaces while ingest,
pipeline, configuration updates, or review GUIs are running.

Inspect or validate the active workspace:

```bash
uv run wv workspace show
uv run wv workspace validate
uv run wv workspace migrate
```

`workspace migrate` upgrades an existing database. The current geography-first
schema is a clean break: a populated legacy workspace is refused rather than
being reset silently. Back up and recreate that workspace intentionally.

## 2. Configure Geography

Every ingest belongs to one monitoring site. A site belongs permanently to one
monitoring area and requires latitude and longitude.

Create an area and site:

```bash
uv run wv monitoring-area create --name "Rancho El Cascabel"

uv run wv monitoring-site create \
  --area RANCHO_EL_CASCABEL \
  --name "Fallen tree in riverbank" \
  --latitude 28.550981 \
  --longitude -101.140348 \
  --description "Large fallen tree beside the river"
```

IDs are generated from names as uppercase ASCII words joined by underscores:

```text
Rancho El Cascabel       -> RANCHO_EL_CASCABEL
Fallen tree in riverbank -> FALLEN_TREE_IN_RIVERBANK
Árbol caído              -> ARBOL_CAIDO
```

Use `--id` when a different or collision-free ID is needed. Updating a name
does not change its ID:

```bash
uv run wv monitoring-area create --id CASCABEL --name "Rancho El Cascabel"
uv run wv monitoring-site create \
  --id CASCABEL_RIVERBANK_TREE \
  --area CASCABEL \
  --name "Fallen tree in riverbank" \
  --latitude 28.550981 \
  --longitude -101.140348
```

Catalog commands:

```bash
uv run wv monitoring-area list
uv run wv monitoring-area show <AREA_ID>
uv run wv monitoring-area update <AREA_ID> --name "New display name"

uv run wv monitoring-site list
uv run wv monitoring-site list --area <AREA_ID>
uv run wv monitoring-site show <SITE_ID>
uv run wv monitoring-site update <SITE_ID> --notes "Access only after rain"
```

## 3. Optional Device Catalog

Devices are currently independent equipment records. They are not required for
ingestion, SD-card metadata, or session identity.

```bash
uv run wv device create HNT001 \
  --name "North camera" \
  --manufacturer "Stealth Cam" \
  --serial-number "BR-1231"

uv run wv device list
uv run wv device show HNT001
uv run wv device update HNT001 --notes "Uses eight AA batteries"
```

## 4. Prepare An SD Card

An initialized SD card stores only its monitoring site in `<sd>/.wv/config.yml`.
It must be initialized from an active workspace so the site can be validated.

```bash
uv run wv sd init /Volumes/TRAIL_CARD \
  --monitoring-site FALLEN_TREE_IN_RIVERBANK

uv run wv sd show /Volumes/TRAIL_CARD
uv run wv sd update /Volumes/TRAIL_CARD \
  --monitoring-site BORDER_FENCE_TRAIL
uv run wv sd clear /Volumes/TRAIL_CARD
```

`sd clear` removes only the card's `.wv/config.yml` file. It does not delete image files.

## 5. Ingest Images

Ingest creates a persisted session and an `init/` directory under the workspace.
New session directory names use:

```text
YYYYMMDD_HHMMSS__MONITORING_SITE
```

Supported input files are regular `.jpg` and `.jpeg` images. Symbolic links are
rejected. Image names use capture time, site ID, and a short content digest:

```text
YYYYMMDD_HHMMSS__MONITORING_SITE__DIGEST.jpg
```

Ingest from an initialized SD card:

```bash
uv run wv ingest sd /Volumes/TRAIL_CARD --mode drain --recursive
```

Ingest any folder by selecting its site explicitly:

```bash
uv run wv ingest folder ~/Downloads/trail-card \
  --monitoring-site FALLEN_TREE_IN_RIVERBANK \
  --mode copy \
  --recursive
```

Modes and useful options:

| Option | Meaning |
| --- | --- |
| `--mode drain` | Copy and verify each image, then remove its source file. |
| `--mode copy` | Copy and verify each image while retaining its source file. |
| `--recursive` | Include nested folders, excluding `.wv` metadata folders. |
| `--dry-run` | Preview counts and destinations without creating a session or changing files. |

## 6. Discover And Inspect Sessions

Use the database, rather than manually browsing directories, to find a session:

```bash
uv run wv session list
uv run wv session list --area RANCHO_EL_CASCABEL
uv run wv session list --monitoring-site FALLEN_TREE_IN_RIVERBANK
uv run wv session list --ingest-status completed --limit 20
```

`session list` displays a table with these columns:

```text
SESSION ID  STARTED AT  SITE ID  PROCESSING STATUS
```

`PROCESSING STATUS` is derived from persisted managed-stage records. Incomplete
sessions, including recoverable and failed work, are listed before cleanly
completed sessions; each group remains newest-first. Use
`session status` for ingest status, filesystem health, detailed stage counters,
and the next permitted action.

Then inspect its status:

```bash
uv run wv session status <SESSION_ID>
```

Status reports ingest counters, area/site identity, database inventory counts,
the four ordered process states, the next permitted action, stored retry
parameters, and filesystem health.

## 7. Run The Managed Pipeline

The managed pipeline performs these ordered stages:

1. `clean_corrupted`
2. `clean_overexposed_ir`
3. `clean_bursts`
4. `detect_content`

Run every eligible stage for a session:

```bash
uv run wv pipeline run <SESSION_ID>
```

Run exactly one stage or stop inclusively after a boundary:

```bash
uv run wv pipeline run <SESSION_ID> --next
uv run wv pipeline run <SESSION_ID> --until bursts
```

Accepted `--until` values are `corrupted`, `overexposed-ir`, `bursts`, and
`detect-content`. `--next` and `--until` are mutually exclusive.

If a previous managed stage was interrupted, confirm that it is no longer
running and recover its durable plan:

```bash
uv run wv pipeline run <SESSION_ID> --recover
```

The pipeline stops after any file failure. Inspect status and retry with the
same parameters before proceeding. Retries and recovery reuse persisted stage
parameters; providing conflicting override values is rejected.

New stages use code defaults. Override them when needed:

```bash
uv run wv pipeline run <SESSION_ID> \
  --mean-threshold 210 \
  --std-threshold 20 \
  --burst-gap-threshold 30 \
  --similarity-threshold 7 \
  --model MDV5A \
  --confidence-threshold 0.7 \
  --ambiguity-gap 0.2 \
  --batch-size 4
```

Individual managed stages remain available when a targeted operation is useful:

```bash
uv run wv session clean corrupted <SESSION_ID>
uv run wv session clean overexposed-ir <SESSION_ID>
uv run wv session clean bursts <SESSION_ID>
uv run wv session detect content <SESSION_ID>
```

## 8. Review Detection Results

The review GUIs operate on a managed session after content detection completes:

```bash
uv run wv gui review-detection <SESSION_ID> --detection animal --pending-only
uv run wv gui favorites <SESSION_ID> --pending-only
```

Both GUI commands offer shell completion for reviewable session IDs. The
`--detection` option also completes `animal`, `human`, `vehicle`, `domestic`,
`empty`, and `other`.

`gui review-detection` records the verified detection in the session database
and moves a relabeled image into its corresponding detection directory. `gui
favorites` records a favorite decision for animal images in the session database
without modifying or moving the image files.

## 9. Export Curated Images

Export favorited animal images:

```bash
uv run wv export favorites <SESSION_ID>
uv run wv export favorites <SESSION_ID> --output ~/Exports/cascabel
uv run wv export favorites <SESSION_ID> --dry-run
```

## Standalone Filesystem Commands

These commands process only `.jpg` and `.jpeg` files directly inside `SOURCE`; they
do not search subdirectories. They do not require an active workspace or update
managed session state. Detection dry runs still load the model and run inference,
but do not move files or write EXIF metadata. Use them only for ad hoc directories
outside the managed workflow:

```bash
uv run wv clean corrupted <SOURCE> --output <SESSION_PATH>
uv run wv clean overexposed-ir <SOURCE> --output <SESSION_PATH>
uv run wv clean bursts <SOURCE> --output <SESSION_PATH>
uv run wv detect content <SOURCE> --output <SESSION_PATH>
```

## Configuration And Setup

Workspace configuration commands manage workspace metadata and validation:

```bash
uv run wv config init
uv run wv config list
uv run wv config get <KEY>
uv run wv config set <KEY> <VALUE>
uv run wv config reset <KEY>
uv run wv config validate
uv run wv config path
```

`config list` prints the known active-workspace settings and their current values.
Unknown compatibility keys are not listed.

All list commands render human-readable tables. `config list` shows `KEY` and
`VALUE`; device and monitoring-area lists show their ID and name; monitoring-site
lists show site ID, area ID, and name. Long values are ellipsized to fit the terminal.

Managed processing defaults are stored in `.wv/config.yml` and may be changed
with `wv config set`. A command option overrides the workspace value for a new
stage. Retries and recovery always use their recorded process parameters.

```yaml
processing:
  overexposed_ir:
    mean_threshold: 200.0
    std_threshold: 25.0
    high_level: 220
    pct_high_threshold: 0.6
  bursts:
    burst_gap_threshold: 60
    similarity_threshold: 5
  detection:
    model: MDV5A
    speciesnet_model: kaggle:google/speciesnet/pyTorch/v4.0.3a/1
    batch_size: 4
    domestic_taxon_ids: []
```

Existing version 1 workspaces must be upgraded with `uv run wv workspace migrate`.
The standalone filesystem commands do not read workspace processing settings.

Prepare models selected by the active workspace. This creates the isolated
SpeciesNet runtime and can download model artifacts:

```bash
uv run wv models setup --megadetector v5a --speciesnet v4.0.3a
```

Use `uv run wv models list` to see supported aliases and `uv run wv models status`
to verify the selected models before processing sessions.

## Command Reference

```text
wv workspace {init,activate,migrate,show,validate}
wv config {init,list,get,set,reset,validate,path}
wv monitoring-area {create,list,show,update}
wv monitoring-site {create,list,show,update}
wv device {create,list,show,update}
wv sd {init,show,update,clear}
wv ingest {sd,folder}
wv models {list,setup,status}
wv session {list,status,clean,detect}
wv pipeline run
wv gui {review-detection,favorites}
wv export favorites
wv clean {corrupted,overexposed-ir,bursts}
```
