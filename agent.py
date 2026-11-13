"""The agent loop: ask the model, run the tools it asks for, send back the results, repeat."""
import anthropic

from permissions import allowed
from prompt import build_system_prompt
from tools import READ_ONLY_TOOLS, run_tool

MODEL = "claude-opus-5-5"
COMPACT_AT = 150_000  # tokens of context before we summarize the conversation

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

SUMMARY_PROMPT = (
    "Summarize the transcript inside <summary></summary> tags, so this work can continue in a new "
    "context window without redoing anything. Preserve exactly: what the user asked for and every "
    "constraint they gave; which files you read and changed; what you tried, what failed and why; "
    "exactly where things stand now; and what is still left to do. Keep file paths, names, numbers "
    "and error messages exact. Do not call any tools while writing this summary; respond with text only."
)


def call_model(system, tools, messages, effort):
    return client.beta.messages.create(
        model=MODEL,
        max_tokens=16_000,
        system=system,
        tools=tools,
        messages=messages,
        output_config={"effort": effort},
        cache_control={"type": "ephemeral"},     # cache the conversation so far for the next turn
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",                     # if a safety classifier declines, retry on a fallback model
    )


def context_size(usage):
    cached = (usage.cache_read_input_tokens or 0) + (usage.cache_creation_input_tokens or 0)
    return usage.input_tokens + cached + usage.output_tokens


def show(call):
    args = call.input
    detail = args.get("path") or args.get("command") or args.get("pattern") or args.get("name") or args.get("prompt", "")
    print(f"  > {call.name}({str(detail)[:80]})")


def run_agent(messages, system, tools, effort="high", ask=True):
    """Loop until the model answers without asking for a tool. Returns its final text."""
    while True:
        response = call_model(system, tools, messages, effort)
        if response.stop_reason == "refusal":
            return "The model declined this request."
        messages.append({"role": "assistant", "content": response.content})

        calls = [block for block in response.content if block.type == "tool_use"]
        if not calls:
            return "".join(block.text for block in response.content if block.type == "text")

        results = []
        for call in calls:
            show(call)
            if response.stop_reason == "max_tokens":
                output, is_error = "Your reply was cut off by max_tokens. Try a smaller step.", True
            elif call.name == "task":
                output, is_error = run_subagent(call.input["prompt"]), False
            elif ask and not allowed(call.name, call.input):
                output, is_error = "The user denied this action.", True
            else:
                output, is_error = run_tool(call.name, call.input)
            results.append({"type": "tool_result", "tool_use_id": call.id,
                            "content": output, "is_error": is_error})
        messages.append({"role": "user", "content": results})  # all results go back in one message

        used = context_size(response.usage)
        print(f"  [{used:,} tokens in context, {response.usage.cache_read_input_tokens or 0:,} read from cache]")
        if used > COMPACT_AT:
            compact(messages, system, tools)


def run_subagent(prompt):
    """A fresh conversation with read-only tools. Only its final report comes back."""
    print("  subagent started")
    report = run_agent([{"role": "user", "content": prompt}], build_system_prompt(subagent=True),
                       READ_ONLY_TOOLS, effort="low", ask=False)
    print("  subagent finished")
    return report


def compact(messages, system, tools):
    """Replace the whole history with one summary message, then carry on."""
    print("  compacting conversation...")
    request = messages + [{"role": "user", "content": SUMMARY_PROMPT}]
    response = call_model(system, tools, request, effort="medium")
    summary = "".join(block.text for block in response.content if block.type == "text")
    messages[:] = [{"role": "user", "content":
                    "This session continues an earlier conversation that ran out of context. "
                    f"Here is a summary of it:\n\n{summary}\n\nContinue the work from where it left off."}]


def close_dangling(messages):
    """Every tool_use needs a tool_result, even when the user interrupts mid-turn."""
    last = messages[-1] if messages else None
    if last and last["role"] == "assistant":
        calls = [block for block in last["content"] if block.type == "tool_use"]
        if calls:
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": c.id, "content": "Interrupted by the user.",
                 "is_error": True} for c in calls]})
