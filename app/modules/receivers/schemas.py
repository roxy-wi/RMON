import ipaddress
import re
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def receiver_url(value):
    value = value.strip()
    if any(ord(c) < 33 for c in value) or any(c in value for c in '\\{}'):
        raise ValueError('Enter an absolute HTTP(S) address without credentials, a path or a query')
    try:
        parsed = urlsplit(value)
        port = parsed.port
        host = parsed.hostname
        if parsed.scheme not in ('http', 'https') or not host or parsed.username or parsed.password:
            raise ValueError
        if parsed.query or parsed.fragment or parsed.path not in ('', '/'):
            raise ValueError
        if ':' in host:
            host = '[' + str(ipaddress.IPv6Address(host)) + ']'
        else:
            host = host.encode('idna').decode('ascii').lower()
            if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host):
                raise ValueError
        if port is not None and not 1 <= port <= 65535:
            raise ValueError
        if port == (443 if parsed.scheme == 'https' else 80):
            port = None
        return urlunsplit((parsed.scheme, host + (f':{port}' if port else ''), '', '', ''))
    except (ValueError, UnicodeError):
        raise ValueError('Enter an absolute HTTP(S) address without credentials, a path or a query') from None


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class EndpointInput(Input):
    name: str = Field(min_length=1, max_length=160)
    url: str = Field(min_length=1, max_length=500)
    role: Literal['classic', 'client']
    transport: Literal['http', 'https', 'mtls'] = 'http'
    kind: Literal['direct', 'lb', 'external'] = 'direct'
    shared: bool = False
    revision: int | None = Field(default=None, ge=1)

    _url = field_validator('url')(receiver_url)

    @model_validator(mode='after')
    def compatible_transport(self):
        if self.url.startswith('https:') != (self.transport != 'http'):
            raise ValueError('The address scheme must match its transport')
        if self.role == 'client' and self.transport == 'mtls':
            raise ValueError('Client projects require HTTP or HTTPS without agent certificates')
        return self


class RoutingInput(Input):
    endpoint_ids: list[int] | None = Field(default=None, max_length=16)
    policy: Literal['balance', 'failover'] = 'balance'

    @field_validator('endpoint_ids')
    @classmethod
    def valid_ids(cls, value):
        if value is not None and (not value or any(x <= 0 for x in value) or len(set(value)) != len(value)):
            raise ValueError('Select distinct receiver addresses or use the group default')
        return value


class ProjectReceiverInput(Input):
    endpoint_id: int | None = Field(default=None, gt=0)


class ServerInput(Input):
    name: str = Field(min_length=1, max_length=160)
    host_id: int = Field(gt=0)
    roles: list[Literal['classic', 'client']] = Field(min_length=1, max_length=2)
    endpoint_ids: list[int] = Field(default_factory=list, max_length=16)
    new_endpoints: list[EndpointInput] = Field(default_factory=list, max_length=2)
    classic_port: int = Field(default=5100, ge=1025, le=65535)
    client_port: int = Field(default=5102, ge=1025, le=65535)
    bind_ip: str = '0.0.0.0'
    database_host: str = Field(default='', max_length=253)
    database_port: int | None = Field(default=None, ge=1, le=65535)
    sqlite_path: str = Field(default='', max_length=500)
    revision: int | None = Field(default=None, ge=1)

    @field_validator('bind_ip')
    @classmethod
    def bind_address(cls, value):
        return str(ipaddress.IPv4Address(value))

    @field_validator('database_host')
    @classmethod
    def database_address(cls, value):
        if value and not re.fullmatch(r'[A-Za-z0-9._:-]+', value):
            raise ValueError('Enter the database hostname or IP address')
        return value

    @field_validator('sqlite_path')
    @classmethod
    def sqlite_file(cls, value):
        if value and (not value.startswith('/') or any(c in value for c in '\n\r\x00{}') or '..' in value.split('/')):
            raise ValueError('Enter the absolute path to the shared SQLite database on this host')
        return value

    @model_validator(mode='after')
    def distinct(self):
        if len(set(self.roles)) != len(self.roles) or len(set(self.endpoint_ids)) != len(self.endpoint_ids):
            raise ValueError('Roles and receiver addresses must not repeat')
        if len(self.roles) == 2 and self.classic_port == self.client_port:
            raise ValueError('Use different ports for the two roles')
        return self
