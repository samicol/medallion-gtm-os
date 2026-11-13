# crawl4ai

Free, open-source web crawler that turns pages into clean Markdown or JSON. Use it to pull a company's website into your research folder, crawl a whole site, or extract structured data from pages, without paying per call.

- Project: [github.com/unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) (Apache License 2.0)
- This kit doesn't bundle crawl4ai's code. You install it from PyPI into a virtual environment inside this folder.

## Install (once)

Needs Python 3.10 or newer. From the repo root:

```bash
python3 -m venv tools/crawl4ai/.venv
tools/crawl4ai/.venv/bin/pip install -U crawl4ai
tools/crawl4ai/.venv/bin/crawl4ai-setup      # installs the browser it uses
tools/crawl4ai/.venv/bin/crawl4ai-doctor     # checks everything works
```

On Windows, use `tools\crawl4ai\.venv\Scripts\` instead of `tools/crawl4ai/.venv/bin/`.

The `.venv` folder is in `.gitignore`, so it never gets committed.

## Use it

Or just ask Claude Code, for example "Use crawl4ai to save acme.com's homepage and pricing page to context/docs/research/". The `crawl4ai` skill tells it how.

```bash
C=tools/crawl4ai/.venv/bin/crwl

# One page as Markdown
$C crawl https://example.com -o markdown

# Save it to your research folder
$C crawl https://example.com/pricing -o markdown -O context/docs/research/pricing-page.md

# Crawl a site, following links (up to 20 pages)
$C crawl https://example.com --deep-crawl bfs --max-pages 20 -o markdown -O context/docs/research/site.md

# Ask a question about a page (needs an LLM API key, see crwl --help)
$C crawl https://example.com -q "What do they sell, and who to?"
```

## When to use what

| Tool | Best for |
|---|---|
| crawl4ai | Reading pages and whole sites into Markdown, fast and free |
| agent-browser | Pages you have to click, log into, or fill in before you can read them |
| Claude Code's web fetch | A quick look at one page during a conversation |

Respect each site's terms of service and robots.txt, and don't crawl faster than a person could read.
