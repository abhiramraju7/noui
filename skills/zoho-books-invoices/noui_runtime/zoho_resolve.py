"""Helpers to resolve Zoho Books customers and deposit accounts by name or id."""

from __future__ import annotations

from .zoho_books import books_request


async def resolve_customer(customer: str) -> dict:
    """Resolve a customer by contact_id or (case-insensitive) name.

    Returns {"contact_id", "contact_name", "email"}. Raises if not found.
    """
    needle = customer.strip()
    # Treat a long numeric string as a contact_id directly.
    if needle.isdigit() and len(needle) > 8:
        return {"contact_id": needle, "contact_name": "", "email": ""}

    res = await books_request("contacts", params={"contact_name_contains": needle, "per_page": 200})
    rows = (res["body"] or {}).get("contacts") or [] if res["status"] == 200 else []
    if not rows:
        res = await books_request("contacts", params={"per_page": 200})
        rows = (res["body"] or {}).get("contacts") or [] if res["status"] == 200 else []

    low = needle.lower()
    exact = [c for c in rows if (c.get("contact_name") or "").lower() == low or (c.get("company_name") or "").lower() == low]
    partial = [c for c in rows if low in f"{c.get('contact_name','')} {c.get('company_name','')}".lower()]
    match = (exact or partial or [None])[0]
    if not match:
        raise RuntimeError(f"No customer matching {customer!r}. Create it first with the contacts skill.")
    persons = match.get("contact_persons") or []
    return {
        "contact_id": match.get("contact_id"),
        "contact_name": match.get("contact_name"),
        "email": match.get("email") or (persons[0].get("email") if persons else ""),
    }


async def resolve_account(account: str) -> dict:
    """Resolve a deposit/bank account by id, code, or (case-insensitive) name.

    Returns {"account_id", "account_name"}. Raises if not found.
    """
    needle = account.strip()
    res = await books_request("bankaccounts")
    rows = (res["body"] or {}).get("bankaccounts") or [] if res["status"] == 200 else []
    if needle.isdigit() and len(needle) > 8:
        for a in rows:
            if str(a.get("account_id")) == needle:
                return {"account_id": needle, "account_name": a.get("account_name", "")}
        return {"account_id": needle, "account_name": ""}
    low = needle.lower()
    for a in rows:
        if (a.get("account_name") or "").lower() == low or str(a.get("account_code") or "") == needle:
            return {"account_id": a.get("account_id"), "account_name": a.get("account_name")}
    for a in rows:
        if low in (a.get("account_name") or "").lower():
            return {"account_id": a.get("account_id"), "account_name": a.get("account_name")}
    names = ", ".join(a.get("account_name", "") for a in rows) or "(none)"
    raise RuntimeError(f"No deposit account matching {account!r}. Available: {names}.")
