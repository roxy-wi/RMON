import re
from annotated_types import Gt, Le
from typing import Optional, Annotated, Union, Literal, Any, List

from shlex import quote
from datetime import datetime, timedelta

from pydantic_core import CoreSchema, core_schema
from pydantic import BaseModel, field_validator, StringConstraints, IPvAnyAddress, AnyUrl, root_validator, \
    GetCoreSchemaHandler, UUID4, PastDate

DomainName = Annotated[str, StringConstraints(pattern=r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9]$")]


class EscapedString(str):
    pattern = re.compile('[&;|$`]')

    @classmethod
    def validate(cls, field_value, info) -> str:
        if isinstance(field_value, str):
            if cls.pattern.search(field_value):
                return re.sub(cls.pattern, '', field_value)
            elif field_value == '':
                return field_value
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
    description: Optional[str] = ''
    place: Literal['all', 'country', 'region', 'agent']
    entities: List[int]
    check_timeout: Annotated[int, Le(59), Gt(1)] = 2
    enabled: Optional[bool] = 1
    telegram_channel_id: Optional[int] = 0
    pd_channel_id: Optional[int] = 0
    mm_channel_id: Optional[int] = 0
    slack_channel_id: Optional[int] = 0
    interval: Optional[int] = 120
    check_group: Optional[EscapedString] = None
    group_id: Optional[int] = None
    retries: Annotated[int, Gt(0)] = 3
    runbook: Optional[EscapedString] = None

    @root_validator(pre=True)
    @classmethod
    def timeout_must_be_lower_interval(cls, values):
        timeout = 2
        interval = 120
        if 'check_timeout' in values:
            try:
                timeout = int(values['check_timeout'])
            except ValueError:
                raise ValueError('check_timeout must be an integer')
        if 'interval' in values:
            try:
                interval = int(values['interval'])
            except ValueError:
                raise ValueError('interval must be an integer')
        if timeout >= interval:
            raise ValueError('timeout value must be less than interval')
        return values

    @root_validator(pre=True)
    @classmethod
    def check_must_has_entities_if_not_all_place(cls, values):
        place = ''
        entities = []
        if 'place' in values:
            place = values['place']
        if 'entities' in values:
            entities = values['entities']
        if place != 'all' and len(entities) == 0:
            raise ValueError('Check must have at least on entity, if place is not "All"')
        return values


class HttpCheckRequest(BaseCheckRequest):
    url: AnyUrl
    method: Literal['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
    header_req: Optional[str] = None
    body_req: Optional[str] = None
    body: Optional[EscapedString] = None
    accepted_status_codes: Annotated[int, Gt(99), Le(599)]
    ignore_ssl_error: Optional[bool] = 0
    redirects: Optional[int] = 10

    @field_validator('method', mode='before')
    @classmethod
    def set_http_method(cls, v):
        return v.lower()

    @field_validator('header_req', 'body_req')
    @classmethod
    def set_header_req(cls, v):
        return v.replace('\'', '"')

    @field_validator('url', mode='before')
    @classmethod
    def set_url(cls, v):
        if v.find('http://') == -1 and v.find('https://') == -1:
            raise ValueError('URL must start with http:// or https://')
        return v


class DnsCheckRequest(BaseCheckRequest):
    resolver: Union[IPvAnyAddress, DomainName]
    port: Annotated[int, Gt(1), Le(65535)] = 53
    record_type: Literal['a', 'aaa', 'caa', 'cname', 'mx', 'ns', 'ptr', 'sao', 'src', 'txt']
    ip: Union[IPvAnyAddress, DomainName]


class SmtpCheckRequest(BaseCheckRequest):
    username: EscapedString
    password: EscapedString
    port: Annotated[int, Gt(1), Le(65535)] = 53
    ip: Union[IPvAnyAddress, DomainName]
    ignore_ssl_error: Optional[bool] = 0


class RabbitCheckRequest(BaseCheckRequest):
    username: EscapedString
    password: EscapedString
    port: Annotated[int, Gt(1), Le(65535)] = 5672
    ip: Union[IPvAnyAddress, DomainName]
    vhost: Optional[EscapedString] = '/'
    ignore_ssl_error: Optional[bool] = 0


class PingCheckRequest(BaseCheckRequest):
    ip: Union[IPvAnyAddress, DomainName]
    packet_size: Annotated[int, Gt(16)]


class TcpCheckRequest(BaseCheckRequest):
    ip: Union[IPvAnyAddress, DomainName]
    port: Annotated[int, Gt(1), Le(65535)]


class UserPost(BaseModel):
    username: EscapedString
    password: str
    email: EscapedString
    enabled: Optional[bool] = 1
    group_id: int
    role: Annotated[int, Gt(0), Le(4)] = 4


class UserPut(BaseModel):
    username: EscapedString
    email: EscapedString
    enabled: Optional[bool] = 1


class AddUserToGroup(BaseModel):
    role_id: Annotated[int, Gt(0), Le(4)]


class RmonAgent(BaseModel):
    name: EscapedString
    description: Optional[EscapedString] = None
    enabled: Optional[bool] = 1
    shared: Optional[bool] = 0
    port: Annotated[int, Gt(1024), Le(65535)] = 5101
    server_id: int
    uuid: Optional[UUID4] = ''
    reconfigure: Optional[bool] = 0
    region_id: Optional[int] = None


class GroupQuery(BaseModel):
    group_id: Optional[int] = None
    recurse: Optional[bool] = False
    max_depth: Optional[int] = 1


class CheckFiltersQuery(GroupQuery):
    offset: int = 1
    limit: int = 25
    check_group: Optional[EscapedString] = None
    check_name: Optional[EscapedString] = None
    check_status: Optional[int] = None
    check_type: Optional[Literal['http', 'tcp', 'ping', 'dns', 'rabbitmq', 'smtp']] = None
    sort_by: Optional[Literal['name', 'status', 'check_type', 'check_group', 'created_at', 'updated_at']] = None


class UserSearchRequest(GroupQuery):
    username: Optional[str] = None
    email: Optional[str] = None
    group_name: Optional[str] = None


class GroupRequest(BaseModel):
    name: EscapedString
    description: Optional[EscapedString] = None


class ServerRequest(BaseModel):
    hostname: EscapedString
    ip: Union[IPvAnyAddress, DomainName]
    enabled: Optional[bool] = 1
    cred_id: int
    port: Optional[int] = 22
    description: Optional[EscapedString] = None
    group_id: Optional[int] = None


class CredRequest(BaseModel):
    name: EscapedString
    username: EscapedString
    password: Optional[EscapedString] = None
    key_enabled: Optional[bool] = 1
    group_id: Optional[int] = None
    shared: Optional[int] = 0


class CredUploadRequest(BaseModel):
    private_key: str
    passphrase: Optional[EscapedString] = None


class ChannelRequest(BaseModel):
    token: EscapedString
    channel: EscapedString
    group_id: Optional[int] = None


class SettingsRequest(BaseModel):
    param: EscapedString
    value: EscapedString


class StatusPageRequest(BaseModel):
    name: EscapedString
    slug: EscapedString
    description: Optional[EscapedString] = None
    custom_style: Optional[EscapedString] = None
    checks: list
    group_id: Optional[int] = None


class RegionRequest(BaseModel):
    name: EscapedString
    description: Optional[EscapedString] = None
    shared: Optional[bool] = 0
    enabled: Optional[bool] = 1
    group_id: Optional[int] = None
    country_id: Optional[int] = None
    agents: Optional[list[int]] = None


class CountryRequest(BaseModel):
    name: EscapedString
    description: Optional[EscapedString] = None
    shared: Optional[bool] = 0
    enabled: Optional[bool] = 1
    group_id: Optional[int] = None
    regions: Optional[list[int]] = None


class CheckGroup(BaseModel):
    name: EscapedString
    group_id: Optional[int] = None


class NettoolsRequest(BaseModel):
    server_from: Optional[EscapedString] = None
    server_to: Optional[Union[IPvAnyAddress, DomainName]] = None
    port: Optional[Annotated[int, Gt(1), Le(65535)]] = None
    action: Optional[Literal['ping', 'trace']] = None
    dns_name: Optional[DomainName] = None
    record_type: Optional[Literal['a', 'aaaa', 'caa', 'cname', 'mx', 'ns', 'ptr', 'sao', 'src', 'txt']] = None
    ip: Optional[IPvAnyAddress] = None
    netmask: Optional[int] = None


class CheckMetricsQuery(GroupQuery):
    step: Optional[str] = '30s'
    start: Optional[str] = (datetime.now() - timedelta(hours=0, minutes=30)).strftime("%Y-%m-%dT%H:%M:%S%z")
    end: Optional[str] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")

    @root_validator(pre=True)
    @classmethod
    def transform_str_to_date(cls, values):
        if 'start' in values:
            start = values['start']
            if 'h' in start:
                start = int(start.replace('h', ''))
                values['start'] = (datetime.now() - timedelta(hours=start, minutes=0)).strftime("%Y-%m-%dT%H:%M:%S%z")
            elif start == 'now':
                values['start'] = (datetime.now() - timedelta(hours=0, minutes=30)).strftime("%Y-%m-%dT%H:%M:%S%z")
            elif 'm' in start:
                start = int(start.replace('m', ''))
                values['start'] = (datetime.now() - timedelta(hours=0, minutes=start)).strftime("%Y-%m-%dT%H:%M:%S%z")
            else:
                values['start'] = (datetime.now() - timedelta(hours=0, minutes=30)).strftime("%Y-%m-%dT%H:%M:%S%z")
        if 'end' in values:
            end = values['end']
            if 'h' in end:
                end = int(end.replace('h', ''))
                values['end'] = (datetime.now() - timedelta(hours=end, minutes=0)).strftime("%Y-%m-%dT%H:%M:%S%z")
            elif end == 'now':
                values['end'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")
            elif 'm' in end:
                end = int(end.replace('m', ''))
                values['end'] = (datetime.now() - timedelta(hours=0, minutes=end)).strftime("%Y-%m-%dT%H:%M:%S%z")
            else:
                values['end'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")
        return values
