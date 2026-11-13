# Clay AI Prompts Library

Reusable prompts for Clay enrichment columns (Claygent, OpenAI, formula AI). Ask for any prompt by name.

---

## clean_job_title

**Purpose:** Normalize raw job titles from job postings into clean, email-ready variables.

**Column Name:** `clean_job_title`

**Input:** `{{open_role_title}}` (raw job title from Clay job search)

**Prompt:**

```
You are a job title normalizer. Given a raw job title from a job posting, return a clean, human-readable version that sounds natural in a cold email.

Rules:
- Remove company name, location, salary, and any metadata
- Remove prefixes like "Senior", "Junior", "Lead", "Staff", "Principal", "Sr.", "Jr.", keep it generic
- Remove suffixes like "I", "II", "III", "IV", "Level 1", "Level 2"
- Remove parenthetical text like "(Remote)" or "(Contract)"
- Remove slashes and pick the most common term (e.g., "Software Engineer/Developer" → "Software Engineer")
- Collapse redundant words (e.g., "Software Development Engineer" → "Software Engineer")
- Use title case
- Keep it to 1-4 words max
- If the title contains multiple roles separated by "and" or "&", keep only the first one

Examples:
"Sr. Full Stack Software Engineer (Remote) - React/Node" → "Full Stack Engineer"
"Junior Backend Developer II" → "Backend Developer"
"Lead DevOps / SRE Engineer - Platform Team" → "DevOps Engineer"
"Staff Machine Learning Engineer, AI/ML" → "Machine Learning Engineer"
"Customer Success Manager (CSM) - Enterprise" → "Customer Success Manager"
"VP of Finance & Operations" → "VP of Finance"
"QA Automation Engineer / SDET" → "QA Engineer"
"Executive Assistant to the CEO (Remote, Contract)" → "Executive Assistant"
"Data Entry Specialist Level III - Part Time" → "Data Entry Specialist"
"Social Media & Community Manager" → "Social Media Manager"

Raw job title: {{open_role_title}}

Return ONLY the cleaned title, nothing else.
```

**Used in:** WF#1, WF#4 and WF#5 for nearshore staffing clients, and any hiring intent workflow.

---

## open_role_country

**Purpose:** Extract and normalize the country name from a raw job posting location string. Handles cities, regions, metro areas, abbreviations, and "Greater [City]" formats.

**Column Name:** `open_role_country`

**Input:** `{{open_role_location}}` (raw location from Clay job search)

**Prompt:**

```
You are a location normalizer. Given a raw job location string from a job posting, extract and return ONLY the country name.

Rules:
- Return the full country name, not abbreviations or codes
- If the location contains a city and country, return only the country (e.g., "São Paulo, Brazil" → "Brazil")
- If the location contains a state/region and country, return only the country (e.g., "Jalisco, Mexico" → "Mexico")
- If the location is just a city with no country, infer the country (e.g., "Bogotá" → "Colombia", "Lima" → "Peru")
- If the location uses "Greater [City]" or "[City] Area" or "[City] Metropolitan", infer the country from the city (e.g., "Greater Rio de Janeiro" → "Brazil", "Buenos Aires Metropolitan Area" → "Argentina")
- If the location is a well-known region or area name, infer the country (e.g., "Silicon Valles" → "United States", "Bajío Region" → "Mexico", "Florianópolis Region" → "Brazil")
- If the location says "Remote - Latin America" or "LATAM", return "Latin America"
- If the location lists multiple countries, return only the first one
- If the location contains "Remote" plus a country, return just the country (e.g., "Remote - Argentina" → "Argentina")
- Use the common English name (e.g., "Brasil" → "Brazil", "México" → "Mexico")
- Title case always

Examples:
"São Paulo, Brazil" → "Brazil"
"Remote - Mexico City, MX" → "Mexico"
"Bogotá, Colombia (Remote)" → "Colombia"
"Buenos Aires" → "Argentina"
"LATAM - Remote" → "Latin America"
"Medellín, CO" → "Colombia"
"Santiago, Chile / Remote" → "Chile"
"Remote - LATAM" → "Latin America"
"Lima, Peru (Contract)" → "Peru"
"Montevideo, UY" → "Uruguay"
"San José, CR" → "Costa Rica"
"BR - Remote" → "Brazil"
"Greater Rio de Janeiro" → "Brazil"
"Buenos Aires Metropolitan Area" → "Argentina"
"Guadalajara Area" → "Mexico"
"Greater Belo Horizonte" → "Brazil"
"Campinas Region" → "Brazil"
"Córdoba Province" → "Argentina"
"Valparaíso Region" → "Chile"
"Antioquia, Colombia" → "Colombia"

Raw location: {{open_role_location}}

Return ONLY the country name, nothing else.
```

