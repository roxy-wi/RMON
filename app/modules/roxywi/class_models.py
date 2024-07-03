import re
from annotated_types import Gt, Le
from typing import Optional, Annotated, Union, Literal, Any

from shlex import quote
from pydantic_core import CoreSchema, core_schema
from pydantic import BaseModel, field_validator, StringConstraints, IPvAnyAddress, AnyUrl, root_validator, GetCoreSchemaHandler, UUID4

DomainName = Annotated[str, StringConstraints(pattern=r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$")]


class EscapedString(str):
    pattern = re.compile('[&;|$`]')

    @classmethod
    def validate(cls, field_value, info) -> str:
        if isinstance(field_value, str):
            if cls.pattern.search(field_value):
                return re.sub(cls.pattern, '', field_value)
            else:
                return quote(field_value.rstrip())

    @classmethod
    def __get_pydantic_core_schema__(
            cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:

        return core_schema.chain_schema(
            [
                core_schema.with_info_plain_validator_function(
                    function=cls.validate,
                )
            ]
        )


class BaseResponse(BaseModel):
    status: str = 'Ok'


class IdResponse(BaseResponse):
    id: int


class IdDataResponse(IdResponse):
    data: str


class ErrorResponse(BaseModel):
    status: str = 'failed'
    error: Union[str, list]


class BaseCheckRequest(BaseModel):
    name: EscapedString
    desc: Optional[str] = ''
    agent_id: int
    timeout: Optional[int] = 2
    enabled: Optional[bool] = 1
    tg: Optional[int] = 0
    pd: Optional[int] = 0
    mm: Optional[int] = 0
    slack: Optional[int] = 0
    interval: Optional[int] = 120
    group: Optional[EscapedString] = None

    @root_validator(pre=True)
    @classmethod
    def timeout_must_be_lower_interval(cls, values):
        timeout = 2
        interval = 120
        if 'timeout' in values:
            try:
                timeout = int(values['timeout'])
            except ValueError:
                raise ValueError('timeout must be an integer')
        if 'interval' in values:
            try:
                interval = int(values['interval'])
            except ValueError:
                raise ValueError('interval must be an integer')
        if timeout >= interval:
            raise ValueError('timeout value must be less than interval')
        return values


class HttpCheckRequest(BaseCheckRequest):
    url: AnyUrl
    http_method: Literal['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
    header_req: Optional[str] = None
    body_req: Optional[str] = None
    body: Optional[EscapedString] = None
    accepted_status_codes: Annotated[int, Gt(99), Le(599)]

    @field_validator('http_method', mode='before')
    @classmethod
    def set_http_method(cls, v):
        return v.lower()

    @field_validator('header_req', 'body_req')
    @classmethod
    def set_header_req(cls, v):
        return v.replace('\'', '"')


class DnsCheckRequest(BaseCheckRequest):
    resolver: Union[IPvAnyAddress, DomainName]
    port: Annotated[int, Gt(1), Le(65535)] = 53
    record_type: Literal['a', 'aaa', 'caa', 'cname', 'mx', 'ns', 'ptr', 'sao', 'src', 'txt']
    ip: Union[IPvAnyAddress, DomainName]


class PingCheckRequest(BaseCheckRequest):
    ip: Union[IPvAnyAddress, DomainName]
    packet_size: Annotated[int, Le(16)]


class TcpCheckRequest(BaseCheckRequest):
    ip: Union[IPvAnyAddress, DomainName]
    port: Annotated[int, Gt(1), Le(65535)]


class UserPost(BaseModel):
    username: EscapedString
    password: str
    email: EscapedString
    enabled: Optional[bool] = 1
    user_group: int
    role: Annotated[int, Gt(0), Le(4)] = 4


class UserPut(BaseModel):
    username: EscapedString
    email: EscapedString
    enabled: Optional[bool] = 1


class AddUserToGroup(BaseModel):
    role_id: Annotated[int, Gt(0), Le(4)]


class RmonAgent(BaseModel):
    name: EscapedString
    desc: Optional[EscapedString] = None
    enabled: Optional[bool] = 1
    shared: Optional[bool] = 0
    port: Annotated[int, Gt(1024), Le(65535)] = 5101
    server_id: int
    uuid: Optional[UUID4] = ''
    reconfigure: Optional[bool] = 0


class GroupQuery(BaseModel):
    group_id: Optional[int] = None
