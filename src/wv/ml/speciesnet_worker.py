"""Executable side of the isolated SpeciesNet adapter."""

import json
import sys
from pathlib import Path


def main(request_path: Path, result_path: Path) -> None:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if request["operation"] == "prepare":
        result_path.write_text(json.dumps(_prepare(request["model"])), encoding="utf-8")
        return
    result_path.write_text(json.dumps(_evaluate(request)), encoding="utf-8")


def _prepare(model: str) -> dict:
    from speciesnet.classifier import SpeciesNetClassifier
    from wv.core.files import get_content_digest

    classifier = SpeciesNetClassifier(model)
    taxonomy_ids = []
    with classifier.model_info.taxonomy.open("r", encoding="utf-8") as handle:
        taxonomy_ids = [line.split(";", 1)[0] for line in handle if line.strip()]
    return {
        "requested_model": model,
        "classifier_path": str(classifier.model_info.classifier),
        "classifier_digest": get_content_digest(classifier.model_info.classifier),
        "model_version": classifier.model_info.version,
        "inference_device": str(classifier.device).upper(),
        "taxonomy_ids": taxonomy_ids,
    }


def _evaluate(request: dict) -> dict:
    import pycountry
    import reverse_geocoder
    import torch
    from PIL import Image, ImageOps
    from speciesnet.classifier import SpeciesNetClassifier
    from speciesnet.ensemble import SpeciesNetEnsemble
    from speciesnet.geofence_utils import geofence_animal_classification, roll_up_labels_to_first_matching_level
    from speciesnet.geolocation import find_admin1_region
    from speciesnet.utils import BBox

    classifier = SpeciesNetClassifier(request["model"])
    ensemble = SpeciesNetEnsemble(request["model"], geofence=True)
    latitude = float(request["latitude"])
    longitude = float(request["longitude"])
    location = reverse_geocoder.search((latitude, longitude), mode=1, verbose=False)[0]
    country_record = pycountry.countries.get(alpha_2=location["cc"])
    country = country_record.alpha_3 if country_record else None
    admin1 = find_admin1_region(country=country, latitude=latitude, longitude=longitude)
    values = []
    requests = request["requests"]
    for start in range(0, len(requests), int(request["batch_size"])):
        batch = requests[start : start + int(request["batch_size"])]
        paths, images = [], []
        for item in batch:
            with Image.open(item["path"]) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                bbox = BBox(*[float(value) for value in item["bbox"]])
                images.append(classifier.preprocess(image, [bbox]))
            paths.append(f"{item['path']}:{item['index']}")
        with torch.inference_mode():
            predictions = classifier.batch_predict(paths, images)
        for item, prediction in zip(batch, predictions, strict=True):
            classes = prediction["classifications"]["classes"]
            scores = [float(value) for value in prediction["classifications"]["scores"]]
            raw = [_parse(label, score, rank) for rank, (label, score) in enumerate(zip(classes, scores, strict=True), start=1)]
            label, score, _ = geofence_animal_classification(
                labels=classes, scores=scores, country=country, admin1_region=admin1,
                taxonomy_map=ensemble.taxonomy_map, geofence_map=ensemble.geofence_map, enable_geofence=True,
            )
            if score < 0.65:
                rollup = roll_up_labels_to_first_matching_level(
                    labels=classes, scores=scores, country=country, admin1_region=admin1,
                    target_taxonomy_levels=["species", "genus", "family", "order", "class", "kingdom"],
                    non_blank_threshold=0.65, taxonomy_map=ensemble.taxonomy_map,
                    geofence_map=ensemble.geofence_map, enable_geofence=True,
                )
                if rollup is not None:
                    label, score, _ = rollup
            final = _parse(str(label), float(score), 0)
            values.append({
                "path": item["path"], "index": item["index"], "predictions": raw,
                "final_taxon_id": final["taxon_id"], "final_taxon_rank": _rank(final),
                "final_taxon_confidence": final["confidence"],
            })
    return {"model": _prepare(request["model"]), "results": values}


def _parse(label: str, confidence: float, rank: int) -> dict:
    parts = label.split(";")
    if len(parts) != 7:
        return {"rank": rank, "taxon_id": label, "taxon_class": None, "taxon_order": None, "taxon_family": None, "taxon_genus": None, "taxon_species": None, "common_name": None, "confidence": confidence}
    return {"rank": rank, "taxon_id": parts[0], "taxon_class": parts[1] or None, "taxon_order": parts[2] or None, "taxon_family": parts[3] or None, "taxon_genus": parts[4] or None, "taxon_species": parts[5] or None, "common_name": parts[6] or None, "confidence": confidence}


def _rank(value: dict) -> str | None:
    for key, rank in (("taxon_species", "species"), ("taxon_genus", "genus"), ("taxon_family", "family"), ("taxon_order", "order"), ("taxon_class", "class")):
        if value[key]:
            return rank
    return "kingdom" if value["common_name"] == "animal" else None


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
