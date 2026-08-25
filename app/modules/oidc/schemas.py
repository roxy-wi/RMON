from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


def _validate_http_url(value: Optional[str]) -> Optional[str]:
    if value in (None, ''):
        return None
    value = str(value).strip()
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise ValueError('must be an absolute HTTP(S) URL')
    return value


class OidcProviderCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=64, pattern=r'^[a-z0-9][a-z0-9_-]*$')
    label: str = Field(min_length=2, max_length=128)
    enabled: bool = True
    client_id: str = Field(min_length=1, max_length=512)
    client_secret: Optional[str] = Field(default=None, max_length=4096)
    metadata_url: Optional[str] = Field(default=None, max_length=2048)
    issuer: Optional[str] = Field(default=None, max_length=2048)
    authorization_endpoint: Optional[str] = Field(default=None, max_length=2048)
    token_endpoint: Optional[str] = Field(default=None, max_length=2048)
    userinfo_endpoint: Optional[str] = Field(default=None, max_length=2048)
    jwks_uri: Optional[str] = Field(default=None, max_length=2048)
    scope: str = Field(default='openid email profile', min_length=6, max_length=512)
    subject_claim: str = Field(default='sub', min_length=1, max_length=128)
    email_claim: str = Field(default='email', min_length=1, max_length=128)
    username_claim: str = Field(default='preferred_username', min_length=1, max_length=128)
    groups_claim: str = Field(default='groups', min_length=1, max_length=128)
    allowed_domains: list[str] = Field(default_factory=list)
    auto_create_users: bool = False
    auto_link_by_email: bool = True
    require_verified_email: bool = True
    sync_group_memberships: bool = True
    remove_missing_group_memberships: bool = False
    default_group_id: int = Field(default=1, ge=1)
    default_role_id: int = Field(default=4, ge=1, le=4)

    _metadata_url = field_validator('metadata_url')(_validate_http_url)
    _issuer = field_validator('issuer')(_validate_http_url)
    _authorization_endpoint = field_validator('authorization_endpoint')(_validate_http_url)
    _token_endpoint = field_validator('token_endpoint')(_validate_http_url)
    _userinfo_endpoint = field_validator('userinfo_endpoint')(_validate_http_url)
    _jwks_uri = field_validator('jwks_uri')(_validate_http_url)

    @field_validator('scope')
    @classmethod
    def validate_scope(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = ' '.join(value.split())
        if 'openid' not in value.split():
            raise ValueError("OIDC scope must include 'openid'")
        return value

    @field_validator('allowed_domains')
    @classmethod
    def validate_domains(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return None
        domains = []
        for item in value:
            domain = str(item).strip().lower()
            if not domain:
                continue
            if '@' in domain or '/' in domain or ' ' in domain:
                raise ValueError('allowed_domains must contain domain names only')
            domains.append(domain)
        return sorted(set(domains))


class OidcProviderUpdate(OidcProviderCreate):
    slug: Optional[str] = Field(default=None, min_length=2, max_length=64, pattern=r'^[a-z0-9][a-z0-9_-]*$')
    label: Optional[str] = Field(default=None, min_length=2, max_length=128)
    enabled: Optional[bool] = None
    client_id: Optional[str] = Field(default=None, min_length=1, max_length=512)
    scope: Optional[str] = Field(default=None, min_length=6, max_length=512)
    subject_claim: Optional[str] = Field(default=None, min_length=1, max_length=128)
    email_claim: Optional[str] = Field(default=None, min_length=1, max_length=128)
    username_claim: Optional[str] = Field(default=None, min_length=1, max_length=128)
    groups_claim: Optional[str] = Field(default=None, min_length=1, max_length=128)
    allowed_domains: Optional[list[str]] = None
    auto_create_users: Optional[bool] = None
    auto_link_by_email: Optional[bool] = None
    require_verified_email: Optional[bool] = None
    sync_group_memberships: Optional[bool] = None
    remove_missing_group_memberships: Optional[bool] = None
    default_group_id: Optional[int] = Field(default=None, ge=1)
    default_role_id: Optional[int] = Field(default=None, ge=1, le=4)


class OidcGroupMappingRequest(BaseModel):
    external_group: str = Field(min_length=1, max_length=255)
    group_id: int = Field(ge=1)
    role_id: int = Field(default=4, ge=1, le=4)
    active: bool = True
    priority: int = Field(default=100, ge=0, le=10000)

    @field_validator('external_group')
    @classmethod
    def normalize_external_group(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('external_group cannot be empty')
        return value