**Used in:** WF#1, WF#4 and WF#5 for nearshore staffing clients, and any hiring intent workflow.

---

## role_summary

**Purpose:** Scrape a job posting URL and summarize the core responsibility in 10 words or less, starting with "capable of". Falls back to the clean job title if the link is inaccessible.

**Column Name:** `role_summary`

**Input:** `{{job_link}}` (URL to the job posting), `{{clean_job_title}}` (fallback if link is broken)

**Prompt:**

```
You are a job posting summarizer. Given a job posting URL, scrape the page and summarize the core role responsibility in no more than 10 words. The summary MUST begin with "capable of".

Rules:
- Read the job posting and identify the single most important responsibility or skill
- Summarize it in 10 words max, starting with "capable of"
- Focus on what the person DOES, not who they are
- Use natural, conversational language that sounds good in a cold email
- No jargon dumping or keyword stuffing
- Pick the most specific and compelling responsibility, not a generic one
- NEVER end the summary with a period or full stop
- If the job link is inaccessible, broken, or returns no content, use the job title provided in {{clean_job_title}} to generate a reasonable summary based on common responsibilities for that role

Examples:
GTM Engineer → "capable of delivering sophisticated GTM workflows on Clay and n8n"
Software Engineer (React/Node) → "capable of building full stack web applications"
DevOps Engineer → "capable of managing cloud infrastructure and CI/CD pipelines"
Data Engineer → "capable of building and maintaining scalable data pipelines"
Machine Learning Engineer → "capable of developing and deploying production ML models"
Product Manager → "capable of driving product strategy and cross-functional execution"
Customer Success Manager → "capable of managing enterprise accounts and reducing churn"
Operations Manager → "capable of streamlining operations and scaling internal processes"
Finance Manager → "capable of overseeing financial planning and budget management"
HR Manager → "capable of leading talent strategy and people operations"
Marketing Manager → "capable of driving demand generation and brand growth"
Project Manager → "capable of leading cross-functional projects from planning to delivery"
Account Executive → "capable of managing full-cycle B2B sales and closing deals"
QA Engineer → "capable of building test automation and ensuring product quality"
Executive Assistant → "capable of managing executive operations and strategic coordination"

Job posting URL: {{job_link}}
Job title (fallback): {{clean_job_title}}

Return ONLY the summary starting with "capable of", nothing else.
```

**Used in:** WF#1, WF#4 and WF#5 for nearshore staffing clients, and any hiring intent workflow.

---

## clean_company_name

**Purpose:** Normalize raw company names into clean, email-ready versions. Handles legal suffixes, domains, symbols, location info, and branding edge cases.

**Column Name:** `clean_company_name`

**Input:** `{{company_name_raw}}` (raw company name from Clay)

**Prompt:**

