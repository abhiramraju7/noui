"""Helpers to resolve Zoho Books accounts and vendors by name or id."""

from __future__ import annotations

from .zoho_books import books_request


async def resolve_account_by_type(name: str, account_type: str = "") -> dict:
    """Resolve a chart-of-accounts entry by id, code, or (case-insensitive) name.

    account_type optionally narrows the search (e.g. "expense"). Returns
    {"account_id", "account_name", "account_type"}. Raises if not found.
    """
    needle = name.strip()
    res = await books_request("chartofaccounts")
    rows = (res["body"] or {}).get("chartofaccounts") or [] if res["status"] == 200 else []
    if account_type:
        at = account_type.strip().lower()
        rows = [a for a in rows if at in (a.get("account_type") or "").lower()]

    if needle.isdigit() and len(needle) > 8:
        for a in rows:
            if str(a.get("account_id")) == needle:
                return {
                    "account_id": needle,
                    "account_name": a.get("account_name", ""),
                    "account_type": a.get("account_type"),
                }
        return {"account_id": needle, "account_name": "", "account_type": ""}

    low = needle.lower()
    for a in rows:
        if (a.get("account_name") or "").lower() == low or str(
            a.get("account_code") or ""
        ) == needle:
            return {
                "account_id": a.get("account_id"),
                "account_name": a.get("account_name"),
                "account_type": a.get("account_type"),
            }
    for a in rows:
        if low in (a.get("account_name") or "").lower():
            return {
                "account_id": a.get("account_id"),
                "account_name": a.get("account_name"),
                "account_type": a.get("account_type"),
            }
    names = ", ".join(a.get("account_name", "") for a in rows[:25]) or "(none)"
    raise RuntimeError(
        f"No account matching {name!r} (type={account_type or 'any'}). Some available: {names}."
    )


async def resolve_paid_through(name: str) -> dict:
    """Resolve a paid-through (bank/cash) account by id or name."""
    needle = name.strip()
    res = await books_request("bankaccounts")
    rows = (res["body"] or {}).get("bankaccounts") or [] if res["status"] == 200 else []
    if needle.isdigit() and len(needle) > 8:
        for a in rows:
            if str(a.get("account_id")) == needle:
                return {"account_id": needle, "account_name": a.get("account_name", "")}
        return {"account_id": needle, "account_name": ""}
    low = needle.lower()
    for a in rows:
        if (a.get("account_name") or "").lower() == low:
            return {"account_id": a.get("account_id"), "account_name": a.get("account_name")}
    for a in rows:
        if low in (a.get("account_name") or "").lower():
            return {"account_id": a.get("account_id"), "account_name": a.get("account_name")}
    names = ", ".join(a.get("account_name", "") for a in rows) or "(none)"
    raise RuntimeError(f"No paid-through account matching {name!r}. Available: {names}.")


async def resolve_vendor(name: str) -> str | None:
    """Resolve a vendor contact_id by name. Returns None if blank/not found."""
    needle = (name or "").strip()
    if not needle:
        return None
    if needle.isdigit() and len(needle) > 8:
        return needle
    res = await books_request("contacts", params={"contact_type": "vendor", "per_page": 200})
    rows = (res["body"] or {}).get("contacts") or [] if res["status"] == 200 else []
    low = needle.lower()
    for c in rows:
        if (c.get("contact_name") or "").lower() == low or (
            c.get("company_name") or ""
        ).lower() == low:
            return c.get("contact_id")
    for c in rows:
        if low in f"{c.get('contact_name', '')} {c.get('company_name', '')}".lower():
            return c.get("contact_id")
    return None
