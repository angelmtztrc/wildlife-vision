from sqlalchemy import delete, select
from sqlalchemy.orm import Session as SqlSession

from wv.domain.session import (
    ImageDetectionResult,
    ImageObjectDetection,
    ImageTaxonPrediction,
)
from wv.persistence.models.session_image import (
    ImageDetectionResultModel,
    ImageObjectDetectionModel,
    ImageTaxonPredictionModel,
)


class ImageDetectionResultRepository:
    """Persist normalized MegaDetector and SpeciesNet results for session images."""

    def __init__(self, sql_session: SqlSession):
        self.sql_session = sql_session

    def replace_many(self, results: list[ImageDetectionResult]) -> None:
        """Replace stored machine results for the supplied image IDs.

        Args:
            results: Complete image-level inference results to persist.

        Side Effects:
            Deletes existing child predictions and detections for supplied images,
            then inserts the supplied immutable machine results.
        """
        image_ids = [result.image_id for result in results]
        if not image_ids:
            return
        detection_ids = self.sql_session.scalars(
            select(ImageObjectDetectionModel.id).where(
                ImageObjectDetectionModel.image_id.in_(image_ids)
            )
        ).all()
        if detection_ids:
            self.sql_session.execute(
                delete(ImageTaxonPredictionModel).where(
                    ImageTaxonPredictionModel.object_detection_id.in_(detection_ids)
                )
            )
        self.sql_session.execute(
            delete(ImageObjectDetectionModel).where(
                ImageObjectDetectionModel.image_id.in_(image_ids)
            )
        )
        self.sql_session.execute(
            delete(ImageDetectionResultModel).where(
                ImageDetectionResultModel.image_id.in_(image_ids)
            )
        )

        for result in results:
            self.sql_session.add(
                ImageDetectionResultModel(
                    image_id=result.image_id,
                    predicted_label=result.predicted_label,
                    predicted_confidence=result.predicted_confidence,
                    decision_source=result.decision_source,
                    megadetector_model=result.megadetector_model,
                    speciesnet_model=result.speciesnet_model,
                    speciesnet_model_version=result.speciesnet_model_version,
                    latitude=result.latitude,
                    longitude=result.longitude,
                    failure_message=result.failure_message,
                )
            )
            for detection in result.detections:
                self._add_detection(detection)
        self.sql_session.flush()

    def list_for_images(self, image_ids: list[str]) -> list[ImageDetectionResult]:
        """Return stored machine results and ranked taxonomy predictions by image."""
        if not image_ids:
            return []
        result_models = self.sql_session.scalars(
            select(ImageDetectionResultModel)
            .where(ImageDetectionResultModel.image_id.in_(image_ids))
            .order_by(ImageDetectionResultModel.image_id)
        ).all()
        detections = self.sql_session.scalars(
            select(ImageObjectDetectionModel)
            .where(ImageObjectDetectionModel.image_id.in_(image_ids))
            .order_by(ImageObjectDetectionModel.image_id, ImageObjectDetectionModel.id)
        ).all()
        predictions = self.sql_session.scalars(
            select(ImageTaxonPredictionModel)
            .where(
                ImageTaxonPredictionModel.object_detection_id.in_(
                    [detection.id for detection in detections]
                )
            )
            .order_by(ImageTaxonPredictionModel.object_detection_id, ImageTaxonPredictionModel.rank)
        ).all() if detections else []
        predictions_by_detection: dict[str, list[ImageTaxonPrediction]] = {}
        for prediction in predictions:
            predictions_by_detection.setdefault(prediction.object_detection_id, []).append(
                _to_prediction(prediction)
            )
        detections_by_image: dict[str, list[ImageObjectDetection]] = {}
        for detection in detections:
            detections_by_image.setdefault(detection.image_id, []).append(
                ImageObjectDetection(
                    id=detection.id,
                    image_id=detection.image_id,
                    category=detection.category,
                    confidence=detection.confidence,
                    bbox_x=detection.bbox_x,
                    bbox_y=detection.bbox_y,
                    bbox_width=detection.bbox_width,
                    bbox_height=detection.bbox_height,
                    final_taxon_id=detection.final_taxon_id,
                    final_taxon_rank=detection.final_taxon_rank,
                    final_taxon_confidence=detection.final_taxon_confidence,
                    predictions=predictions_by_detection.get(detection.id, []),
                )
            )
        return [
            ImageDetectionResult(
                image_id=model.image_id,
                predicted_label=model.predicted_label,
                predicted_confidence=model.predicted_confidence,
                decision_source=model.decision_source,
                megadetector_model=model.megadetector_model,
                speciesnet_model=model.speciesnet_model,
                speciesnet_model_version=model.speciesnet_model_version,
                latitude=model.latitude,
                longitude=model.longitude,
                failure_message=model.failure_message,
                detections=detections_by_image.get(model.image_id, []),
            )
            for model in result_models
        ]

    def _add_detection(self, detection: ImageObjectDetection) -> None:
        self.sql_session.add(
            ImageObjectDetectionModel(
                id=detection.id,
                image_id=detection.image_id,
                category=detection.category,
                confidence=detection.confidence,
                bbox_x=detection.bbox_x,
                bbox_y=detection.bbox_y,
                bbox_width=detection.bbox_width,
                bbox_height=detection.bbox_height,
                final_taxon_id=detection.final_taxon_id,
                final_taxon_rank=detection.final_taxon_rank,
                final_taxon_confidence=detection.final_taxon_confidence,
            )
        )
        for prediction in detection.predictions:
            self.sql_session.add(
                ImageTaxonPredictionModel(
                    id=f"{detection.id}:{prediction.rank}",
                    object_detection_id=detection.id,
                    rank=prediction.rank,
                    taxon_id=prediction.taxon_id,
                    taxon_class=prediction.taxon_class,
                    taxon_order=prediction.taxon_order,
                    taxon_family=prediction.taxon_family,
                    taxon_genus=prediction.taxon_genus,
                    taxon_species=prediction.taxon_species,
                    common_name=prediction.common_name,
                    confidence=prediction.confidence,
                )
            )


def _to_prediction(model: ImageTaxonPredictionModel) -> ImageTaxonPrediction:
    return ImageTaxonPrediction(
        rank=model.rank,
        taxon_id=model.taxon_id,
        taxon_class=model.taxon_class,
        taxon_order=model.taxon_order,
        taxon_family=model.taxon_family,
        taxon_genus=model.taxon_genus,
        taxon_species=model.taxon_species,
        common_name=model.common_name,
        confidence=model.confidence,
    )