```
You are a company name normalizer. Given a raw company name, return a clean version that sounds natural in a cold email.

Rules:
- Remove legal suffixes: Inc, Inc., LLC, Ltd, Ltd., L.L.C., Corp, Corp., Corporation, Co., Company, Group, Holdings, PLC, GmbH, S.A., S.A.S., S.R.L., B.V., Pty, Pty Ltd, LP, LLP, AG, SE, NV, SARL
- Remove generic business descriptors: Technologies, Solutions, Software, Labs, Digital, Studios, Services, Consulting, Partners, Enterprises, Global, International, Worldwide, unless removing them would leave a single generic word or meaningless name
- Remove trailing punctuation like commas, periods, dashes after removing suffixes
- Keep the brand name exactly as stylized if it's clearly intentional (e.g., "HubSpot" stays "HubSpot", not "Hubspot")
- Preserve intentional lowercase branding (e.g., "eBay" stays "eBay", "dbt Labs" stays "dbt Labs")
- If the name is an acronym or all caps and clearly a brand, keep it (e.g., "IBM", "AWS", "SAP")
- If the name is all caps but NOT an acronym, convert to title case (e.g., "ACME SOLUTIONS" → "Acme")
- Remove "The" prefix only if the company is not commonly known with it (e.g., "The Home Depot" stays, "The Acme Group LLC" → "Acme")
- Remove parenthetical text like "(formerly XYZ)", "(a Division of ABC)", or stock tickers like "(AAPL)"
- If the name contains "DBA" or "d/b/a", use only the name after it
- Remove trademark symbols: ™, ®, ©
- Remove emojis
- If the input is a domain/URL (contains .com, .io, .co, .ai, .org, etc.), extract the brand name and title case it (e.g., "acme.io" → "Acme", "www.coolbrand.com" → "CoolBrand")
- Remove location info after dashes or pipes (e.g., "Acme - San Francisco" → "Acme", "Acme | NYC" → "Acme")
- Keep ampersands (&) as-is
- Keep numbers as-is (e.g., "M37 Ventures" stays "M37 Ventures")
- Trim any extra whitespace
- NEVER end with a period, comma, or trailing punctuation

Examples:
"Acme Solutions, Inc." → "Acme"
"HubSpot, Inc" → "HubSpot"
"SPECTRUM VOIP LLC" → "Spectrum VoIP"
"The Webster Group Holdings, Ltd." → "The Webster"
"FlipSystem Corporation" → "FlipSystem"
"Mad Mobile, Inc. (formerly Mobile Solutions)" → "Mad Mobile"
"SAVYU S.A.S." → "SavYu"
"m37 ventures llc" → "M37 Ventures"
"Coinigy, Inc." → "Coinigy"
"Smith & Wesson Corp." → "Smith & Wesson"
"ABC COMPANY DBA CoolBrand" → "CoolBrand"
"  Acme Solutions,  Inc.  " → "Acme"
"Brightpath, LLC" → "Brightpath"
"Northwind Ltd." → "Northwind"
"acme.io" → "Acme"
"www.coolbrand.com" → "CoolBrand"
"Apple Inc. (AAPL)" → "Apple"
"Acme - San Francisco" → "Acme"
"Acme | Enterprise Solutions Division" → "Acme"
"eBay Inc." → "eBay"
"dbt Labs, Inc." → "dbt Labs"
"Stripe™" → "Stripe"
"🚀 RocketCo LLC" → "RocketCo"
"Digital Ocean Technologies, Inc." → "Digital Ocean"
"MongoDB, Inc." → "MongoDB"
"Palo Alto Networks, Inc." → "Palo Alto Networks"

Raw company name: {{company_name_raw}}

Return ONLY the cleaned company name, nothing else.
```

**Used in:** All workflows. Universal enrichment.

---

## clean_first_name

**Purpose:** Extract and clean the first name from a raw name field. Removes honorifics (Dr, Mr, Mrs, etc.), suffixes (Jr, Sr, III, MD, PhD, etc.), extra whitespace, and non-alpha characters. Returns title case.

**Column Name:** `clean_first_name`

**Type:** Clay Formula (not AI prompt)

**Input:** `{{First Name}}` (raw first name from Clay)

**Formula:**

```
{{First Name}}?.toString()?.trim()?_.startCase({{First Name}}?.toString()?.trim()?.replace(/\s+/g," ")?.replace(/^(?:(?:dr|mr|mrs|ms|miss|mx|sir|madam)\.?\s+)+/i,"")?.replace(/\b(?:jr|sr|iii|iv|md|phd|dds|dmd|do|esq)\b\.?/ig,"")?.trim()?.split(" ")?.[0]?.replace(/^[^a-zA-Z]+|[^a-zA-Z]+$/g,"")?.toLowerCase()):{{First Name}}
```

**What it does step by step:**
1. Trims whitespace
2. Collapses multiple spaces into one
3. Strips honorific prefixes (Dr., Mr., Mrs., Ms., Miss, Mx, Sir, Madam)
4. Strips suffixes (Jr, Sr, III, IV, MD, PhD, DDS, DMD, DO, Esq)
5. Takes only the first word (first name)
6. Removes leading/trailing non-alpha characters
7. Converts to title case

**Used in:** All workflows. Universal enrichment.

---

## extract_latam_hire

