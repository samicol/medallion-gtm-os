---
name: copy-iron-laws
description: "The 14 non-negotiable rules of campaign copy. Read before writing any copy. Violating these = bad copy."
---

# Copy Iron Laws

These are non-negotiable. Every piece of copy, email or LinkedIn DM, must satisfy all 14. Read this before every copy generation session.

> **Related docs:** `knowledge-base/playbooks/copy-frameworks.md` (SPARK framework, 6 archetypes, follow-up stack), `knowledge-base/playbooks/linkedin-dm-frameworks.md` (LinkedIn DM specifics), `knowledge-base/playbooks/workflow-anatomy.md` (signal stacking, narrative routing), `knowledge-base/playbooks/copy-bans.yaml` (banned characters, words, phrases), the `/campaign-copy` skill (the step-by-step procedure for generating copy).
>
> **Syntax:** variables are written `{{snake_case}}` and spintax `{option1|option2}`. Convert both to your sequencer's syntax at export.

---

## Structural Laws (How Copy is Built)

### 1. Three Campaign Types

Not every campaign starts with a signal. Know which type you're writing:

**Signal-based:** A mother intent triggers the campaign, hiring, funding, new leadership, tech usage, job change, website visit. Line 1 references the signal without being explicit about it. The whole goal is to understand the situation the prospect is in, not show them what you saw about them.

**Bait campaigns:** You lead with something valuable for the prospect, Form D filing intel they haven't seen, competitive data, market research. The bait earns attention before you pitch. Also called Permissionless Value Proposition (PVP)

**Niche-specific:** No signal, but the right pain for the right niche. Copy is built on understanding the ICP's specific challenges and creating compelling messaging around that pain. The relevance comes from knowing their world, not from a triggering event.

Each type has a different Line 1 strategy, but the rest of the email structure (conditional waterfall, static value prop, matched social proof) applies to all three.

### 2. The Conditional Waterfall

Dynamic lines route based on secondary enrichments. This is the engine that makes copy feel personally written at scale.

**How it works:**
- Identify which lines in the email are DYNAMIC (change based on signals) vs STATIC (same for everyone, spintaxed)
- For each dynamic line, write ALL conditional variations before sending
- Priority order matters: best signal match first, fallback last
- Every dynamic line MUST have a fallback, if no signals match, what does the prospect see?

**Example waterfall for Line 2:**
```
+ FUNDRAISING: "Doing X after a raise is..."
+ HYPERGROWTH: "Your growth pace means..."
+ NEW LEADERSHIP (to the leader): "Stepping into a new role means..."
+ NEW LEADERSHIP (to the founder): "Now that you've brought on..."
+ OFFSHORE HEADCOUNT: "My research shows you have talent in..."
FALLBACK: "Most companies at your stage..."
```

### 3. Static Lines Earn Their Place

Value prop and CTA lines are static because they've been tested and proven. Don't reinvent them per lead.

- Use spintax (`{option1|option2}`) for natural variation
- Never use spintax for fundamentally different messages, if the meaning changes, it's a separate conditional route
- Static doesn't mean boring, it means battle-tested

### 4. Social Proof is Matched, Not Generic

Every social proof line must connect to the prospect's world:

- **By tech stack:** "We built production systems in React for Acme Health..." (only if prospect uses React)
- **By industry:** "Tech startups like Acme Analytics & Northwind Labs..." (only if prospect is a tech startup)
- **By company stage:** "Series A companies like yours typically..." (only if stage matches)

If no match exists, use the closest analog or skip the social proof line entirely. Generic proof is worse than no proof, it signals you're mass-sending.

Build a **social proof matrix**: rows = case studies (only names authorized in `context/messaging/facts.md`), columns = tech stack / industry / stage they match to.

---

## Voice Laws (How Copy Sounds)

### 5. 60 Words Optimal, 120 Ceiling

60 words is the target. It's hard to reach, most emails land between 80-120, but aim for it. 120 is the real ceiling.

- Follow-ups get shorter, not longer
- One sentence per line, mobile-first formatting
- If it doesn't scan in 3 seconds on a phone, rewrite
- No walls of text, break after every thought

### 6. Earn the Reply, Don't Demand It

CTAs are questions or relevance checks:

**Good:** "Relevant?", "Can I send it over?", "Worth a conversation?", "How's that search going?", "Is your team already running plays like this?"

**Bad:** "Book a call", "Let me know when you're free", "Schedule 15 minutes"

The goal is to confirm their situation, not to close. Step 1 earns the reply. Step 2 earns the meeting. Never combine.

### 7. 3:1 Rule

3 parts about the prospect's world, 1 part about you.

If half your email talks about your product or service, rewrite it. The prospect's situation, challenges, and context come first. You earn the right to talk about yourself only after demonstrating you understand their world.

### 8. Adapt to Your Company's Voice

Every company sounds different. A direct, scrappy, GTM-native voice sounds nothing like an executive, measured, enterprise-ready one, or a warm, founder-to-founder one.

**Before writing copy:**
- Read your existing messaging, website, and positioning (`context/messaging/`, `context/brand-kit/brand.md`, `context/positioning/`)
- Note their tone: formal vs casual, technical vs accessible, aggressive vs consultative
- Match the register, emails should read like a conversation between peers in the prospect's industry

