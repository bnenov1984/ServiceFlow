"""Vendor Control Plane (ADR-BOS-009) — Business OS Core.

Vendor Administrators are a **different security principal** from tenant users:
their own identity table (no `company_id`), their own session kind and cookie,
their own route namespace (`/api/v1/platform-admin/*`), their own append-only
audit log. Nothing here ever produces a `TenantContext` and nothing here ever
binds the tenant RLS GUC — a vendor session reading a tenant table would get
zero rows by construction (fail-closed policy, ADR-016), which is the intended
default and must never be "fixed" with an RLS exemption.

Scope of this slice (walking skeleton): identity, authentication boundary, one
protected read (`GET /me`), audit foundation, bootstrap CLI. No company
browsing, no provisioning, no entitlement or subscription mutation — those are
docs/business-os/18 §9 phases 2-4.
"""