**Purpose:** From a lookup column that returns one or more LatAm employees, extract the full name and country of a single hire (preferring the most senior). Returns JSON for easy formula parsing into two columns.

**Column Name:** `latam_hire_extract` (then split into `latam_hire_full_name` + `latam_country`)

**Input:** `{{latam_employees_lookup}}` (lookup column from LatAm headcount table), `{{company_name}}`

**Prompt:**

```
You are given a list of employees at {{company_name}} who are based in Latin America.

Input: {{latam_employees_lookup}}

From this list, extract exactly ONE employee. Pick the most senior person if titles are available, otherwise pick the first one.

Return ONLY a JSON object with two fields:
- "full_name": the employee's full first and last name
- "country": the Latin American country they are based in

Example output:
{"full_name": "Carlos Mendoza", "country": "Argentina"}

Rules:
- If only one employee exists, return that one
- If multiple exist, prefer the most senior by title. If titles are equal or unavailable, return the first one
- Country must be the specific country (e.g. "Colombia"), not "Latin America" or "LatAm"
- If the country is ambiguous or not clearly LatAm, return your best guess based on available data
- Return ONLY the JSON object, nothing else
```

**Post-processing formulas:**
- `latam_hire_full_name`: `JSON.parse({{latam_hire_extract}}).full_name`
- `latam_country`: `JSON.parse({{latam_hire_extract}}).country`

**Used in:** WF#3.C and WF#1.B for nearshore staffing clients, and any active headcount workflow targeting LatAm.

---

## icp_industry_check

**Purpose:** Verify whether a company operates in Tech, SaaS, Fintech, Healthcare Tech, or Enterprise Software. Returns a JSON object with a boolean result, category, rationale, and confidence level.

**Column Name:** `icp_industry_check`

**Input:** `{{company_name}}`, `{{domain}}`

**Prompt:**

```
Search the web for {{company_name}} (website: {{domain}}). Review their homepage, About page, product pages, and any available descriptions. Based on everything you find, determine whether this company primarily operates in one of the following categories:

- Technology: companies that build or sell hardware, software, developer tools, infrastructure, cloud services, APIs, or tech platforms
- SaaS: companies that deliver software as a subscription service (B2B or B2C)
- Fintech: companies building financial technology products: payments, lending, banking infrastructure, wealth management, insurance tech, crypto/blockchain
- Healthcare Tech: companies building technology for healthcare delivery, medical records, telemedicine, health data, medical devices with software, pharma tech, or health insurance tech
- Enterprise Software: companies selling software solutions to large businesses: ERP, CRM, HCM, SCM, BI, cybersecurity, compliance, or workflow automation platforms

---

EXAMPLES

TRUE examples:
- Stripe (stripe.com) → Fintech. Sells payment infrastructure APIs to businesses. Core product is software. → true
- Salesforce (salesforce.com) → Enterprise Software. Sells CRM and business automation software on subscription. → true
- Figma (figma.com) → SaaS. Browser-based design platform sold on subscription to teams. → true
- Veeva Systems (veeva.com) → Healthcare Tech + Enterprise Software. Cloud software for life sciences and pharma. → true
- Vercel (vercel.com) → Technology. Cloud platform for deploying frontend applications. Core product is infrastructure. → true

FALSE examples:
- Accenture (accenture.com) → Consulting and systems integration. Uses technology but sells services, not software. → false
- McKinsey (mckinsey.com) → Management consulting. No software product. → false
- Toptal (toptal.com) → Staffing/talent marketplace. Connects clients with freelancers. Not a software product company. → false
- WeWork (wework.com) → Real estate/coworking. Technology is internal, not the core product. → false
- Deloitte (deloitte.com) → Professional services. Audit, tax, consulting. Not a software company. → false
- Kaiser Permanente (kp.org) → Healthcare provider. Delivers medical care, not technology. → false

EDGE CASES:
- A company that is "tech-enabled" but primarily delivers a service (e.g. a tech-enabled recruiting firm) → false
- A company that licenses proprietary software AND delivers services → true if the software is the primary revenue driver
- A fintech company that also has human advisors → true if the core product is the software platform

---

Output TRUE if:
- The company's primary product is software, a platform, or a technology solution
- The company sells subscriptions, licenses, or API access to a tech product
- The company is a marketplace or data platform built on proprietary technology
- The company's core value proposition is delivered through software or technology

Output FALSE if:
- The company is primarily a services firm, agency, consultancy, or systems integrator (even if tech-adjacent)
- The company is primarily staffing, recruiting, or outsourcing
- The company is primarily a law firm, accounting firm, or professional services provider
- The company is primarily in retail, e-commerce, manufacturing, logistics, real estate, media, publishing, or entertainment
- The company is a nonprofit, government entity, or educational institution
- The company uses technology internally but does not sell technology as its core product

If you cannot find enough information to make a confident determination, output result: false with confidence: low.

---

Output as JSON:

{
  "result": true or false,
  "category": "Technology" or "SaaS" or "Fintech" or "Healthcare Tech" or "Enterprise Software" or "None",
  "rationale": "One sentence explaining what the company does and why it qualifies or does not qualify",
  "confidence": "high" or "medium" or "low"
}

Confidence guidance:
- high: Clear evidence from homepage or product pages confirming or ruling out the category
- medium: Some evidence but product vs. services distinction is unclear, or limited web presence
- low: Could not find sufficient information, or the company operates in a genuinely ambiguous space
```

