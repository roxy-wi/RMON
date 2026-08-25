from dataclasses import dataclass
from functools import wraps
from types import MappingProxyType
from typing import Iterable, Optional

from flask import jsonify, request

import app.modules.roxywi.common as roxywi_common
from app.modules.roxywi.exception import RoxywiCheckLimits, RoxywiPermissionError


OIDC = 'oidc'
ACTION_HISTORY = 'action_history'
MONITORING_HISTORY = 'monitoring_history'
ALERT_HISTORY = 'alert_history'
ALERTING_CHANNELS = 'alerting_channels'
STATUS_PAGES = 'status_pages'
MONITORING_CHECKS = 'monitoring_checks'
MONITORING_AGENTS = 'monitoring_agents'
SERVICE_CONTROL = 'service_control'

# Keep every subscription feature free until monetization is enabled in code.
SUBSCRIPTION_ENFORCEMENT_ENABLED = False


@dataclass(frozen=True)
class FeaturePolicy:
    allowed_plans: frozenset[str]
    error: str


FEATURE_POLICIES = MappingProxyType({
    OIDC: FeaturePolicy(
        frozenset({'enterprise', 'premium'}),
        'OIDC requires an active Enterprise plan or higher',
    ),
    ACTION_HISTORY: FeaturePolicy(
        frozenset({'enterprise', 'premium'}),
        'Action history requires an active Enterprise plan or higher',
    ),
    MONITORING_HISTORY: FeaturePolicy(
        frozenset({'enterprise', 'premium'}),
        'Monitoring history requires an active Enterprise plan or higher',
    ),
    ALERT_HISTORY: FeaturePolicy(
        frozenset({'home', 'enterprise', 'premium'}),
        'Alert history requires an active Home plan or higher',
    ),
    ALERTING_CHANNELS: FeaturePolicy(
        frozenset({'home', 'enterprise', 'premium'}),
        'Alerting channels require an active Home plan or higher',
    ),
    STATUS_PAGES: FeaturePolicy(
        frozenset({'premium'}),
        'Status pages require an active Premium plan',
    ),
    MONITORING_CHECKS: FeaturePolicy(
        frozenset({'free', 'home', 'enterprise', 'premium'}),
        'Monitoring checks require an active subscription',
    ),
    MONITORING_AGENTS: FeaturePolicy(
        frozenset({'free', 'home', 'enterprise', 'premium'}),
        'Monitoring agents require an active subscription',
    ),
    SERVICE_CONTROL: FeaturePolicy(
        frozenset({'free', 'home', 'enterprise', 'premium'}),
        'Service control requires an active subscription',
    ),
})


PLAN_LIMITS = MappingProxyType({
    MONITORING_CHECKS: MappingProxyType({
        'free': 10,
        'home': 30,
        'enterprise': 100,
        'premium': None,
    }),
    MONITORING_AGENTS: MappingProxyType({
        'free': 1,
        'home': 3,
        'enterprise': 10,
        'premium': None,
    }),
})


@dataclass(frozen=True)
class SubscriptionEntitlement:
    active: bool
    plan: str


def _policy(feature: str) -> FeaturePolicy:
    try:
        return FEATURE_POLICIES[feature]
    except KeyError as exc:
        raise ValueError(f'Unknown subscription feature: {feature}') from exc


def is_enforcement_enabled() -> bool:
    return SUBSCRIPTION_ENFORCEMENT_ENABLED


def normalize_subscription(subscription: Optional[dict] = None) -> SubscriptionEntitlement:
    if subscription is None:
        subscription = roxywi_common.return_user_subscription()

    try:
        active = int(subscription.get('user_status', 0)) == 1
        plan = str(subscription.get('user_plan') or '').strip().lower()
    except (AttributeError, TypeError, ValueError):
        return SubscriptionEntitlement(active=False, plan='')
    return SubscriptionEntitlement(active=active, plan=plan)


def is_feature_available(feature: str, subscription: Optional[dict] = None) -> bool:
    policy = _policy(feature)
    if not is_enforcement_enabled():
        return True
    entitlement = normalize_subscription(subscription)
    return entitlement.active and entitlement.plan in policy.allowed_plans


def require_feature(feature: str, subscription: Optional[dict] = None) -> SubscriptionEntitlement:
    policy = _policy(feature)
    if not is_enforcement_enabled():
        return SubscriptionEntitlement(active=True, plan='free')
    entitlement = normalize_subscription(subscription)
    if not entitlement.active or entitlement.plan not in policy.allowed_plans:
        raise RoxywiPermissionError(policy.error)
    return entitlement


def enforce_resource_limit(feature: str, current_count: int, subscription: Optional[dict] = None) -> None:
    if feature not in PLAN_LIMITS:
        raise ValueError(f'Feature has no resource limits: {feature}')
    if not is_enforcement_enabled():
        return

    entitlement = require_feature(feature, subscription)
    limit = PLAN_LIMITS[feature].get(entitlement.plan)
    if limit is not None and current_count >= limit:
        plan_name = entitlement.plan.title()
        raise RoxywiCheckLimits(f'You have reached the limit for the {plan_name} plan')


def feature_availability(subscription: Optional[dict] = None) -> dict[str, bool]:
    if not is_enforcement_enabled():
        return {feature: True for feature in FEATURE_POLICIES}
    entitlement = normalize_subscription(subscription)
    normalized = {'user_status': int(entitlement.active), 'user_plan': entitlement.plan}
    return {
        feature: is_feature_available(feature, normalized)
        for feature in FEATURE_POLICIES
    }


def feature_required(feature: str, *, methods: Optional[Iterable[str]] = None):
    policy = _policy(feature)
    guarded_methods = frozenset(method.upper() for method in methods) if methods else None

    def decorator(function):
        @wraps(function)
        def decorated_view(*args, **kwargs):
            if guarded_methods is not None and request.method.upper() not in guarded_methods:
                return function(*args, **kwargs)
            try:
                require_feature(feature)
            except RoxywiPermissionError:
                return jsonify({'status': 'failed', 'error': policy.error}), 403
            return function(*args, **kwargs)

        return decorated_view

    return decorator
