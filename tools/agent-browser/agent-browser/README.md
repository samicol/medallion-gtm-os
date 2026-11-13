# agent-browser

A browser that Claude Code can drive: open pages, click, fill forms, log in, take screenshots and pull data from sites that need interaction. It reads pages as short accessibility snapshots, so it uses far fewer tokens than reading raw HTML.

- Project: [github.com/vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) (Apache License 2.0)
- This kit doesn't bundle its code. You install the CLI with npm.

## Install (once)

Needs Node.js 18 or newer.

```bash
npm install -g agent-browser
agent-browser install      # downloads the browser it controls
agent-browser doctor       # checks the install
```

On Linux, use `agent-browser install --with-deps`.

## Use it

Ask Claude Code in plain English, for example:

- "Use agent-browser to open acme.com/customers and list every customer logo name."
- "Use agent-browser to take a screenshot of our pricing page."

The `agent-browser` skill in `.claude/skills/` loads the CLI's own up-to-date instructions (`agent-browser skills get core`) before it runs anything.

## When to use what

| Tool | Best for |
|---|---|
| agent-browser | Pages you have to click, scroll, log into or fill in |
| crawl4ai | Reading pages and whole sites into Markdown |

Only automate sites and accounts you're allowed to. Many sites, LinkedIn included, ban automated access in their terms.
