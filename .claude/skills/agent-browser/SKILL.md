---
name: agent-browser
description: Browser automation for AI agents. Use when asked to interact with a website, fill a form, click elements, extract data from a page that needs interaction, take screenshots, log into a site, or automate any browser task.
allowed-tools: Bash(agent-browser:*)
---

# agent-browser

1. Check the CLI is installed: `agent-browser --version`. If it isn't, follow `tools/agent-browser/README.md` (ask before installing).
2. Run `agent-browser skills get core` and follow those instructions exactly. They ship with the CLI, so they always match the installed version.
3. Save anything you extract for research into `context/docs/research/`, with the source URL and today's date at the top.
4. Only automate sites and accounts the user is allowed to. Stop and ask before logging in, submitting a form, or sending anything.
