"""Nib's tools: what the model can do, and the code that does it."""
import re
import subprocess
from pathlib import Path

from skills import load_skill

ROOT = Path.cwd().resolve()  # the project Nib works in
MAX_OUTPUT = 30_000          # characters a single tool result may return
SKIP = {".git", "node_modules", "__pycache__", ".venv"}
read_times = {}              # file -> modification time when the model last read it


class ToolError(Exception):
    """A mistake the model can fix. It goes back as a tool result, not a crash."""


# ---------- the schemas the model sees ----------

TOOLS = [
    {
        "name": "read_file",
        "description": "Read a text file. Each line comes back prefixed with its line number. "
                       "For large files, use offset and limit. Always read a file before editing it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to the project root"},
                "offset": {"type": "integer", "description": "First line to read (1-based)"},
                "limit": {"type": "integer", "description": "How many lines to read"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create a new file, or overwrite a file you have already read.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace an exact piece of text in a file. old_string must match the file exactly, "
                       "indentation included, and must appear only once unless replace_all is true. "
                       "Never include the line-number prefix from read_file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
                "replace_all": {"type": "boolean"},
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
    {
        "name": "bash",
        "description": "Run a shell command in the project directory and return its output and exit code. "
                       "Use it for tests, git and build tools. Every call starts a fresh shell.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "description": "Seconds before the command is stopped (default 120)"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "grep",
        "description": "Search file contents with a regular expression. Returns path:line: text, at most 200 matches.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "glob": {"type": "string", "description": "Only search files matching this name pattern, e.g. *.py"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "glob",
        "description": "Find files by name pattern, such as *.py or tests/*.py. Newest first, at most 100.",
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    },
    {
        "name": "load_skill",
        "description": "Load the full instructions of a skill listed in the system prompt.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "task",
        "description": "Hand a self-contained question to a subagent. It gets a fresh context and read-only "
                       "tools, explores on its own, and returns a short report. Use it for broad searches "
                       "that would otherwise fill your context.",
        "input_schema": {
            "type": "object",
            "properties": {"prompt": {"type": "string", "description": "Everything the subagent needs to know"}},
            "required": ["prompt"],
        },
    },
]

READ_ONLY_TOOLS = [t for t in TOOLS if t["name"] in ("read_file", "grep", "glob")]


# ---------- the code that runs them ----------

def resolve(path):
    """Turn a model-supplied path into a real one, and refuse anything outside the project."""
    p = (ROOT / path).resolve()
    if p != ROOT and ROOT not in p.parents:
        raise ToolError(f"{path} is outside the project directory")
    return p


def read_file(path, offset=1, limit=2000):
    p = resolve(path)
    lines = p.read_text(errors="replace").splitlines()
    read_times[p] = p.stat().st_mtime
    start = max(offset, 1) - 1
    chunk = lines[start:start + limit]
    text = "\n".join(f"{n:6}\t{line[:2000]}" for n, line in enumerate(chunk, start + 1))
    if start + limit < len(lines):
        text += f"\n... ({len(lines)} lines in total, use offset to read more)"
    return text or "(empty file)"


def write_file(path, content):
    p = resolve(path)
    if p.exists() and p not in read_times:
        raise ToolError("This file already exists. Read it before overwriting it.")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    read_times[p] = p.stat().st_mtime
    return f"Wrote {len(content.splitlines())} lines to {path}"


def edit_file(path, old_string, new_string, replace_all=False):
    p = resolve(path)
    if read_times.get(p) != p.stat().st_mtime:
        raise ToolError("You haven't read this file, or it changed since you read it. Read it first.")
    text = p.read_text()
    count = text.count(old_string)
    if count == 0:
        raise ToolError("old_string was not found. Copy it exactly from read_file, without line numbers.")
    if count > 1 and not replace_all:
        raise ToolError(f"old_string appears {count} times. Include more surrounding lines to make it unique.")
    p.write_text(text.replace(old_string, new_string))
    read_times[p] = p.stat().st_mtime
    return f"Edited {path} ({count} replacement{'s' if count > 1 else ''})"


def bash(command, timeout=120):
    try:
        run = subprocess.run(command, shell=True, cwd=ROOT, capture_output=True,
                             text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ToolError(f"The command was stopped after {timeout} seconds")
    output = (run.stdout + run.stderr).strip()
    return f"{output}\n(exit code {run.returncode})"


def project_files(pattern="*"):
    for p in ROOT.rglob(pattern):
        if p.is_file() and not SKIP & set(p.relative_to(ROOT).parts):
            yield p


def grep(pattern, glob="*"):
    regex = re.compile(pattern)
    hits = []
    for f in project_files(glob):
        if f.stat().st_size > 1_000_000:
            continue
        for n, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
            if regex.search(line):
                hits.append(f"{f.relative_to(ROOT)}:{n}: {line.strip()[:200]}")
                if len(hits) == 200:
                    return "\n".join(hits) + "\n... (stopped at 200 matches)"
    return "\n".join(hits) or "No matches."


def glob(pattern):
    found = sorted(project_files(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return "\n".join(str(p.relative_to(ROOT)) for p in found[:100]) or "No files found."


def clip(text):
    """Long outputs keep their head and tail: errors usually live at one end."""
    if len(text) <= MAX_OUTPUT:
        return text
    half = MAX_OUTPUT // 2
    return f"{text[:half]}\n\n... [{len(text) - MAX_OUTPUT} characters cut] ...\n\n{text[-half:]}"


FUNCTIONS = {"read_file": read_file, "write_file": write_file, "edit_file": edit_file,
             "bash": bash, "grep": grep, "glob": glob, "load_skill": load_skill}


def run_tool(name, args):
    """Run one tool call. Returns (output, is_error); errors are results, not crashes."""
    try:
        return clip(str(FUNCTIONS[name](**args))), False
    except (ToolError, OSError, ValueError, TypeError, KeyError, re.error) as e:
        return f"Error: {e}", True
