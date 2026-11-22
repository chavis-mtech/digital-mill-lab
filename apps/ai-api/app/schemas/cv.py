"""Computer Vision FFB grading - RESEARCH PROTOTYPE (owner: ml). No fake accuracy."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiModel, FeatureStatus


class CvPrototypeResponse(ApiModel):
    status: FeatureStatus = FeatureStatus.prototype
    filename: str
    content_type: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    image_stats: dict = Field({}, description="Deterministic image statistics (e.g. colour histogram summary)")
    assessment: str = Field(description="Prototype output text; never presented as a validated grade")
    validated: bool = False
    requires_human_review: bool = True
    disclaimer: str = (
        "Research prototype. No properly licensed labelled FFB dataset was used; this is not a validated grader."
    )


class CvProtocolResponse(ApiModel):
    status: FeatureStatus = FeatureStatus.prototype
    dataset_requirements: list[str]
    camera_position: str
    lighting: str
    labelling_protocol: list[str]
    class_definitions: dict[str, str]
    evaluation_plan: list[str]
    pilot_validation_plan: list[str]
