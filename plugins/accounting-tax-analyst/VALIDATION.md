# Validation

How to validate the `accounting-tax-analyst` plugin before merging or installing.

## Automated checks

Run from the plugin root:

```bash
# 1. Manifest is valid JSON with required fields
python3 -c "
import json
m = json.load(open('.claude-plugin/plugin.json'))
assert m['name'] == 'accounting-tax-analyst'
assert m['version'] == '0.1.0'
assert m['description']
print('plugin.json OK')
"

# 2. All command files exist
for f in accounting-review invoice-workflow tax-summary reconcile-books vendor-customer-review; do
  test -f "commands/$f.md" && echo "commands/$f.md OK" || echo "MISSING: commands/$f.md"
done

# 3. All skill files exist
for s in accounting-tax-analyst wave-accounting freshbooks-accounting xero-accounting zoho-books-accounting odoo-accounting; do
  test -f "skills/$s/SKILL.md" && echo "skills/$s OK" || echo "MISSING: skills/$s/SKILL.md"
done

# 4. All agent files exist
for a in accounting-tax-analyst invoice-specialist tax-reviewer reconciliation-specialist; do
  test -f "agents/$a.md" && echo "agents/$a.md OK" || echo "MISSING: agents/$a.md"
done

# 5. Documentation exists
test -f README.md && test -f VALIDATION.md && echo "docs OK"

# 6. No hardcoded secrets (should print nothing)
grep -rniE "(api[_-]?key|secret|token|password|bearer )\s*[:=]\s*['\"][A-Za-z0-9]" \
  --include="*.md" --include="*.json" . || echo "no secrets OK"

# 7. No destructive operations offered (matches should only be prohibitions)
grep -rniE "delete|void|unlink" commands/ skills/ agents/ | grep -viE "not supported|never|decline|out of scope|do not|don't|excluded?|deleted?/|VOIDED" \
  && echo "REVIEW matches above" || echo "no destructive actions OK"

# 8. Write-safety language present in every command and platform skill
grep -rLi "confirmation" commands/ && echo "REVIEW files above" || echo "confirmation language OK"

# 9. Tax disclaimer present
grep -rli "not certified tax" commands/tax-summary.md skills/accounting-tax-analyst/SKILL.md README.md \
  && echo "disclaimer OK"
```

## Manual checklist

- [ ] `plugin.json` parses; name/version/description correct
- [ ] 5 command files present with valid YAML frontmatter (`description`)
- [ ] 6 SKILL.md files present with valid frontmatter (`name`, `description`)
- [ ] 4 agent files present with valid frontmatter (`name`, `description`)
- [ ] README and VALIDATION present
- [ ] No credentials, API keys, tokens, or hardcoded business/organization/account IDs anywhere
- [ ] No delete/void/unlink workflows offered by default (mentions are prohibitions only)
- [ ] Every write operation (create, send, record payment, post) requires explicit confirmation in the text
- [ ] Tax disclaimer present in `/tax-summary`, shared skill, tax-reviewer agent, and README
- [ ] Author placeholder updated before release

## Manual test scenarios (in Claude Code)

```txt
/plugin install accounting-tax-analyst
/reload-plugins            # or restart Claude Code, per your version
/accounting-tax-analyst:accounting-review
/accounting-tax-analyst:tax-summary 2026 Q2
/accounting-tax-analyst:invoice-workflow list unpaid invoices
/accounting-tax-analyst:reconcile-books June 2026
/accounting-tax-analyst:vendor-customer-review
```

If your Claude Code version exposes bare command names, use `/accounting-review` etc. Adjust install/reload steps to the marketplace conventions of the host repo.

Expected behavior:

1. Commands appear in the `/` autocomplete after reload.
2. `/accounting-review` with no connected platform asks which platform to use rather than fabricating data.
3. `/invoice-workflow send #123` refuses to send without restating details and receiving explicit confirmation.
4. `/tax-summary` output ends with the non-certified-advice disclaimer.
5. Asking any agent to delete an invoice is declined with a pointer to the platform UI.
