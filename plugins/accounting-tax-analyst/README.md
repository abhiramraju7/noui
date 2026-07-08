# accounting-tax-analyst

A Claude Code plugin providing a structured accounting and tax automation layer for NoUI workflows. It packages skills, slash commands, and agents for inspecting accounting data, managing invoices, analyzing tax-relevant records, and performing safe bookkeeping workflows.

## Supported platforms

| Platform | Skill | Notes |
|---|---|---|
| Wave | `wave-accounting` | Business, customers, accounts, products, invoices, send, payments |
| FreshBooks | `freshbooks-accounting` | Clients, invoices, items, expenses, payments |
| Xero | `xero-accounting` | Contacts, invoices/bills, accounts, items, payments, tax rates, reports |
| Zoho Books | `zoho-books-accounting` | Customers, vendors, invoices, items, chart of accounts, payments, taxes, reports |
| Odoo | `odoo-accounting` | Partners, invoices, bills, products, chart of accounts, payments, journal entries, taxes |

## Folder structure

```txt
accounting-tax-analyst/
  .claude-plugin/
    plugin.json                     # Plugin manifest
  commands/
    accounting-review.md            # /accounting-review
    invoice-workflow.md             # /invoice-workflow
    tax-summary.md                  # /tax-summary
    reconcile-books.md              # /reconcile-books
    vendor-customer-review.md       # /vendor-customer-review
  skills/
    accounting-tax-analyst/SKILL.md # Shared analyst role, output formats, safety rules
    wave-accounting/SKILL.md
    freshbooks-accounting/SKILL.md
    xero-accounting/SKILL.md
    zoho-books-accounting/SKILL.md
    odoo-accounting/SKILL.md
  agents/
    accounting-tax-analyst.md       # General books/records review (read-only)
    invoice-specialist.md           # Invoice lifecycle (confirmed writes)
    tax-reviewer.md                 # Non-certified tax review (read-only)
    reconciliation-specialist.md    # Discrepancy detection (read-only)
  README.md
  VALIDATION.md
```

Commands, skills, and agents are auto-discovered by Claude Code from their default directories, so the manifest doesn't declare them explicitly.

## Installation

From a marketplace containing this plugin:

```txt
/plugin marketplace add <marketplace-repo-or-path>
/plugin install accounting-tax-analyst
```

Or for local development, add the plugin directory to a local marketplace and install from there. Restart or `/reload-plugins` afterwards (naming may vary by Claude Code version).

The plugin assumes accounting platform access is provided by your NoUI setup (e.g., authenticated MCP servers or CLI tooling for Wave/FreshBooks/Xero/Zoho Books/Odoo). The plugin contains **no credentials** and never hardcodes business, organization, or account IDs.

## Usage

```txt
/accounting-review
/invoice-workflow
/tax-summary
/reconcile-books
/vendor-customer-review
```

If your Claude Code version namespaces plugin commands:

```txt
/accounting-tax-analyst:accounting-review
/accounting-tax-analyst:invoice-workflow
/accounting-tax-analyst:tax-summary
/accounting-tax-analyst:reconcile-books
/accounting-tax-analyst:vendor-customer-review
```

Examples:

```txt
/accounting-review wave
/invoice-workflow create invoice for Acme Corp, 10 hrs consulting at $150/hr
/tax-summary 2026 Q2
/reconcile-books June 2026
/vendor-customer-review customers only
```

## Commands

| Command | Purpose | Writes? |
|---|---|---|
| `/accounting-review` | Business status, unpaid/overdue invoices, record quality, bookkeeping risks | No |
| `/invoice-workflow` | List/inspect invoices; draft, send, record payments | Only with explicit confirmation |
| `/tax-summary` | Revenue/expense summary, tax categories, missing records, non-certified tax review | No |
| `/reconcile-books` | Invoice↔payment matching, balance consistency, reconciliation checklist | No |
| `/vendor-customer-review` | Duplicates, incomplete contacts, cleanup suggestions | No |

## Skills

`accounting-tax-analyst` (shared) defines the analyst role, data-inspection discipline, standard output format, tax disclaimer, and write-safety rules. The five platform skills describe each platform's supported read/write operations, safety requirements, common workflows, and edge cases. Load the shared skill plus the platform skill matching the user's system.

## Agents

| Agent | Focus | Write policy |
|---|---|---|
| `accounting-tax-analyst` | General books and records review | Read-only |
| `invoice-specialist` | Invoice creation, sending, payment recording | Per-action confirmation |
| `tax-reviewer` | Non-certified tax summaries | Read-only |
| `reconciliation-specialist` | Discrepancy detection, reconciliation checklists | Read-only |

No agent performs destructive actions, and no agent chains multiple writes on a single confirmation.

## Safety model

**Reads** (list/get invoices, customers, vendors, accounts, items, payments, taxes, reports) are performed when needed, without ceremony.

**Writes** require clear user intent for the specific action, with the full proposed change shown first:

- Create customer/vendor/partner — confirm details before creating
- Create invoice — always draft first; confirm contents before creating
- Send invoice — explicit confirmation restating number, recipient, amount
- Record/register payment — explicit confirmation restating invoice, amount, date, account
- Create/modify tax records — explicit confirmation; platform UI preferred

**Never**: deleting or voiding records (not supported by default); inventing amounts, names, tax rates, or IDs; hardcoding credentials, API keys, tokens, or business/organization/account IDs; performing a second write under a previous confirmation.

All outputs distinguish observed data (from API responses) from inferred conclusions (analysis), and flag partial datasets (pagination, unsupported endpoints).

## Odoo notes

Odoo deployments vary (Community/Enterprise, versions, localization modules, multi-company). The `odoo-accounting` skill is written generically against core models (`res.partner`, `account.move`, `account.payment`, `account.account`, `account.tax`, `product.product`) and instructs Claude to verify availability rather than assume. Posting an invoice (draft → posted) is treated as a distinct ledger write with its own confirmation. `unlink`/delete and cancelling posted moves are not supported.

## Tax disclaimer

All tax-oriented outputs from this plugin are for **operational review only** and are **not certified tax, accounting, or legal advice**. Figures come from the connected accounting platform and are not independently audited. Consult a qualified tax professional before filing or making tax decisions.

## Troubleshooting

- **Commands not appearing**: verify install (`/plugin` list), reload plugins or restart, and check `plugin.json` parses as valid JSON.
- **Namespaced vs. bare commands**: depending on Claude Code version and conflicts, commands may be exposed as `/accounting-review` or `/accounting-tax-analyst:accounting-review`. Try both.
- **"Platform not reachable"**: this plugin provides guidance, not connectivity. Ensure the platform's NoUI integration (MCP server/CLI) is configured and authenticated separately.
- **Skill not triggering**: skills load based on their descriptions; mention the platform by name (e.g., "review my Xero invoices").
- **Partial data**: large accounts paginate; summaries state when they cover a partial dataset. Narrow the period or scope.

## Roadmap

- MCP server integrations per platform (bundled `.mcp.json` definitions)
- Platform-specific runtime adapters/scripts for high-volume reads
- Automated tests for command/skill/agent discovery
- Additional platforms: QuickBooks Online, Sage, Kashoo
- Report export support (CSV/XLSX summaries of reviews and reconciliation checklists)
- Multi-currency consolidation helpers
