# MISSING.md — the claim-check for the contextink repo

## The name, checked (2026-10-18)

Searched on GitHub (API search, repos):

- `contextink` (repos): 0 hits — coined word, unused.
- `context acquisition agent` (repos): 10 hits — all noise (chatbot, MCP, RAG tutoring).
- `minimal clarifying questions` (repos): 6 hits — all noise (credit-risk articles, a 0★ Codex skill).
- `information gain clarification` (repos): 1 hit — a 0★ academic NLP project.

The slot this repo takes — an agent that acquires context from the environment and asks
only the minimal high-information-gain questions — did not appear in those hits. The claim
stays only that the specific combination is not there.

## What this repo does NOT claim

- It does not read minds. Context comes from files, git, and manifests; nothing is
  invented.
- It does not "understand intent" in the model sense. It detects gaps by rules (missing
  target, missing success criteria, terse input, ambiguous referents) and ranks them by
  fixed information-gain weights.
- It does not replace asking the user. When acquisition fails, it asks — but only what's
  genuinely missing, at most 3 questions.

## What is genuinely absent (to build or not to build)

- The portrait: Yogi has the png; the README slot waits.
- Semantic context acquisition (using an LLM to infer intent from vague instructions) —
  not built; this repo stays deterministic and offline.
- Cross-repo context (scanning sibling repos) — not built.