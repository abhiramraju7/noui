"""Resolve Wave customers, products, and payment accounts by name or id."""

from __future__ import annotations

from .wave_gql import get_business_id, gql_request


async def resolve_customer(customer: str) -> dict:
    needle = customer.strip()
    business_id = await get_business_id()
    if needle.startswith("Q3VzdG9t") or (len(needle) > 20 and ":" not in needle):
        return {"id": needle, "name": "", "email": ""}

    body = await gql_request(
        """
        query ($businessId: ID!, $page: Int!, $pageSize: Int!) {
          business(id: $businessId) {
            customers(page: $page, pageSize: $pageSize) {
              edges { node { id name email } }
            }
          }
        }
        """,
        {"businessId": business_id, "page": 1, "pageSize": 200},
    )
    rows = (
        (((body.get("data") or {}).get("business") or {}).get("customers") or {}).get("edges")
    ) or []
    low = needle.lower()
    for e in rows:
        c = e.get("node") or {}
        if (c.get("name") or "").lower() == low:
            return {"id": c["id"], "name": c.get("name"), "email": c.get("email")}
    for e in rows:
        c = e.get("node") or {}
        if low in (c.get("name") or "").lower():
            return {"id": c["id"], "name": c.get("name"), "email": c.get("email")}
    raise RuntimeError(f"No customer matching {customer!r}. Create one with wave-contacts first.")


async def resolve_or_create_product(name: str, unit_price: float) -> str:
    """Return a product id, creating a sold product if none matches by name."""
    business_id = await get_business_id()
    body = await gql_request(
        """
        query ($businessId: ID!, $page: Int!, $pageSize: Int!) {
          business(id: $businessId) {
            products(page: $page, pageSize: $pageSize) {
              edges { node { id name unitPrice isSold } }
            }
          }
        }
        """,
        {"businessId": business_id, "page": 1, "pageSize": 200},
    )
    rows = (
        (((body.get("data") or {}).get("business") or {}).get("products") or {}).get("edges")
    ) or []
    low = name.strip().lower()
    for e in rows:
        p = e.get("node") or {}
        if (p.get("name") or "").lower() == low and p.get("isSold"):
            return p["id"]

    create = await gql_request(
        """
        mutation ($input: ProductCreateInput!) {
          productCreate(input: $input) {
            didSucceed
            inputErrors { message path }
            product { id name }
          }
        }
        """,
        {
            "input": {
                "businessId": business_id,
                "name": name[:100],
                "unitPrice": unit_price,
                "description": name,
                "isSold": True,
                "isBought": False,
            }
        },
    )
    payload = (create.get("data") or {}).get("productCreate") or {}
    if not payload.get("didSucceed"):
        raise RuntimeError(f"productCreate failed: {payload.get('inputErrors')}")
    return payload["product"]["id"]


async def resolve_payment_account(account: str) -> dict:
    """Resolve a bank/cash account for invoice payments (ASSET subtype)."""
    business_id = await get_business_id()
    needle = account.strip()
    body = await gql_request(
        """
        query ($businessId: ID!, $page: Int!, $pageSize: Int!) {
          business(id: $businessId) {
            accounts(page: $page, pageSize: $pageSize, types: [ASSET]) {
              edges { node { id name subtype { value } } }
            }
          }
        }
        """,
        {"businessId": business_id, "page": 1, "pageSize": 200},
    )
    rows = (
        (((body.get("data") or {}).get("business") or {}).get("accounts") or {}).get("edges")
    ) or []
    if needle.startswith("QWNjb3Vud"):
        return {"id": needle, "name": ""}
    low = needle.lower()
    for e in rows:
        a = e.get("node") or {}
        if (a.get("name") or "").lower() == low:
            return {"id": a["id"], "name": a.get("name")}
    for e in rows:
        a = e.get("node") or {}
        if low in (a.get("name") or "").lower():
            return {"id": a["id"], "name": a.get("name")}
    names = ", ".join((e.get("node") or {}).get("name", "") for e in rows[:15]) or "(none)"
    raise RuntimeError(f"No payment account matching {account!r}. Available: {names}.")