**Universal rule:** The email reads like a peer talking to a peer. Not a sales deck. Not a marketing brochure. A conversation.

### 9. Spintax is Light and Purposeful

`{option1|option2|option3}` creates natural variation so emails don't look templated.

**Use spintax for:**
- Greetings: `{Hey|Hi|Hello}`
- Connectives: `{so|which is why|that's why}`
- Closings: `{Best,|Cheers,|Talk soon,}`
- Soft language swaps: `{scaling|growing}`, `{hard|challenging|difficult}`

**Never use spintax for:**
- Fundamentally different messages (that's a conditional route)
- Value propositions (test them as separate variants, don't randomize)
- Social proof (must be deliberately matched)

If the meaning of the sentence changes, it's NOT spintax, it's a separate conditional path.

> **NEARSHORING OVERRIDE (standing standard since 2026-08-06):** For nearshoring campaigns, spintax is NOT light. Every line, dynamic AND static, gets **3 LINE-level variants** (three full same-meaning paraphrases of the whole line, not word swaps), living inside each scenario route. Subject line: **aim for 10 variants**. Signature: **3 variants** (a per-inbox signature variable can hold spintax if your sequencer resolves it at send time). And **rotate copy often**. This is a deliverability requirement: a placement test (2026-08-06, see `/inbox-placement-test`) proved Microsoft was fingerprinting the campaign copy itself (fresh copy flipped O365 placement 0/8 → 8/8 on the same inboxes). Line-level is required over word-level, it is also grammatically safer (each variant is a complete sentence). This override applies to nearshoring only; scenario routing (Law 2) still governs anything where the MEANING changes.

---

## System Laws (How Copy Scales)

### 10. Each Follow-Up Adds New Value

- **Email 2:** New social proof, a case study, a different angle, or a resource. It must say something Email 1 didn't.
- **Email 3:** Final touch, urgency ("2026 roadmap"), breakup ("this will be my last message"), or referral ("who else should I talk to?").
- **Never:** "Just bumping this to the top of your inbox." If you have nothing new to say, don't send.

Each email in the sequence has one job. The sequence as a whole tells a story, not the same story three times.

### 11. Data Beats Intuition

- Write 3+ variants of Line 1 (the dynamic opener)
- Test with 200+ sends per variant minimum
- Let **positive reply rate** pick the winner, not total reply rate (which includes "not interested")
- Refresh subject lines every 4-6 weeks
- Refresh email body copy every 8-12 weeks
- **Nearshoring / fingerprint-sensitive fleets: rotate more aggressively than the above.** Copy fingerprinting (esp. Microsoft) burns a body over time regardless of variant count, so treat rotation as a standing deliverability habit, not a quarterly chore. Heavy per-line spintax (Law 9 nearshoring override) slows the burn; rotation resets it.
- Your instinct about what works is often wrong. Let the numbers decide.

### 12. Avoid Cliches

- Avoid sounding like every cold email saying "I saw" or "I noticed" or "Looks like" as openers
- No "just following up" or "just circling back"
- No fillers or pleasantries

### 13. No Empty Flattery or Filler

Never write lines that sound specific but say nothing. If you can't name the actual thing, cut the line entirely.

**Bad:** "especially at a company doing what {{company_name}} is doing", What are they doing? This says nothing.
**Bad:** "a company like yours" with no qualifier, Like them how?

If you reference the company, it must be tied to a real signal or concrete detail. Otherwise it's filler and the reader knows it.

### 14. Guess Their Situation, Don't Diagnose Their Gaps

Be assumptive about their **feeling or situation** (new role pressure, board expectations, growth pace). Never assume they're **missing something** or **failing at something**, you don't know that.

**Bad:** "every month without a proper GTM engine is pipeline left on the table", Assumes they don't have one.
**Bad:** "the difference between cost and ROI", Assumes they're not getting ROI.
**Bad:** "who's building the workflows?", Assumes nobody is.

**Good:** "I imagine pipeline is probably top of mind", Guessing their situation.
**Good:** "that pressure probably compounds fast", Guessing their feeling.
**Good:** "how's the workflow side going?", Asking, not telling.

---

## Quick QA Pass

Before finalizing any copy, run this checklist:

- [ ] Campaign type identified? (signal, bait, or niche) (Law 1)
- [ ] All dynamic lines have complete waterfall + fallback? (Law 2)
- [ ] Static lines use spintax for variation? (Law 3)
- [ ] Social proof matched to prospect's segment? (Law 4)
- [ ] Under 120 words? (aim for 60) (Law 5)
- [ ] CTA is a question, not a demand? (Law 6)
- [ ] 3:1 ratio (prospect vs you)? (Law 7)
- [ ] Matches your company's voice and tone? (Law 8)
- [ ] Spintax is variation only, not different messages? (Law 9)
- [ ] Each follow-up email adds something new? (Law 10)
- [ ] Subject line: lowercase, 3-5 words, no clickbait? (SPARK)
- [ ] All `{{variables}}` are defined and will resolve? (QA)
- [ ] No spam trigger words? (QA)
- [ ] No empty flattery or filler? Every company reference tied to a real signal? (Law 13)
- [ ] Guessing their situation, not diagnosing their gaps? (Law 14)