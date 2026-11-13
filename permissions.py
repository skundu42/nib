"""Permissions: the model proposes, the user decides."""
from difflib import unified_diff

READ_ONLY = {"read_file", "grep", "glob", "load_skill", "task"}
SAFE_COMMANDS = ("ls", "pwd", "git status", "git diff", "git log")
SHELL_TRICKS = (";", "&", "|", ">", "<", "`", "$(", "\n")
always_allowed = set()  # tools the user approved for the rest of this session


def is_safe(command):
    """Auto-approve a few read-only commands, and only when nothing is chained onto them."""
    if any(trick in command for trick in SHELL_TRICKS):
        return False
    return any(command == safe or command.startswith(safe + " ") for safe in SAFE_COMMANDS)


def preview(name, args):
    if name == "edit_file":
        diff = unified_diff(args["old_string"].splitlines(), args["new_string"].splitlines(),
                            fromfile=args["path"], tofile=args["path"], lineterm="")
        return "\n".join(diff)
    if name == "write_file":
        return f"write {len(args['content'].splitlines())} lines to {args['path']}"
    return f"$ {args.get('command', '')}"


def allowed(name, args):
    if name in READ_ONLY or name in always_allowed:
        return True
    if name == "bash" and is_safe(args.get("command", "")):
        return True
    print(preview(name, args))
    answer = input("  Allow? [y]es, [n]o, [a]lways: ").strip().lower()
    if answer == "a":
        always_allowed.add(name)
    return answer in ("y", "a")
