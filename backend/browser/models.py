from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ActionType = Literal[
    "navigate",
    "fill",
    "click",
    "select",
    "upload",
    "checkbox",
    "screenshot",
    "scroll",
]


class ScreenshotResult(BaseModel):
    success: bool
    screenshot_bytes: bytes = b""
    error: str | None = None


class Action(BaseModel):
    step: int
    action: ActionType
    expected_state: str
    field_description: str | None = None
    value: str | None = None
    url: str | None = None
    file_path: str | None = None
    option_value: str | None = None
    selector: str | None = None

    def human_description(self) -> str:
        target = self.field_description or self.url or self.selector or "page"
        if self.action in {"fill", "select", "upload"}:
            value = self.value or self.option_value or self.file_path or ""
            return f"{self.action} {target} with {value}"
        return f"{self.action} {target}"


class ActionValidationResult(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0)
    passed: bool
    observation: str
    error_detected: bool = False
    error_text: str | None = None
    blocking_element: str | None = None
    failure_reason: str | None = None


class ApplicationResult(BaseModel):
    status: str
    stopped_at_step: int | None = None
    paused_at_step: int | None = None
    failure_reason: str | None = None


class RunGuardResult(BaseModel):
    passed: bool
    checks: dict[str, str]


class AgentRuntimeStatus(BaseModel):
    status: Literal["idle", "running", "paused", "error"]
    current_application_id: str | None = None
    current_company: str | None = None
    current_field: str | None = None
    trace_id: str | None = None
    updated_at: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
