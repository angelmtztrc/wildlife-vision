# 🦉 Wildlife Vision

An offline-first set of automated image pipelines for wildlife trail camera photos. This toolset helps you organise, detect, and classify images using metadata and models to identify content in photos, making it easy to handle your photos for long-term storage and further research and tagging.

## Set Up

> You must have Python 3 installed in your computer to use this project.

After cloning the repository, you should install the needed dependencies for using this project, ideally you will have to do this only once.

Run the following command in your terminal. Make sure to be in the root directory of the project.

```sh
pip install -r requirements.txt
```

> If you intent to use the training model scripts offline, make sure to change `weights` param to `None`.

## Usage

Once you install all dependencies you are free to run all the scripts using the following command:

```sh
python3 scripts/name_of_script_you_want_to_run.py
```

Some of the scripts may receive additional args. Read the table bellow to know how to run correctly the scripts.

| Script              | Usage                                  | Args                                                                                   | Description                                                                                                                                                             |
| ------------------- | -------------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| camshots_organiser  | python3 scripts/camshots_organiser.py  | `--generate-subfolders` Allows to generate YYYYMMDD subfolders for better organisation | Script that organises all photos of the given input folder, renaming all the photos with the YYYYMMDD_HHMMSS_Location format and moving them to an output folder.       |
| detection_organiser | python3 scripts/detection_organiser.py |                                                                                        | Script that organises all photos of the given input folder based in the Detection attribute and moving them to the output folder organising them by animal/empty/object |
| predict_photo       | python3 scripts/predict_photo.py       |                                                                                        | Script that predict if the given input photo fits into the classes animal/empty/object                                                                                  |
| train_classifier    | python3 scripts/train_classifier       |                                                                                        | Script that trains the animal_classifier model using the photos stored in dataset using the classes animal/empty/object                                                 |

### Graphical User Interfaces

This project contains GUI's created to make easy chores like manual categorisation and so on. You can run them using the following command:

```sh
python3 -m gui.photo_tagger
```

Here is the description of each GUI available:

| File         | Description                                                                                                                                                                                                                                             |
| :----------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| photo_tagger | Created to set the Detection tag for photos stored in the selected folder. Use 1, 2, 3 (empty, animal, object) to set the corresponding value to the Detection tag. The use of left/right arrow is available for returning or going to the next photo.) |

## Tag system

The entire project uses the ImageDescription exiftag to store tags that helps the script identify important information for the given photo. The tags are stored in `ImageDescription` using the format `TagName=TagValue;TagName=TagValue;`. The list of used Tags is listed bellow:

| Tag       | Definition                                                                                                                         |
| :-------- | :--------------------------------------------------------------------------------------------------------------------------------- |
| Detection | Determines the detection value of the photo, which currently is represented using animal, empty or object.                         |
| Location  | Determines the location of the camera, helps with organisation of the pictures. The camshots_organiser alters this tag by default. |
| Specie    | Contains the scientific name of the Specie that appears in the photo.                                                              |

> This list contains the current used tags, but more would be added depending of the goals of the project.
