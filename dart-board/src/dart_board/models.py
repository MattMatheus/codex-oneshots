from typing import Optional

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    user_id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class UserOut(BaseModel):
    user_id: str
    name: str
    created_at: str


class SessionCreate(BaseModel):
    session_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    source_ref: Optional[str] = None


class SessionOut(BaseModel):
    session_id: str
    user_id: str
    started_at: str
    ended_at: Optional[str]
    source_ref: Optional[str]


class ThrowCreate(BaseModel):
    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    x_norm: float = Field(ge=0.0, le=1.0)
    y_norm: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class ThrowOut(BaseModel):
    id: int
    user_id: str
    session_id: str
    ts: str
    x_norm: float
    y_norm: float
    confidence: float


class CheckoutSuggestion(BaseModel):
    score: int
    combinations: list[list[str]]


class FinishAdviceOut(BaseModel):
    user_id: str
    current_score: int
    can_finish: bool
    combinations: list[list[str]]


class CaptureStartRequest(BaseModel):
    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    camera_index: int = Field(default=0, ge=0)
    fps: int = Field(default=10, ge=1, le=60)


class CaptureStatusOut(BaseModel):
    running: bool
    user_id: Optional[str]
    session_id: Optional[str]
    camera_index: Optional[int]
    fps: int
    frames_processed: int
    throws_detected: int
    last_error: Optional[str]


class CalibrationSetRequest(BaseModel):
    # Source points order: top-left, top-right, bottom-right, bottom-left
    src_points: list[list[float]] = Field(min_length=4, max_length=4)


class CalibrationStatusOut(BaseModel):
    calibrated: bool
    target_size: int
    src_points: Optional[list[list[float]]]
