# Clay Actions & Data Credits

Source: https://university.clay.com/docs/actions-data-credits

Clay tracks usage with two separate metrics. They are NOT the same thing and deplete independently.

---

## Actions

Actions measure platform orchestration -- enriching data, running AI research, sending data to other tools.

**Cost:** Fractions of a penny each  
**Rate:** 1 action per enrichment, regardless of which provider  
**Rollover:** None -- unused actions expire at end of month  
**Top-up:** Not available -- you can only get more by upgrading plan tier

### What consumes actions

- Enrichments from any provider (1 per enrichment per row)
- AI usage and signals (Claygent, AI columns)
- Clay Sequencer email sends (1 per lead added to a campaign)
- CRM/data warehouse syncs and exports
- HTTP API calls
- Ads audience exports

### What does NOT consume actions

- Sourcing/importing contact lists
- CRM or warehouse imports into Clay
- Formulas, filters, manual data entry
- Data transfers between Clay tables

### Plan tiers (actions/month)

| Plan | Actions/Month | Practical capacity |
|------|---------------|-------------------|
| Launch | 15,000 | ~10,000 records/year enriched |
| Growth | 40,000 | ~50,000 records/year enriched |
| Enterprise | 100,000+ | Millions of records/year |

---

## Data Credits

Data Credits are currency for purchasing data from Clay's 150+ integrated providers.

**Cost:** Several pennies each (meaningfully more expensive than actions)  
**Typical spend:** 6-20 credits per fully enriched record  
**Rollover:** YES -- up to 2x monthly limit (annual plans: up to 15%)  
**Top-up:** Available as one-time purchase (30% premium over plan rate)

### Plan tiers (credits/month)

| Plan | Credits/Month | Volume |
|------|---------------|--------|
| Launch | 2,500-10,000 | ~1,000 records/month |
| Growth | 6,000-100,000 | 1,000-10,000 records/month |
| Enterprise | 100,000+ | 10,000+ records/month |

### Practical example

Enriching 100 contacts with LinkedIn profiles + emails via Clay marketplace = ~95 data credits.  
Using your own API key for email enrichment = ~50 data credits (45-credit saving on 100 contacts).

---

## Key Rules

### Using your own API keys

When you connect external API credentials (Apollo, ZoomInfo, Clearbit, etc.) to a Clay enrichment:

- **Data Credits:** 0 -- the external provider bills you directly
- **Actions:** Still 1 per enrichment -- Clay still does the orchestration

This is the primary lever for reducing data credit burn. 50-80% savings are typical for high-volume enrichments.

### Workflow design for credit efficiency

1. **Filter before enriching** -- only run enrichments on rows that pass ICP criteria. Never enrich the full list.
2. **Test on small batches first** -- 50-100 rows before scaling. This is how you measure burn rate.
3. **Use conditional logic** -- only run expensive enrichments when cheaper signals pass a threshold.
4. **Avoid redundant enrichments** -- if a field is already populated, skip the enrichment.

### What happens on downgrade

- Current billing cycle: Data Credit balance is preserved
- After cycle ends: balance caps at the new (lower) plan limit
- Data in tables remains intact regardless of plan

---

## Usage notes from real builds

### Start small when credits are tight

Check the live credit balance before a new workflow (`clay.credit_balance()` in Rex, or Settings in the Clay app) and start every new workflow with a small test list.

### Estimating burn for an accounts + people workflow

A typical workflow (accounts + people, 5-8 enrichments per row) costs roughly:

- People table: ~6 actions + ~6-8 credits per row
- Accounts table: ~4 actions + ~4-6 credits per row

**How to measure accurately:** Run 100-150 companies through a test batch. Divide total credits consumed / rows processed = cost-per-row. Multiply up to know max list size before top-up is needed.

**Rule of thumb for test lists:** 100-150 accounts (~300-600 people rows) = ~2,500-4,000 credits for a full enrichment run. That leaves safe headroom on a ~10k balance with enough data to establish a reliable burn rate.
