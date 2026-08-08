# wildlife-vision

## Introduction

An offline-first set of automated image pipelines for managing, organizing, reviewing, and curating images captured by trail and hunting cameras.

The project is designed for large batches of wildlife photos collected from cameras placed in ranches, rural areas, and natural environments. Its goal is to reduce the manual effort required to review thousands of images while preserving the photos that are useful for long-term storage, research, species tracking, and publication on platforms such as iNaturalist.

## Motivation

I have been monitoring various sites in the area where I live, intending to help the scientific community by capturing images of wildlife. This has not come easy in any way possible; the main problem I encountered was the number of images I could get from one camera, or even worse, from several. At every trip to extract the images from my cameras every week, I always ended up having a folder with **thousands** of pictures that needed to be reviewed one by one to determine which ones would be suitable to be posted on iNaturalist.

Because of this, I decided to create a project that solves many problems I encounter when handling those images; that’s why the project provides the following features:

1. Importing and organizing images: Automatically move the files from an input path to an established destination, and it renames the files using a suitable format.
2. Clean up: It provides a set of commands that allow flagging corrupted, redundant, and overexposed images.
3. Auto-detection: Use the mega-detector model to automatically detect the content of every image and sort them into animal, human, empty, and other categories.
4. Manual verification: It provides a clear and easy-to-use interface to manually review the result of the detection process to verify or correct any misdetection.
5. Exporting: It provides a set of commands to allow you to export those ready-to-use images for publishing or further research.

## Definition

### Workspace

A workspace is a given filesystem path that serves as the output directory for the sessions generated using the `ingestion` process.

Workspaces can be created using the command:

```bash
wv workspace init <PATH>
```

When a workspace is initialized, the command would do the following:

1. Resolve the absolute path.
2. Verify that the directory is accessible and writable.
3. Create the needed folders, which are: `sessions`, `models`, `exports`.
4. Initialize and migrate SQLite
5. Create the configuration file
6. Activates the workspace

The project would be prepared to only handle one workspace; there would not be commands or functionality to “switch” between created workspaces.

Additional commands would be:

```bash
wv workspace show # returns formatted information of the workspace
wv workspace migrate # applies pending Alembic migrations to the active workspace database
wv workspace validate # ensures the workspace is accessible and its database is up to date
```

`wv workspace migrate` upgrades only the configured workspace's existing
`.wv/database.sqlite` database to the packaged Alembic head. It is forward-only
and idempotent: a database already at the current revision is left unchanged.
It does not create a missing database, migrate workspace configuration or
directories, or create an automatic backup.

### Configuration

Once a workspace is created, a `config.yml` file will be available within the workspace.

This file will contain all the needed configuration for every process that would be run; the configuration will contain the following:

```yaml
schema_version: 1

processing:
  overexposed_ir:
    mean_threshold: 200.0
    std_threshold: 25.0
    high_level: 220
    pct_high_threshold: 0.60

  bursts:
    burst_gap_seconds: 60
    similarity_threshold: 5

  detection:
    model: "MDV5A"
    confidence_threshold: 0.80
    ambiguity_gap: 0.30
    batch_size: 32

runtime:
  continue_on_file_error: true
```

This would allow the running of processes like `overexposed_ir` to point to this configuration as default values.

If, for any reason, the configuration file is missing or invalid, the CLI will automatically switch to and retrieve the default values defined in the code.

Available commands for this feature will be:

```bash
wv config init # it creates/replace the config file of the workspace
wv config get <KEY> # it returns the value of a certain config property
wv config set <KEY> <VALUE> # it sets the value of a certain config property
wv config reset <KEY> # it sets the default value of a certain config property
wv config validate # it verifies if the active config is valid for use
wv config path # it returns the path of the config
```

### Monitoring areas and sites

Monitoring areas are large geographic catalogs such as ranches, reserves, or properties. Each monitoring site is one fixed geographic location inside exactly one area and must include latitude and longitude.

