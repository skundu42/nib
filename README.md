# Nib: a coding agent in 380 lines of Python

Nib is a small coding agent in the style of Claude Code, built for the Forward Pass video
"I Built My Own Claude Code From Scratch". It has the same skeleton as the real thing:
an agent loop, file and shell tools, permission prompts, a system prompt with project memory
(CLAUDE.md / AGENTS.md), prompt caching, compaction, subagents and skills.

It is a teaching project: small enough to read in one sitting, not a replacement for Claude Code.

## Files

| File | What it does |
|---|---|
| `main.py` | The terminal prompt: reads your task, runs the agent, handles Ctrl+C |
| `agent.py` | The agent loop, the model call, subagents and compaction |
| `tools.py` | Tool schemas (what the model sees) and their implementations |
| `permissions.py` | Which actions run on their own and which ask you first |
| `prompt.py` | The system prompt: identity, environment, project memory, skills list |
| `skills.py` | Finds `.claude/skills/*/SKILL.md` and loads one on demand |

## Run it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # your Claude API key
cd /path/to/your/project            # Nib works in the current directory
python /path/to/nib/main.py
```

Nib uses `claude-opus-5-5` (change `MODEL` in `agent.py`). Every API call costs money:
watch the token line it prints after each step.

`examples/` holds a sample `CLAUDE.md` and a sample skill (`.claude/skills/fix-failing-tests`).
Copy them into a project to see project memory and skills in action.

## Safety

Nib only reads and writes inside the directory you start it in, and asks before every file
change and every shell command except a few read-only ones (`ls`, `pwd`, `git status`,
`git diff`, `git log`). It has no sandbox: a command you approve runs with your user's
permissions. Read what you approve.
