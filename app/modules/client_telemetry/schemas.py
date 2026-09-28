"""Version 1 of the client observation and definition contracts."""
import math
import re
from datetime import datetime, timezone
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, field_validator, model_validator

MAX_BATCH_BYTES = 48 * 1024
MAX_BATCH_EVENTS = 50
SAFE_NUMBER = 2 ** 53 - 1
NAME = re.compile(r'^[a-z][a-z0-9_.]{0,63}$')
STANDARD_CONTEXT = {'environment', 'platform', 'app_version', 'country', 'network_type'}
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
Number = Annotated[StrictInt | StrictFloat, Field(ge=-SAFE_NUMBER, le=SAFE_NUMBER, allow_inf_nan=False)]
Label = Annotated[str, Field(min_length=1, max_length=160)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Metric(Contract):
    label: Label
    type: Literal['number', 'integer'] = 'number'
    unit: Annotated[str, Field(min_length=1, max_length=32)]
    required: bool = False
    minimum: Number | None = None
    maximum: Number | None = None

    @model_validator(mode='after')
    def bounds(self):
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError('minimum must not exceed maximum')
        return self


class ContextField(Contract):
    label: Label
    type: Literal['string', 'enum', 'boolean'] = 'string'
    required: bool = False
    filterable: bool = False
    values: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(default_factory=list, max_length=50)

    @model_validator(mode='after')
    def enumeration(self):
        if (self.type == 'enum') != bool(self.values) or len(set(self.values)) != len(self.values):
            raise ValueError('enum fields require distinct allowed values; other fields must omit values')
        return self


class Definition(Contract):
    has_outcome: bool = True
    duration: Metric | None = None
    metrics: dict[str, Metric] = Field(default_factory=dict, max_length=20)
    context: dict[str, ContextField] = Field(default_factory=dict, max_length=11)
    primary_metric: str | None = None

    @model_validator(mode='after')
    def fields(self):
        for name in (*self.metrics, *self.context):
            if not NAME.fullmatch(name) or name == 'duration_ms' or name in STANDARD_CONTEXT:
                raise ValueError('field names must be lowercase identifiers and must not use reserved names')
        if self.duration and (self.duration.unit != 'ms' or self.duration.type != 'number'
                              or self.duration.minimum is None or self.duration.minimum < 0):
            raise ValueError('duration requires type number, unit ms and a nonnegative minimum')
        if not self.has_outcome and not self.duration and not self.metrics:
            raise ValueError('a check without an outcome requires at least one measurement')
        if self.primary_metric == 'duration_ms':
            if not self.duration:
                raise ValueError('primary metric must be defined')
        elif self.primary_metric is not None and self.primary_metric not in self.metrics:
            raise ValueError('primary metric must be defined')
        if sum(field.filterable for field in self.context.values()) > 2:
            raise ValueError('at most two custom fields may be filterable')
        return self


class ProjectInput(Contract):
    name: Label
    description: Annotated[str, Field(max_length=1000)] = ''
    group_id: Annotated[int, Field(gt=0, le=2147483647)] | None = None
    events_per_minute: Annotated[int, Field(ge=1, le=1000000)] = 6000
    requests_per_minute: Annotated[int, Field(ge=1, le=100000)] = 1200
    bytes_per_minute: Annotated[int, Field(ge=1024, le=1073741824)] = 8 * 1024 * 1024


class ProjectState(Contract):
    enabled: bool


class CheckInput(Contract):
    code: Annotated[str, Field(pattern=r'^[a-z][a-z0-9_.]{0,63}$')]
    name: Label
    description: Annotated[str, Field(max_length=1000)] = ''
    definition: Definition


class KeyInput(Contract):
    name: Label
    checks: list[Annotated[str, Field(pattern=r'^[a-z][a-z0-9_.]{0,63}$')]] = Field(min_length=1, max_length=100)
    environments: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(min_length=1, max_length=20)
    origins: list[Annotated[str, Field(max_length=512)]] = Field(default_factory=list, max_length=20)
    allow_no_origin: bool = True

    @field_validator('origins')
    @classmethod
    def valid_origins(cls, values):
        for value in values:
            try:
                parsed = urlsplit(value)
                port = parsed.port
            except ValueError as exc:
                raise ValueError('origins must be HTTP(S) origins') from exc
            if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username
                    or parsed.password or parsed.path or parsed.query or parsed.fragment
                    or any(c.isspace() for c in value) or value.endswith(':') or port == 0):
                raise ValueError('origins must be HTTP(S) origins without a path')
        return list(dict.fromkeys(values))

    @model_validator(mode='after')
    def usable(self):
        if not self.allow_no_origin and not self.origins:
            raise ValueError('allow at least one origin or clients without Origin')
        self.checks = list(dict.fromkeys(self.checks))
        self.environments = list(dict.fromkeys(self.environments))
        return self


class ErrorDetails(Contract):
    code: Annotated[str, Field(min_length=1, max_length=64)]
    message: Annotated[str, Field(max_length=512)] = ''


