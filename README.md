# claude-skills

Personal Claude Code skill plugins by Sodiq Fakorede.

## Skills

| Skill | Version | Description |
|-------|---------|-------------|
| `literature:card` | 0.1.0 | Hallucination-proof paper intake, full-text retrieval, quote-locked card creation, BibTeX verification |

## Setup

Add to `~/.claude/settings.json`:

```json
"extraKnownMarketplaces": {
  "my-skills": {
    "source": {
      "source": "github",
      "repo": "BolaFlame1/claude-skills"
    }
  }
},
"enabledPlugins": {
  "literature@my-skills": true
}
```

## Usage

- `/literature:card doi:10.xxxx/xxxxx` — create or update a card for a paper
