# Campaign Contract / Example: US independent breweries / DRAFT / 2026-09-24

This is a fictional worked example. The seller, an invented brewhouse-scheduling software company,
does not exist. The segment is real so that the matching table JSON
(`.claude/skills/design-clay-table-json/references/example.flow.json`) can be imported and run.

## 1. Campaign Overview

<details><summary>Campaign in a nutshell</summary>

We find small and mid-sized US companies whose public profile says they brew beer.

A cheap AI check reads each company's own description and keeps only real breweries: craft
breweries, brewpubs and production breweries. Coffee, tea, kombucha and spirits makers, suppliers,
trade bodies and agencies are left out.

For each brewery that passes, a second AI column writes the first sentence of a cold email that
opens on one concrete fact the brewery says about itself. It never mentions the software and never
invents anything.

</details>

**Starting Point:** a company search for US breweries with 11 to 200 staff.

---

## 2. Find breweries

| Field | Contract |
|---|---|
| Source | Find Companies |
| Column | Source \| US Independent Breweries |
| Geography | United States (at least one location) |
| Industry | Industry / Included:<br><br>Food and Beverage Manufacturing, Food and Beverage Services, Beverage Manufacturing |
| Description | Description / Contains:<br><br>brewery, brewing, craft beer |
| Company Size | 11-50, 51-200 |
| Limit | 10 |
| Stage result | One row per company |

---

## 3. Company name

| Field | Contract |
|---|---|
| Column | Name / Formula |
| Entry | Source \| US Independent Breweries: name |
| Runs when | The source row exists |

---

## 4. Company domain

| Field | Contract |
|---|---|
| Column | Domain / Formula |
| Entry | Source \| US Independent Breweries: domain |
| Runs when | The source row exists |
| Downstream | A people table would take the company domain from here (never from the person record) |

---

## 5. Company LinkedIn page

| Field | Contract |
|---|---|
| Column | LinkedIn URL / Formula |
| Entry | Source \| US Independent Breweries: social_urls.linkedin |
| Runs when | The source row exists |
| Downstream | A people search would be scoped to qualified companies by this URL (never by domain) |

---

## 6. Company description

| Field | Contract |
|---|---|
| Column | Description / Formula |
| Entry | Source \| US Independent Breweries: description |
| Runs when | The source row exists |

---

## 7. Prompt / Is this a brewery?

| Field | Contract |
|---|---|
| Column | Qualify Brewery / Use AI / GPT 4.1 Mini |
| We Qualify | Craft breweries, brewpubs and production breweries that brew beer under their own brands |
| We Exclude | Coffee, tea, kombucha, spirits and cider makers; ingredient and equipment suppliers; trade bodies, media, education and marketing agencies; any company whose description does not say it brews beer |
| Entry | Name, Description |
| Model | `gpt-5-nano` (an example id; name the exact id your workspace offers). The table JSON binds it as `${bindings.models.default}`, so `models.default` in rex-config.json is set to this id |
| Model Account | the workspace's AI account (`authAccounts.llm`) |
| Runs when | The row has a description |
| Result | isBrewery: yes or no; reason |

<details><summary>Prompt - Qualify Brewery / Use AI / GPT 4.1 Mini</summary>

```text
You decide whether a company is an independent beer brewery that brews and sells its own beer.

Qualify: craft breweries, brewpubs and production breweries that brew beer under their own brands.
Reject: coffee, tea, kombucha, spirits or cider makers; ingredient and equipment suppliers; trade bodies, media, education and marketing agencies; any company whose description does not say it brews beer.
Judge only from the name and description below. If they do not say the company brews beer, answer no.

Company name: {Name}
Description: {Description}

Return isBrewery ("yes" or "no") and one sentence of reason that quotes the words in the description you relied on.
```

JSON Schema

```json
{
  "type": "object",
  "properties": {
    "isBrewery": {"type": "string", "enum": ["yes", "no"]},
    "reason": {"type": "string"}
  },
  "required": ["isBrewery", "reason"],
  "additionalProperties": false
}
```

</details>

---

## 8. Show the brewery verdict

| Field | Contract |
|---|---|
| Column | Brewery Qualified? / Formula |
| Role | Show the verdict as its own column |
| Entry | Qualify Brewery: isBrewery |
| Result | yes or no |
| Downstream | Write Opening Line runs only when this is yes; the Demo view shows only yes |

---

## 9. Show the reason

| Field | Contract |
|---|---|
| Column | Qualification Reason / Formula |
| Entry | Qualify Brewery: reason |
| Result | One sentence quoting the description |

---

## 10. Prompt / Opening line

| Field | Contract |
|---|---|
| Column | Write Opening Line / Use AI / GPT 4.1 Mini |
| Role | Write the first sentence of a cold email, opening on one fact the brewery states about itself |
| Entry | Name, Description |
| Model | `gpt-5-nano` (an example id; name the exact id your workspace offers). The table JSON binds it as `${bindings.models.default}`, so `models.default` in rex-config.json is set to this id |
| Model Account | the workspace's AI account (`authAccounts.llm`) |
| Runs when | Brewery Qualified? is yes |
| Result | openingLine |

<details><summary>Prompt - Write Opening Line / Use AI / GPT 4.1 Mini</summary>

```text
Write the first sentence of a cold email to the owner of the brewery below. The sender sells brewhouse scheduling software (a fictional company used as an example).

Open on one concrete fact from the description (a beer, the brewery's history or its taproom). Write the company name the way a person says it, without legal suffixes or symbols. Do not mention the software, do not praise, do not invent anything the description does not say. One sentence, under 25 words.

Company name: {Name}
Description: {Description}
```

JSON Schema

```json
{
  "type": "object",
  "properties": {"openingLine": {"type": "string"}},
  "required": ["openingLine"],
  "additionalProperties": false
}
```

</details>

---

## 11. Show the opening line

| Field | Contract |
|---|---|
| Column | Opening Line / Formula |
| Entry | Write Opening Line: openingLine |
| Result | One sentence |

---

## 12. Demo view

| Field | Contract |
|---|---|
| View | Demo (the table's default view) |
| Shows | Rows where Brewery Qualified? is yes |
| Columns | Source \| US Independent Breweries, Name, Domain, LinkedIn URL, Description, Qualify Brewery, Brewery Qualified?, Qualification Reason, Write Opening Line, Opening Line |
| Hidden | - |
| Target | Every qualified row from a 10-company source |

---