**Post-processing formulas:**
- `icp_result`: `JSON.parse({{icp_industry_check}}).result`
- `icp_category`: `JSON.parse({{icp_industry_check}}).category`
- `icp_rationale`: `JSON.parse({{icp_industry_check}}).rationale`
- `icp_confidence`: `JSON.parse({{icp_industry_check}}).confidence`

**Used in:** WF#13 for a nearshore software development client, and any workflow requiring industry ICP verification.

---

## competitor_check

**Purpose:** Determine whether a company is a direct competitor to a client (example: Acme Dev Partners, nearshore software development / staff augmentation). Flags companies whose primary business is building or placing dedicated engineering teams for US clients.

**Column Name:** `competitor_check`

**Input:** `{{company_name}}`, `{{company_domain}}`, `{{company_industry}}`, `{{company_description}}`

**Prompt:**

```
You are researching a company to determine if they compete with Acme Dev Partners, a nearshore software development firm that builds dedicated engineering teams in Latin America for US companies.

Company: {{company_name}}
Website: {{company_domain}}
Industry: {{company_industry}}
Description: {{company_description}}

A competitor is any company whose PRIMARY business is one or more of:
- Nearshore or offshore software development / staff augmentation
- Dedicated development teams (LatAm, Eastern Europe, Asia, etc.)
- IT outstaffing or outsourcing
- Talent placement for software engineers
- Contract or freelance developer marketplaces

A company is NOT a competitor if they:
- Use offshore talent internally (as a client, not a provider)
- Build software products or SaaS for their own customers
- Do IT consulting, systems integration, or implementation (not team building)
- Provide recruiting/ATS tools but don't place engineers themselves

Research the company using their website and LinkedIn. Focus on what they SELL, not what they USE.

Return your answer as JSON only:
{
  "is_competitor": true/false,
  "confidence": "high/medium/low",
  "business_type": "one-line description of what they actually do",
  "rationale": "1-2 sentences explaining why they are or are not a competitor"
}

Examples:
- Toptal → { "is_competitor": true, "confidence": "high", "business_type": "freelance developer marketplace", "rationale": "Toptal's core product is connecting companies with vetted remote engineers. Direct competitor." }
- Stripe → { "is_competitor": false, "confidence": "high", "business_type": "payments infrastructure SaaS", "rationale": "Stripe sells payment APIs to developers. They may hire engineers but do not sell engineering teams." }
- Outliant → { "is_competitor": true, "confidence": "high", "business_type": "nearshore software development and staff augmentation", "rationale": "Outliant's primary offering is dedicated engineering teams built from LatAm talent, identical to Acme Dev Partners' model." }

Return only the JSON object. No preamble.
```

**Post-processing formulas:**
- `is_competitor`: `JSON.parse({{competitor_check}}).is_competitor`
- `competitor_confidence`: `JSON.parse({{competitor_check}}).confidence`
- `competitor_business_type`: `JSON.parse({{competitor_check}}).business_type`
- `competitor_rationale`: `JSON.parse({{competitor_check}}).rationale`

**Used in:** WF#10 and WF#13 for a nearshore software development client, and any workflow requiring competitor exclusion. Swap in your own client's name and business model.
