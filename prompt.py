"""The system prompt: who Nib is, where it is, and what this project expects."""
import platform

from skills import list_skills
from tools import ROOT

IDENTITY = """You are Nib, a coding agent that works in the user's terminal.
You complete software tasks by reading code, editing files and running commands with your tools.

How to work:
- Explore before you change anything: find and read the relevant files first.
- Make the smallest change that solves the task. Edit surgically instead of rewriting whole files.
- After a change, check it: run the tests or the code, and read the output.
- When a tool returns an error, read it and adjust. Don't repeat the same failing call.
- Use the task tool for broad searches, so your own context stays focused.
- Keep replies short: say what you changed and how you checked it."""

SUBAGENT = """You are a research subagent working for a coding agent.
Explore the codebase with your read-only tools to answer the question you are given.
Reply with a concise report: what you found, with file paths and line numbers. You cannot edit files."""


def environment():
    is_git = (ROOT / ".git").exists()
    return f"Environment:\n- Working directory: {ROOT}\n- Platform: {platform.system()}\n- Git repository: {is_git}"


def build_system_prompt(subagent=False):
    parts = [SUBAGENT if subagent else IDENTITY, environment()]
    if not subagent:
        for name in ("CLAUDE.md", "AGENTS.md"):  # project memory, loaded once per session
            memory = ROOT / name
            if memory.exists():
                parts.append(f"Project instructions from {name}:\n{memory.read_text()}")
        skills = list_skills()
        if skills:
            lines = [f"- {name}: {description}" for name, (description, _) in skills.items()]
            parts.append("Skills (call load_skill before using one):\n" + "\n".join(lines))
    # One cache breakpoint here: tools + system prompt are identical on every request.
    return [{"type": "text", "text": "\n\n".join(parts), "cache_control": {"type": "ephemeral"}}]
