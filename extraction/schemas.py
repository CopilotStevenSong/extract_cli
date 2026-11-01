"""Pydantic models the model's reply must match.

Strict mode makes every field required, so optional values are written as
Optional[...] without defaults (the model returns null).
"""
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class ActionItem(BaseModel):
    task: str = Field(description="What needs to be done")
    owner: Optional[str] = Field(description="Person responsible, or null if not stated")
    due_date: Optional[str] = Field(description="Due date as YYYY-MM-DD, or null if not stated")


class TicketRecord(BaseModel):
    customer_name: Optional[str]
    product: Optional[str]
    category: str = Field(description="Short category, e.g. bug, outage, billing, access, feature request")
    summary: str = Field(description="One-sentence summary of the problem")
    priority: Priority
    sentiment_score: int = Field(description="Customer mood from 1 (angry) to 5 (happy)")
    steps_to_reproduce: list[str]
    action_items: list[ActionItem]


class EmailIntent(str, Enum):
    request = "request"
    complaint = "complaint"
    info = "info"
    scheduling = "scheduling"
    other = "other"


class EmailRecord(BaseModel):
    sender: Optional[str]
    recipients: list[str]
    subject: Optional[str]
    sent_date: Optional[str] = Field(description="Date sent as YYYY-MM-DD, or null if not stated")
    summary: str = Field(description="One-sentence summary of the email")
    intent: EmailIntent
    people: list[str] = Field(description="Names of people mentioned")
    organizations: list[str] = Field(description="Companies or teams mentioned")
    action_items: list[ActionItem]


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogEvent(BaseModel):
    timestamp: Optional[str] = Field(description="ISO 8601 timestamp, or null if the line has none")
    level: LogLevel
    component: Optional[str] = Field(description="Service, module or logger name, or null")
    message: str = Field(description="The log message; fold stack traces into the event they belong to")
    error_code: Optional[str] = Field(description="Error code, exception type or HTTP status, or null")


class LogRecord(BaseModel):
    summary: str = Field(description="One-sentence summary of what happened")
    events: list[LogEvent]
    probable_root_cause: Optional[str] = Field(description="Most likely root cause, or null if no errors")


class DocKind(BaseModel):
    kind: Literal["email", "log", "ticket"]
