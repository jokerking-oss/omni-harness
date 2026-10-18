"""Pluggable fine-grained authorization (resource-level RBAC and beyond)."""

from omniharness.authz.adapter import GuardrailAuthorizationAdapter
from omniharness.authz.enforcement import filter_tools_by_authorization
from omniharness.authz.principal import build_principal_from_context, normalize_authz_attributes
from omniharness.authz.provider import AuthorizationProvider, AuthzDecision, AuthzReason, AuthzRequest, Principal
from omniharness.authz.rbac import RbacAuthorizationProvider
from omniharness.authz.runtime import resolve_authorization_provider
from omniharness.authz.sandbox_authz import authorize_sandbox_execution
from omniharness.authz.tool_filter import apply_tool_authorization

__all__ = [
    "AuthzDecision",
    "AuthzReason",
    "AuthzRequest",
    "AuthorizationProvider",
    "GuardrailAuthorizationAdapter",
    "Principal",
    "RbacAuthorizationProvider",
    "apply_tool_authorization",
    "authorize_sandbox_execution",
    "build_principal_from_context",
    "filter_tools_by_authorization",
    "normalize_authz_attributes",
    "resolve_authorization_provider",
]