class Event(Contract):
    event_id: str
    check: Annotated[str, Field(pattern=r'^[a-z][a-z0-9_.]{0,63}$')]
    definition_version: Annotated[int, Field(ge=1, le=2147483647)]
    observed_at: Annotated[str, Field(max_length=40)]
    page_url: Annotated[str, Field(min_length=1, max_length=2048)] | None = None
    status: Literal['ok', 'error'] | None = None
    duration_ms: Number | None = None
    metrics: dict[str, Number] = Field(default_factory=dict, max_length=20)
    context: dict[str, str | bool] = Field(default_factory=dict, max_length=16)
    error: ErrorDetails | None = None
    sampling_probability: Annotated[Number, Field(gt=0, le=1)] = 1

    @field_validator('page_url')
    @classmethod
    def page_address(cls, value):
        if value is None:
            return None
        if any(ord(char) < 32 or ord(char) == 127 for char in value) or '\\' in value:
            raise ValueError('page_url must be an HTTP(S) page address')
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError('page_url must be an HTTP(S) page address without credentials')
        # Discard search parameters and fragments before persistence and hashing.
        return parsed._replace(path=parsed.path or '/', query='', fragment='').geturl()

    @field_validator('event_id')
    @classmethod
    def canonical_uuid(cls, value):
        if not re.fullmatch(r'[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', value):
            raise ValueError('event_id must be a UUID')
        return str(UUID(value))

    @field_validator('observed_at')
    @classmethod
    def timestamp(cls, value):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})', value):
            raise ValueError('observed_at must be an RFC 3339 timestamp with a timezone')
        if not value.endswith('Z') and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
            raise ValueError('invalid timezone offset')
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
        except (ValueError, OverflowError) as exc:
            raise ValueError('invalid observed_at') from exc
        return parsed.isoformat(timespec='microseconds').replace('+00:00', 'Z')

    @field_validator('metrics', 'duration_ms', 'sampling_probability')
    @classmethod
    def canonical_numbers(cls, value):
        # 1 and 1.0 denote the same measurement for idempotency.
        def number(item):
            return int(item) if isinstance(item, float) and math.isfinite(item) and item.is_integer() else item
        return {key: number(item) for key, item in value.items()} if isinstance(value, dict) else number(value)

    @field_validator('context')
    @classmethod
    def context_values(cls, values):
        for name, value in values.items():
            if not NAME.fullmatch(name) or isinstance(value, str) and not 1 <= len(value) <= 128:
                raise ValueError('context requires valid names and values of 1 to 128 characters')
        return values

    @model_validator(mode='after')
    def outcome(self):
        if self.error is not None and self.status != 'error':
            raise ValueError('error details require status error')
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError('duration_ms must be nonnegative')
        for name in ('status', 'duration_ms', 'error'):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f'omit {name} instead of sending null')
        return self

    def observed_us(self):
        delta = datetime.fromisoformat(self.observed_at.replace('Z', '+00:00')) - EPOCH
        return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


class Batch(Contract):
    schema_version: Literal[1]
    project_key: Annotated[str, Field(pattern=r'^rmon_pub_[A-Za-z0-9_-]{43}$')]
    events: list[Event] = Field(min_length=1, max_length=MAX_BATCH_EVENTS)

    @field_validator('schema_version', mode='before')
    @classmethod
    def version_integer(cls, value):
        if type(value) is not int:
            raise ValueError('schema_version must be an integer')
        return value


def validate_event(event, definition, now_us):
    """Return field errors without echoing event content or credentials."""
    errors = []
    if event.observed_us() < now_us - 86400 * 1000000 or event.observed_us() > now_us + 300 * 1000000:
        errors.append(('observed_at', 'Use a time within the last 24 hours and at most 5 minutes ahead'))
    if definition.has_outcome != (event.status is not None):
        errors.append(('status', 'This check requires status' if definition.has_outcome else 'This check has no outcome'))
    metrics = dict(definition.metrics)
    values = dict(event.metrics)
    if definition.duration:
        metrics['duration_ms'] = definition.duration
    if event.duration_ms is not None:
        values['duration_ms'] = event.duration_ms
    if 'duration_ms' in event.metrics:
        errors.append(('metrics.duration_ms', 'Send duration_ms as a top-level field'))
    for name in values.keys() - metrics.keys():
        errors.append((f'metrics.{name}', 'Measurement is not defined'))
    for name, metric in metrics.items():
        path = name if name == 'duration_ms' else f'metrics.{name}'
        if name not in values:
            if metric.required:
                errors.append((path, 'Measurement is required'))
            continue
        value = values[name]
        if metric.type == 'integer' and type(value) is not int:
            errors.append((path, 'Measurement must be an integer'))
        if metric.minimum is not None and value < metric.minimum or metric.maximum is not None and value > metric.maximum:
            errors.append((path, 'Measurement is outside its allowed range'))
    for name, value in event.context.items():
        if name in STANDARD_CONTEXT:
            if type(value) is not str:
                errors.append((f'context.{name}', 'Standard context must be a string'))
        elif name not in definition.context:
            errors.append((f'context.{name}', 'Context field is not defined'))
    for name, field in definition.context.items():
        if name not in event.context:
            if field.required:
                errors.append((f'context.{name}', 'Context field is required'))
            continue
        value = event.context[name]
        expected = bool if field.type == 'boolean' else str
        if type(value) is not expected or field.type == 'enum' and value not in field.values:
            errors.append((f'context.{name}', 'Context value does not match its definition'))
    return errors