```bash
wv monitoring-area create --name "Rancho El Cascabel"
wv monitoring-site create \
  --area RANCHO_EL_CASCABEL \
  --name "Fallen tree in riverbank" \
  --latitude 28.550981 \
  --longitude -101.140348
```

Area and site identifiers are generated from `--name` as uppercase ASCII words
joined with underscores. Use `--id <IDENTIFIER>` when a collision or a preferred
identifier requires an override. Updating a name does not change its ID.

A monitoring site can be created using the following command and options.

```bash
wv site create <ID> \
	--name "El Viejo Ranch - Westside Creek" \ # only required value
	--description "Mesquite are approximately 20 meters east" \
	--latitude 28.550981 \
	--longitude -101.140348 \
	--elevation 310 \
	--notes "Password is 1234"
```

To manage monitoring sites, we provide the following commands:

```bash
wv monitoring-area {create,list,show,update}
wv monitoring-site {create,list,show,update}
wv monitoring-site list --area <AREA_ID>
```

### Devices

The devices feature is an independent equipment catalog. Devices are not required for ingestion or SD-card metadata.

To create a device, the following command is available:

```bash
wv device create <ID> \
	--name "Red camera" \
	--manufacturer "Stealth cam"
	--model "SC-2131"
	--serial-number "BR-1231"
	--notes "It uses 8 batteries"
```

We also provide several commands for managing the information of your devices, which are:

```bash
wv device list # returns the available devices
wv device show <ID> # returns the information of a certain device
wv device update <ID> --name <DISPLAY_NAME> # update the monitoring information
wv device delete <ID> # soft-deletes a device
```

### SD

The SD feature stores the monitoring site represented by a card. The created file is stored inside `.wv/config.yml`.

The purpose of this command is to pair it with the `wv ingest sd` command, which would automatically read the information under the `config.yml` to recover the information of the device and monitoring site, saving time by not having to write those values manually.

To initialize an SD card, you must run:

```bash
wv sd init <PATH> --monitoring-site <MONITORING_SITE_ID>
```

We also provide additional helpful commands:

```bash
wv sd show <PATH> # returns the information of the SD card
wv sd update <PATH> --monitoring-site <MONITORING_SITE_ID>
wv sd clear <PATH> # it clears the configuration file
```

### Ingestion

The ingestion process happens when an input filesystem path, the system will iterate through the files of that path and look for valid image files. The criteria used for this are as follows:

1. Is a readable and accessible file
2. Its extension is any of the following: `.jpg`, `.jpeg`, `.png`, `.heic`

When a file is a valid image file, the system will then proceed to prepare the new name of the file, which would be composed using the pattern: `YYYYMMDD_HHMMSS__MONITORING_SITE__UUID`

Once the image file has been prepared, the following will happen:

1. A folder within the workspace sessions will be created using the name: `YYYYMMDD_HHMMSS__MONITORING_SITE`
2. The image will be safely copied into the generated session folder under the `init/` folder.
3. Once the image file has been copied, verify that it was copied correctly. If it is, the following outcomes can happen depending on what mode was selected: `drain` or `copy`
   1. When `drain` mode, the system will remove the original file from the input path once the image file has been copied and verified.
   2. When `copy` mode, the system will not perform additional operations; the original files located in the input path will be preserved.

Available commands for this feature are:

```bash
wv ingest sd <PATH> --mode <drain | copy> # automatically reads the .wv/config.yml of an SD card
wv ingest folder <PATH> --monitoring-site <MONITORING_SITE> --mode <drain | copy>
```

Complete list of available options

| Option           | Value   | Description                                                                                                                                                                   |
| ---------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| —device          | string  | device                                                                                                                                                                        | The name of the device the image files belong to or where extracted from.                                                                                  |
| —monitoring-site | string  | monitoring_site                                                                                                                                                               | The name of the monitoring device the images files where taken from.                                                                                       |
| —mode            | “drain” | “copy”                                                                                                                                                                        | The extraction mode the system would use. `drain` will remove the original files from the source once the process has finished. `copy` will preserve them. |
| —recursive       | boolean | When `true` it will iterate throught every folder in the given source to find image files, when `false` it will only look for image files at first level of the given source. |
| —dry-run         | boolean | When `true` the command will no perform write operations, and it will only return the expected operations to be done.                                                         |

