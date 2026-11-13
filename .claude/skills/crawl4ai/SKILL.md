---
name: crawl4ai
description: Crawl web pages or whole websites into clean Markdown or JSON with crawl4ai, free and local. Use when asked to scrape or crawl a site, pull a company's website into research, save pages as Markdown, or extract structured data from many pages.
allowed-tools: Bash(tools/crawl4ai/.venv/bin/*)
---

# crawl4ai

Local, free web crawler. Output goes into the Context OS, usually `context/docs/research/`.

## Before the first run

Check it's installed: `tools/crawl4ai/.venv/bin/crwl --help`. If that fails, follow the install steps in `tools/crawl4ai/README.md` (create the venv, `pip install -U crawl4ai`, `crawl4ai-setup`). Ask before installing.

## Commands

```bash
C=tools/crawl4ai/.venv/bin/crwl
$C crawl <url> -o markdown                                   # one page to stdout
$C crawl <url> -o markdown -O context/docs/research/<name>.md   # save to a file
$C crawl <url> --deep-crawl bfs --max-pages 20 -o markdown -O <file>   # follow links
$C crawl <url> -o markdown-fit                                # main content only, less boilerplate
$C crawl --help                                               # every option
```

## Rules

1. **Save raw pages to `context/docs/research/`**, one file per page or topic, named clearly (`<company>-pricing.md`).
2. **Record the source.** Add the URL and today's date at the top of every saved file, so every fact can be traced.
3. **Raw first, conclusions later.** Don't summarise or interpret while crawling. Synthesis is a separate step.
4. **Start small.** One page first, check the output, then deep crawl with a page limit. Never crawl without `--max-pages`.
5. **Empty or blocked page?** Try `-o markdown` without `-fit`, then try the page through `agent-browser`, which drives a real browser.
6. **Be polite.** Respect robots.txt and the site's terms. No logins, no paywalls, no personal data.
7. **Never commit** `tools/crawl4ai/.venv` or large raw dumps you don't need.
