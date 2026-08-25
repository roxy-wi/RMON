from pathlib import Path

import pytest

import app.modules.subscription.access as subscription_access
import app.modules.tools.smon as smon_service
import app.modules.tools.smon_agent as agent_service
from app.modules.roxywi.exception import RoxywiCheckLimits, RoxywiPermissionError


PAID_FEATURES = {
    subscription_access.OIDC,
    subscription_access.ACTION_HISTORY,
    subscription_access.MONITORING_HISTORY,
    subscription_access.ALERT_HISTORY,
    subscription_access.ALERTING_CHANNELS,
    subscription_access.STATUS_PAGES,
    subscription_access.MONITORING_CHECKS,
    subscription_access.MONITORING_AGENTS,
    subscription_access.SERVICE_CONTROL,
}


@pytest.mark.security
def test_subscription_catalog_contains_every_paid_feature_and_is_immutable():
    assert set(subscription_access.FEATURE_POLICIES) == PAID_FEATURES
    assert set(subscription_access.PLAN_LIMITS) == {
        subscription_access.MONITORING_CHECKS,
        subscription_access.MONITORING_AGENTS,
    }
    with pytest.raises(TypeError):
        subscription_access.FEATURE_POLICIES['bypass'] = subscription_access.FEATURE_POLICIES[
            subscription_access.OIDC
        ]


@pytest.mark.security
def test_all_paid_features_are_free_without_reading_license_state(monkeypatch):
    monkeypatch.setattr(subscription_access, 'SUBSCRIPTION_ENFORCEMENT_ENABLED', False)

    def unexpected_license_read():
        pytest.fail('Free mode must not depend on a license server or stored subscription')

    monkeypatch.setattr(
        subscription_access.roxywi_common,
        'return_user_subscription',
        unexpected_license_read,
    )

    assert subscription_access.feature_availability() == {
        feature: True for feature in PAID_FEATURES
    }
    for feature in PAID_FEATURES:
        assert subscription_access.is_feature_available(feature)
        assert subscription_access.require_feature(feature).active

    subscription_access.enforce_resource_limit(
        subscription_access.MONITORING_CHECKS, 1_000_000
    )
    subscription_access.enforce_resource_limit(
        subscription_access.MONITORING_AGENTS, 1_000_000
    )


@pytest.mark.security
def test_existing_check_and_agent_limits_are_disabled_in_free_mode(monkeypatch):
    monkeypatch.setattr(subscription_access, 'SUBSCRIPTION_ENFORCEMENT_ENABLED', False)
    monkeypatch.setattr(smon_service.smon_sql, 'count_checks', lambda: 1_000_000)
    monkeypatch.setattr(agent_service.smon_sql, 'count_agents', lambda: 1_000_000)

    smon_service.check_checks_limit()
    agent_service.check_agent_limit()


@pytest.mark.security
def test_enforcement_can_only_be_enabled_by_the_code_constant(monkeypatch):
    monkeypatch.setattr(subscription_access, 'SUBSCRIPTION_ENFORCEMENT_ENABLED', True)

    free = {'user_status': 1, 'user_plan': 'free'}
    premium = {'user_status': 1, 'user_plan': 'premium'}
    inactive = {'user_status': 0, 'user_plan': 'premium'}

    assert subscription_access.is_feature_available(
        subscription_access.MONITORING_CHECKS, free
    )
    assert not subscription_access.is_feature_available(subscription_access.OIDC, free)
    assert all(
        subscription_access.is_feature_available(feature, premium)
        for feature in PAID_FEATURES
    )
    assert not any(
        subscription_access.is_feature_available(feature, inactive)
        for feature in PAID_FEATURES
    )


@pytest.mark.security
@pytest.mark.parametrize(
    ('feature', 'plan', 'limit'),
    (
        (subscription_access.MONITORING_CHECKS, 'free', 10),
        (subscription_access.MONITORING_CHECKS, 'home', 30),
        (subscription_access.MONITORING_CHECKS, 'enterprise', 100),
        (subscription_access.MONITORING_AGENTS, 'free', 1),
        (subscription_access.MONITORING_AGENTS, 'home', 3),
        (subscription_access.MONITORING_AGENTS, 'enterprise', 10),
    ),
)
def test_plan_limits_are_ready_for_future_enforcement(monkeypatch, feature, plan, limit):
    monkeypatch.setattr(subscription_access, 'SUBSCRIPTION_ENFORCEMENT_ENABLED', True)
    subscription = {'user_status': 1, 'user_plan': plan}

    subscription_access.enforce_resource_limit(feature, limit - 1, subscription)
    with pytest.raises(RoxywiCheckLimits, match=plan.title()):
        subscription_access.enforce_resource_limit(feature, limit, subscription)

    subscription_access.enforce_resource_limit(
        feature, 1_000_000, {'user_status': 1, 'user_plan': 'premium'}
    )


@pytest.mark.security
def test_business_service_rechecks_status_page_entitlement_before_writing(monkeypatch):
    monkeypatch.setattr(subscription_access, 'SUBSCRIPTION_ENFORCEMENT_ENABLED', True)
    monkeypatch.setattr(
        subscription_access.roxywi_common,
        'return_user_subscription',
        lambda: {'user_status': 1, 'user_plan': 'enterprise'},
    )
    writes = []
    monkeypatch.setattr(
        smon_service.smon_sql,
        'add_status_page',
        lambda *_args, **_kwargs: writes.append('status-page'),
    )

    with pytest.raises(RoxywiPermissionError, match='Status pages'):
        smon_service.create_status_page('name', 'slug', '', [1], '', 1)
    assert writes == []


@pytest.mark.security
def test_http_feature_guard_is_ready_for_future_enforcement(client, monkeypatch):
    monkeypatch.setattr(subscription_access, 'SUBSCRIPTION_ENFORCEMENT_ENABLED', True)
    monkeypatch.setattr(
        subscription_access.roxywi_common,
        'return_user_subscription',
        lambda: {'user_status': 1, 'user_plan': 'free'},
    )

    response = client.get('/oidc/providers')

    assert response.status_code == 403
    assert response.get_json() == {
        'status': 'failed',
        'error': 'OIDC requires an active Enterprise plan or higher',
    }


@pytest.mark.security
def test_subscription_templates_use_central_feature_availability():
    root = Path(__file__).resolve().parents[2] / 'app' / 'templates'
    templates = {
        'history.html': 'action_history',
        'include/smon/smon_history.html': 'monitoring_history',
        'smon/history.html': 'alert_history',
        'smon/manage_status_page.html': 'status_pages',
    }

    for template, feature in templates.items():
        source = (root / template).read_text(encoding='utf-8')
        assert f"subscription_features['{feature}']" in source
        assert "user_subscription['user_status']" not in source