### Pipeline

The pipeline feature is probably the most useful and important feature of this project; it basically uses a session (created by the ingestion process) and runs the following processes:

1. **Corruption clean-up**: It iterates inside the `init/` folder of a session, verifies every image file there, and moves into `ignored/corrupted/` the corrupted files. A corrupted file is any file that cannot be loaded, accessed, or opened.
2. **Overexposed IR clean-up**: Using an algorithm with pre-configured values that can be customised, the process basically analyses the images of the `init/` folder that contains a certain amount of white color, producing bad-quality night-vision images. Those images that are flagged as overexposed will be moved into `ignored/overexposed/`
3. **Burst-reduction**: The burst reduction step scans a folder of images and identifies sequences of photos that were likely captured as part of the same rapid burst. It first groups images by monitoring site and capture time, treating photos from the same site taken within a configurable time gap as one burst. For each image in a burst, the system computes a perceptual hash to estimate visual similarity and a simple quality score based on sharpness, contrast, and brightness. Images that look alike are grouped together into similarity clusters. Within each cluster, the highest-quality images are kept, and the lower-ranked duplicates are reduced. Reduced images are moved to `ignored/bursts`, while the best images remain in place.
4. **Auto-detection**: Using the MegaDetector model, images within the `init/` folder are analysed in clusters of configurable sizes; every image would be evaluated and determined if the content of the images belongs to **animal, human, vehicle, empty, or other.** Once evaluated, the image will be moved to `detection/...` based on its detection value. This step is only intended to be used to save time of manual review; it doesn’t determine the exact species; it only provides a way to determine if the image is worth checking.

It’s important to clarify that the pipeline feature is heavily related to sessions, which means you need one to be able to run a pipeline process.

To execute a pipeline, we provide the following commands:

```bash
wv pipeline run <SESSION_ID> # resumes and runs all eligible stages
wv pipeline run <SESSION_ID> --next # runs exactly one eligible stage
wv pipeline run <SESSION_ID> --until bursts # runs inclusively through burst cleanup
wv pipeline run <SESSION_ID> --recover # resumes an interrupted stage
```

The managed pipeline records each stage in the workspace database and stops when
a stage has file failures. Retry that stage before proceeding. `--recover` is
required for an `in_progress` stage; it reuses its durable processing plan.
`--next` and `--until` cannot be combined. Available `--until` stages are
`corrupted`, `overexposed-ir`, `bursts`, and `detect-content`.

### Managed session cleanup

Ingested sessions and their processing progress are recorded in the active
workspace database. Recent sessions can be discovered with:

```bash
wv session list
wv session list --area <AREA_ID>
wv session list --monitoring-site <MONITORING_SITE_ID>
wv session list --ingest-status <STATUS> --limit 20
```

Sessions are shown newest first. Filters can be combined and the default result
limit is 20. Available ingest statuses are `in_progress`, `completed`,
`completed_with_failures`, and `failed`.

Use the session identifier from that list to inspect its operational state:

```bash
wv session status <SESSION_ID>
```

The status command reports ingest counts, ordered processing stages, current
database inventory counts, the next eligible processing action, and filesystem
health. Missing or invalid session paths are reported as diagnostics so failed
or interrupted database records remain inspectable.

Database-tracked cleanup and detection commands require an active workspace and
use that session identifier:

```bash
wv session clean corrupted <SESSION_ID>
wv session clean overexposed-ir <SESSION_ID>
wv session clean bursts <SESSION_ID>
wv session detect content <SESSION_ID>
```

The order is enforced: corrupted cleanup precedes overexposed cleanup, which
precedes burst cleanup. Use `--recover` only after an interrupted managed command;
it reconciles the saved session state before continuing. The standalone `wv clean`
commands remain filesystem-only and do not update session inventory or process
tracking.
