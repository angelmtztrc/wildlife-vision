# wildlife-vision

An offline-first set of automated image pipelines for managing, organizing, reviewing, and curating images captured by trail and hunting cameras.

The project is designed for large batches of wildlife photos collected from cameras placed in ranches, rural areas, and natural environments. Its goal is to reduce the manual effort required to review thousands of images while preserving the photos that are useful for long-term storage, research, species tracking, and publication on platforms such as iNaturalist.

## Purpose

Trail and hunting cameras can produce hundreds or thousands of images in a short period of time. Many of those images are empty, highly similar, overexposed, blurry, or simply not useful.

Manually curating large image batches requires a significant amount of time and attention. `wildlife-vision` provides a structured pipeline for:

1. Importing and organizing trail and hunting camera images.
2. Preserving original image information and metadata.
3. Detecting animal, human, vehicle, empty, and other image types.
4. Reducing redundant images from bursts and near-duplicate sequences.
5. Helping the user decide which animal photos should be published, kept, or rejected.
6. Producing summaries and export-ready data for further review, research, or publication.
