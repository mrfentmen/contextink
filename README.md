# Contextink — the context agent

> **Contextink** is the agent that gets the context so you don't have to explain it. You say
> "do this" and it scans the repo, git state, recent files, and manifest to acquire what's
> missing; it only asks the minimal set of high-information-gain questions when acquisition
> fails. No invented context, no "ask everything" — only what's genuinely missing.

The word is coined: *context* + *instink* → **contextink** — the rung where the agent
stops needing to be told and starts figuring it out.

```text
        .----.
       /  _   \
       |=[_]==|
  (`.--.____.---.'\
   `-./'\\_.'
      |  /.  .||
       \:-: .'
  LGB   `-'                     (archive piece, credited, until the portrait lands)
```

## What it does

| You say | Contextink does |
|---|---|
| `do this` / `fix the login bug` | scans repo, git, recent files; acquires context; plans if enough, asks minimal questions if not |
| `status` | shows what was acquired and what gaps remain |
| `ask tides: what are the tides?` | forwards to a sibling over ACP, cited |

Rules: acquire first, ask only what's genuinely missing, ranked by information gain. At most
3 questions, never "ask everything."

## Run it

```bash
npm i -g contextink     # or: npx contextink  (packaged agent; needs python3)
contextink              # launches agents/contextink/agent.py
```

Or from source:

```bash
git clone https://github.com/mrfentmen/contextink && cd contextink
python3 agents/contextink/agent.py
```

For forwarded questions, point it at a checkout of the answerer repo:

```bash
AWESOME_SERVERS_HOME=/path/to/awesome-servers contextink
```

Run the tests (15 of them, offline, including real child-process federation):

```bash
python3 agents/contextink/tests/test_agent.py
```

## The honest parts

- Context is acquired from files and git commands, never invented. A gap is named
  explicitly rather than papered over.
- Vendored lockwork is credited line by line: `kit/` from the ACP kit; `federation.py`
  from the polymath — vendored on 2026-10-18, kept standalone on purpose.
- A missing sibling is a named row, never silence.

Built on top of: [mrfentmen/awesome-servers](https://github.com/mrfentmen/awesome-servers)
(the watcher runtime, the feeds) and
[mrfentmen/superagents](https://github.com/mrfentmen/superagents) (the polymath and the
sentry, the first two agents this one borrows transport and lockwork from) and
[mrfentmen/fedora-hat](https://github.com/mrfentmen/fedora-hat) and
[mrfentmen/instink](https://github.com/mrfentmen/instink).