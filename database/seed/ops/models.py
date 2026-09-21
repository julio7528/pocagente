"""Validated, JSON-facing models for reusable OPS seed scenarios."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


RunStatus = Literal["SUCCESS", "PARTIAL", "ERROR"]
RequestStatus = Literal["WAITING_RESULT", "COMPLETED", "FAILED"]
ProcessingStatus = Literal["WAITING_RESULT", "RESULT_AVAILABLE", "COMPLETED", "ERROR"]
UploadStatus = Literal["PENDING", "SUCCESS", "ERROR"]
DownloadStatus = Literal["NOT_AVAILABLE", "AVAILABLE", "DOWNLOADED", "ERROR"]
LogStatus = Literal["SUCCESS", "ERROR", "EXCEPTION"]
EntityReference = Literal["email", "attachment", "request", "establishment"]


class _SeedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class SeedEvent(_SeedModel):
    timestamp: datetime
    event: str = Field(min_length=1)
    status: LogStatus
    message: str = Field(min_length=1)
    references: tuple[EntityReference, ...] = ()

    @model_validator(mode="after")
    def timestamp_is_timezone_aware(self) -> "SeedEvent":
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("Event timestamps must be timezone-aware")
        return self


class EmailDefinition(_SeedModel):
    received_at: datetime
    processed_at: datetime
    sender: str = Field(min_length=1)
    recipient: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    attachment_count: int = Field(ge=1)
    sender_status: Literal["VALID"]
    processing_status: Literal["PROCESSED"]


class AttachmentDefinition(_SeedModel):
    file_name: str = Field(min_length=1)
    file_type: str = Field(min_length=1)
    received_at: datetime
    validation_status: Literal["VALID"]
    validation_message: str = Field(min_length=1)
    establishment_count: int = Field(ge=1)
    processing_status: Literal["PROCESSED"]


class EstablishmentDefinition(_SeedModel):
    establishment_number: str = Field(min_length=1)
    generated_file_name: str = Field(min_length=1)
    r1_state_at: datetime
    r1_processing_status: Literal["WAITING_RESULT", "ERROR"]
    r1_upload_status: Literal["SUCCESS", "ERROR"]
    r1_upload_at: datetime | None
    r1_download_status: Literal["NOT_AVAILABLE"]
    available_at: datetime | None
    available_processing_status: Literal["RESULT_AVAILABLE"] | None
    available_download_status: Literal["AVAILABLE"] | None
    final_at: datetime
    final_processing_status: ProcessingStatus
    final_upload_status: UploadStatus
    final_download_status: DownloadStatus
    download_at: datetime | None = None
    return_email_at: datetime | None = None
    result_message: str = Field(min_length=1)


class RequestDefinition(_SeedModel):
    initial_updated_at: datetime
    r1_updated_at: datetime
    r1_status: Literal["WAITING_RESULT", "FAILED"]
    final_updated_at: datetime
    final_status: RequestStatus
    result: str | None = None
    failure_reason: str | None = None
    completed_at: datetime | None = None
    return_email_at: datetime | None = None


class RobotRunDefinition(_SeedModel):
    started_at: datetime
    finished_at: datetime
    status: RunStatus
    result_message: str = Field(min_length=1)
    events: tuple[SeedEvent, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def lifecycle_is_ordered(self) -> "RobotRunDefinition":
        timestamps = (self.started_at, *(event.timestamp for event in self.events), self.finished_at)
        if any(item.tzinfo is None or item.utcoffset() is None for item in timestamps):
            raise ValueError("Run timestamps must be timezone-aware")
        if tuple(sorted(timestamps)) != timestamps:
            raise ValueError("Run timestamps must be chronological")
        return self


class OpsSeedScenario(_SeedModel):
    """A JSON-described cancellation lifecycle supported by the generic executor."""

    scenario_id: str = Field(min_length=1)
    protocol_number: str = Field(min_length=1)
    email: EmailDefinition
    attachment: AttachmentDefinition
    establishment: EstablishmentDefinition
    request: RequestDefinition
    r1: RobotRunDefinition
    r2: RobotRunDefinition | None = None

    @model_validator(mode="after")
    def lifecycle_is_consistent(self) -> "OpsSeedScenario":
        for value in self._timestamps():
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Scenario timestamps must be timezone-aware")
        expected_r1_events = 10 if self.r1.status == "SUCCESS" else 11
        if len(self.r1.events) != expected_r1_events:
            raise ValueError(f"R1 must contain exactly {expected_r1_events} lifecycle events for this outcome")
        if self.r1.status == "ERROR":
            if self.request.r1_status != "FAILED":
                raise ValueError("Failed R1 requires request.r1_status FAILED")
            if self.establishment.r1_processing_status != "ERROR":
                raise ValueError("Failed R1 requires ERROR establishment processing state")
            if self.establishment.r1_upload_status == "ERROR" and self.establishment.r1_upload_at is not None:
                raise ValueError("Failed upload cannot have r1_upload_at")
            if self.r2 is not None:
                raise ValueError("Failed R1 cannot have an R2 definition")
            if self.request.final_status != "FAILED":
                raise ValueError("Failed R1 requires a FAILED final request")
            return self
        if self.r1.status != "SUCCESS":
            raise ValueError("The supported seed lifecycle requires R1 SUCCESS or ERROR")
        if self.r2 is None:
            raise ValueError("Successful R1 requires an R2 definition")
        if self.r2.status == "SUCCESS":
            if len(self.r2.events) != 6:
                raise ValueError("Successful R2 must contain exactly 6 lifecycle events")
            if self.request.final_status != "COMPLETED" or self.request.failure_reason is not None:
                raise ValueError("Successful R2 requires a completed request without failure reason")
            if self.establishment.final_processing_status != "COMPLETED" or self.establishment.final_download_status != "DOWNLOADED":
                raise ValueError("Successful R2 requires completed downloaded establishment state")
            if self.establishment.download_at is None or self.establishment.return_email_at is None:
                raise ValueError("Successful R2 requires download and return-email timestamps")
            if self.request.completed_at is None or self.request.return_email_at is None:
                raise ValueError("Completed request requires completion and return-email timestamps")
        elif self.r2.status == "ERROR":
            if len(self.r2.events) < 5:
                raise ValueError("Failed R2 must contain at least 5 lifecycle events")
            if self.request.final_status != "FAILED" or not self.request.failure_reason:
                raise ValueError("Failed R2 requires a failed request with failure reason")
            if self.request.completed_at is not None:
                raise ValueError("Failed request cannot have completed_at")
            if self.establishment.final_processing_status != "ERROR":
                raise ValueError("Failed R2 requires ERROR establishment processing state")
            if self.establishment.final_download_status == "ERROR":
                if self.establishment.download_at is not None:
                    raise ValueError("Failed download cannot have download_at")
            elif self.establishment.final_download_status == "DOWNLOADED":
                if self.establishment.download_at is None:
                    raise ValueError("Post-download failure requires download_at")
            else:
                raise ValueError("Failed R2 requires ERROR or DOWNLOADED final download state")
            if not any(event.status == "ERROR" for event in self.r2.events):
                raise ValueError("Failed R2 requires ERROR event evidence")
        else:
            raise ValueError("Only SUCCESS or ERROR R2 outcomes are supported")
        return self

    def _timestamps(self) -> tuple[datetime, ...]:
        values: tuple[datetime | None, ...] = (
            self.email.received_at, self.email.processed_at,
            self.attachment.received_at,
            self.establishment.r1_state_at, self.establishment.r1_upload_at,
            self.establishment.available_at, self.establishment.final_at,
            self.establishment.download_at, self.establishment.return_email_at,
            self.request.initial_updated_at, self.request.r1_updated_at,
            self.request.final_updated_at, self.request.completed_at,
            self.request.return_email_at,
        )
        return tuple(value for value in values if value is not None)


class OpsSeedResult(_SeedModel):
    scenario_id: str
    protocol_number: str
    created: bool
    r1_run_id: int | None = None
    r2_run_id: int | None = None
    email_id: int | None = None
    attachment_id: int | None = None
    request_id: int | None = None
    establishment_id: int | None = None
