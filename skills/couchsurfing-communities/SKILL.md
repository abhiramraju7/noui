---
name: couchsurfing-communities
description: Use when the user wants public Couchsurfing place-community links or public destination-page details. Does not access private member data.
---

# Couchsurfing Communities

Read public Couchsurfing place/community pages through Tabby's `POST /execute/fetch`. No CDP or credential extraction is used.

## Operations

- `list_community_links [--query <text>] [--limit 20]`
- `get_place_details --url <couchsurfing-place-url>`

Requires a HEALTHY `couchsurfing` Tabby profile. Private hosts, member identities, groups, and messages are outside this skill.
