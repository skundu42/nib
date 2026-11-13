"""Nib: a small coding agent. Run it from the root of the project you want it to work on."""
from agent import close_dangling, run_agent
from prompt import build_system_prompt
from tools import TOOLS


def main():
    system = build_system_prompt()  # built once: changing it later would break the cache
    messages = []
    print("Nib is ready. Describe a task, or press Ctrl+D to quit.")
    while True:
        try:
            task = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not task:
            continue
        messages.append({"role": "user", "content": task})
        try:
            print(run_agent(messages, system, TOOLS))
        except KeyboardInterrupt:
            close_dangling(messages)
            print("\n(interrupted)")


if __name__ == "__main__":
    main()
