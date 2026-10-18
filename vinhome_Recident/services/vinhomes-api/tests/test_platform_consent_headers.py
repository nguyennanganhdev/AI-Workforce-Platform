"""Consent browser policy permits only the registered callback redirect."""

import pytest
from fastapi import HTTPException
from vinhomes_api.platform_customers import private_html


def test_private_consent_form_preserves_origin_and_registered_redirect_only():
    response = private_html("fixture", "test-nonce", "https://platform.example.invalid/connections/callback/vinhomes")
    assert response.headers["referrer-policy"] == "same-origin"
    policy = response.headers["content-security-policy"]
    assert "form-action 'self' https://platform.example.invalid;" in policy
    assert "connect-src 'self'" in policy and "frame-ancestors 'none'" in policy and "*" not in policy
    assert "form-action 'self';" in private_html("login", "test-nonce").headers["content-security-policy"]
    with pytest.raises(HTTPException):
        private_html("fixture", "nonce", "https://allowed.invalid;form-action*/")
