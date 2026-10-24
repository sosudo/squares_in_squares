Claude Code 2.1.310 is installed from Anthropic's official npm distribution at
`/workspace/.tools/claude-code/node_modules/.bin/claude`. The user requested
Claude as an additional strategy collaborator and completed subscription OAuth
login on 2026-10-24. The CLI's status reports `loggedIn=true`,
`authMethod=claude.ai`, and `apiProvider=firstParty`.

Always set `CLAUDE_CONFIG_DIR=/workspace/.claude-squares`. This directory is
outside the repository and has mode 0700; its credential file has mode 0600.
Never copy it into source, checkpoints, logs or prompts. Authentication must be
checked after a restored environment; a successful login in this instance does
not guarantee restored credentials or sessions.

The tested installation is:

```sh
npm install --prefix /workspace/.tools/claude-code --cache /tmp/squares-claude-npm-cache --no-audit --no-fund @anthropic-ai/claude-code@2.1.310
CLAUDE_CONFIG_DIR=/workspace/.claude-squares /workspace/.tools/claude-code/node_modules/.bin/claude --version
```

Reusable install and startup instructions were saved in the environment draft,
preserving the existing Python/Rust/Kaggle setup. The user saved and published
the configuration. The added domains are `api.anthropic.com`, `claude.ai`,
`claude.com`, and `platform.claude.com`; existing entries and package-manager
presets were retained. Before publication the proxy refused OAuth exchange;
after publication a fresh login succeeded. No API billing credentials or paid
compute resources were created.

Begin with a bounded, tools-disabled strategy consultation using a concise
credential-free brief. Review ideas against completed finite experiments,
competition rules and current resource budgets before giving Claude a concrete
implementation task. Its proposals remain hypotheses until independently tested.
The strict submission cutoff remains below 22.24 on both required transports.
