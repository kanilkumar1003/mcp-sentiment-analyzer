"""
Agentic loop for the Autonomous Market Sentiment & Competitor Intel Agent.

Supports TWO modes selectable at startup:
  1. ONLINE  — Gemini API  (requires GEMINI_API_KEY in .env)
  2. OFFLINE — Ollama local model (requires `ollama serve` running)

Run:
  python run_intel_agent.py               # interactive mode selector
  python run_intel_agent.py --online      # force Gemini
  python run_intel_agent.py --offline     # force Ollama

Env (via .env):
  GEMINI_API_KEY=...
  OLLAMA_HOST=http://localhost:11434      (optional, defaults shown)
  OLLAMA_MODEL=gemma4:e4b                 (optional)
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import sys
from concurrent.futures import TimeoutError
from datetime import datetime

import requests as http_requests
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

# ───────────────────────────────────────────────────────────────────────────
# Configuration
# ───────────────────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")

MAX_ITERATIONS = 10
LLM_TIMEOUT = 240       # generous for both APIs
RETRY_ATTEMPTS = 2       # retry on transient 503 / timeout errors

# ───────────────────────────────────────────────────────────────────────────
# Pretty terminal helpers (ANSI colours — works on macOS/Linux natively)
# ───────────────────────────────────────────────────────────────────────────
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
MAGENTA = "\033[95m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"


def banner(mode: str) -> None:
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════╗
║  🚀  Autonomous Market Sentiment & Competitor Intel Agent   ║
║                                                              ║
║  Mode : {mode.upper():7s}                                            ║
║  Tools: intel_mcp_server.py                                  ║
╚══════════════════════════════════════════════════════════════╝{RESET}
""")


def log_iter(n: int) -> None:
    print(f"\n{BOLD}{MAGENTA}━━━ Iteration {n} ━━━{RESET}")


def log_llm(text: str) -> None:
    print(f"{YELLOW}🤖 LLM:{RESET} {text}")


def log_call(name: str, args_preview: str) -> None:
    print(f"{CYAN}  → {name}{RESET}({DIM}{args_preview}{RESET})")


def log_result(payload: str, max_len: int = 300) -> None:
    short = payload[:max_len] + ("…" if len(payload) > max_len else "")
    print(f"{GREEN}  ← {short}{RESET}")


def log_error(msg: str) -> None:
    print(f"{RED}  ✗ {msg}{RESET}")


def log_done(text: str) -> None:
    print(f"\n{GREEN}{BOLD}══════════════════════════════════════")
    print(f"  ✅  Agent finished")
    print(f"══════════════════════════════════════{RESET}")
    print(f"{DIM}{text}{RESET}\n")


# ───────────────────────────────────────────────────────────────────────────
# LLM Backends
# ───────────────────────────────────────────────────────────────────────────

# --- Gemini ----------------------------------------------------------------
_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _gemini_client


def _call_gemini(prompt: str) -> str:
    from google import genai  # noqa: F811
    client = _get_gemini_client()
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text or ""


# --- Ollama ----------------------------------------------------------------
def _call_ollama(prompt: str) -> str:
    try:
        r = http_requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=LLM_TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("response", "")
    except http_requests.ConnectionError:
        raise RuntimeError(
            f"Cannot reach Ollama at {OLLAMA_HOST}. Is it running? Try: ollama serve"
        )
    except http_requests.HTTPError as e:
        raise RuntimeError(
            f"Ollama API error: {e}. Did you pull the model? Try: ollama pull {OLLAMA_MODEL}"
        )


# --- Unified async wrapper -------------------------------------------------
async def generate(prompt: str, mode: str) -> str:
    """Run the blocking LLM call in a thread with a timeout + retry."""
    loop = asyncio.get_event_loop()
    backend = _call_gemini if mode == "online" else _call_ollama

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            raw = await asyncio.wait_for(
                loop.run_in_executor(None, backend, prompt),
                timeout=LLM_TIMEOUT,
            )
            return raw
        except (TimeoutError, asyncio.TimeoutError):
            if attempt < RETRY_ATTEMPTS:
                log_error(f"Timeout (attempt {attempt}/{RETRY_ATTEMPTS}) — retrying in 5s…")
                await asyncio.sleep(5)
            else:
                raise
        except Exception as e:
            err_str = str(e)
            if ("503" in err_str or "UNAVAILABLE" in err_str) and attempt < RETRY_ATTEMPTS:
                log_error(f"Transient error (attempt {attempt}/{RETRY_ATTEMPTS}) — retrying in 8s…")
                await asyncio.sleep(8)
            else:
                raise


# ───────────────────────────────────────────────────────────────────────────
# Tool helpers
# ───────────────────────────────────────────────────────────────────────────

def describe_tools(tools) -> str:
    lines = []
    for i, t in enumerate(tools, 1):
        props = (t.inputSchema or {}).get("properties", {})
        params = ", ".join(f"{n}: {p.get('type', '?')}" for n, p in props.items()) or "no params"
        lines.append(f"{i}. {t.name}({params}) — {t.description or ''}")
    return "\n".join(lines)


def coerce(value: str, schema_type: str):
    if schema_type == "integer":
        return int(value)
    if schema_type == "number":
        return float(value)
    if schema_type == "array":
        return eval(value)  # teaching code; fine inside the sandbox
    if schema_type == "boolean":
        return value.lower() in ("true", "1", "yes")
    return value


def first_directive(text: str) -> str:
    """Find the FUNCTION_CALL or FINAL_ANSWER directive.
    If it spans multiple lines (like a JSON payload), capture the whole block.
    """
    lines = (text or "").splitlines()
    for i, line in enumerate(lines):
        s = line.strip().lstrip("`").lstrip()
        if s.startswith("FUNCTION_CALL:"):
            payload = "\n".join(lines[i:])
            if payload.startswith("FUNCTION_CALL: ```json"):
                payload = payload.replace("FUNCTION_CALL: ```json", "FUNCTION_CALL:", 1)
            elif payload.startswith("FUNCTION_CALL: ```"):
                payload = payload.replace("FUNCTION_CALL: ```", "FUNCTION_CALL:", 1)
            if payload.endswith("```"):
                payload = payload[:-3].strip()
            return payload.strip()
        if s.startswith("FINAL_ANSWER:"):
            return s
    return (text or "").strip()


# ───────────────────────────────────────────────────────────────────────────
# Mode selector
# ───────────────────────────────────────────────────────────────────────────

def select_mode() -> str:
    # Check CLI flags first
    if "--online" in sys.argv:
        return "online"
    if "--offline" in sys.argv:
        return "offline"

    # Interactive prompt
    print(f"{BOLD}Select LLM mode:{RESET}")
    print(f"  {CYAN}1{RESET} — Online  (Gemini API — needs GEMINI_API_KEY)")
    print(f"  {CYAN}2{RESET} — Offline (Ollama local — needs ollama serve)")
    while True:
        choice = input(f"\n{BOLD}Enter 1 or 2: {RESET}").strip()
        if choice in ("1", "online"):
            return "online"
        if choice in ("2", "offline"):
            return "offline"
        print(f"{RED}Invalid choice.{RESET} Please enter 1 or 2.")


# ───────────────────────────────────────────────────────────────────────────
# Main agentic loop
# ───────────────────────────────────────────────────────────────────────────

async def main():
    mode = select_mode()
    banner(mode)

    model_label = GEMINI_MODEL if mode == "online" else f"Ollama/{OLLAMA_MODEL}"
    sleep_seconds = 5 if mode == "online" else 0
    print(f"{DIM}Model: {model_label} | MaxIter: {MAX_ITERATIONS} | Timeout: {LLM_TIMEOUT}s{RESET}\n")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["intel_mcp_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f"{GREEN}✓ Connected to intel_mcp_server{RESET}")

            tools = (await session.list_tools()).tools
            tools_desc = describe_tools(tools)
            print(f"{GREEN}✓ Loaded {len(tools)} tools{RESET}\n")

            # ── System prompt ─────────────────────────────────────────
            system_prompt = f"""You are an Autonomous Market Sentiment & Competitor Intel Agent working with an MCP server.
You solve tasks by calling tools ONE AT A TIME and observing their results.

Available tools:
{tools_desc}

Respond with exactly one of these two directives:
  FUNCTION_CALL: tool_name|arg1|arg2|...
  FINAL_ANSWER: <short natural-language summary of what you did>

Rules:
- Output only the directive. No prose, no markdown before it.
- Provide args in the exact order of the tool's parameters.
- Do not invent tools that are not listed above.
- After each FUNCTION_CALL you'll receive the result; use it to decide the next step.
- When the task is complete, emit FINAL_ANSWER.
- When generating the UI spec for generate_ui, you MUST pass a valid JSON string as the argument. You MAY format the JSON across multiple lines for readability. Do NOT wrap the JSON inside quotes or escape it as a string literal.
- For tools with no params (e.g. read_sentiment_log, compare_topics, list_sandbox_files), call them as: FUNCTION_CALL: tool_name
"""

            # ── Task ──────────────────────────────────────────────────
            topics = ["DeepSeek", "Tesla Robotaxi", "OpenAI GPT-5", "Apple Intelligence", "Claude 3.5 Sonnet", "Meta Llama 4", "Nvidia Blackwell"]
            chosen_topic = random.choice(topics)

            task = (
                "You are an autonomous research agent. Perform the following steps:\n"
                f"1. Fetch data from Hacker News about the following trending tech topic: '{chosen_topic}'.\n"
                f"2. Also fetch data from Reddit about the SAME topic ('{chosen_topic}') for broader coverage.\n"
                "3. Analyze the combined findings: decide the overall sentiment (positive/neutral/negative) and save it using save_sentiment. "
                "Pass the combined raw_data from both sources, and an overall sentiment_score string like 'positive' or 'mixed'.\n"
                "4. Generate a professional Markdown report summarizing your findings using generate_report. "
                "The summary should be 3-5 sentences covering: key themes, community reactions, notable controversies, and an overall conclusion.\n"
                "5. Finally, generate a beautiful Prefab UI dashboard using generate_ui.\n"
                "\n"
                "CRITICAL UI GUIDELINES — the dashboard must be rich and informative:\n"
                "The JSON structure: {\"params\": {\"title\": \"<topic> — Market Sentiment & Intel Dashboard\", \"tabs\": [...]}}\n"
                "\n"
                "Tab 1 — 'Sentiment Overview' (4 widgets):\n"
                "  a) 'stat' widget: label='Overall Market Sentiment', value=the sentiment word (e.g. 'Positive'), sub='Based on N articles from 2 sources'\n"
                "  b) 'pie' widget: title='Sentiment Distribution', data array with Positive/Neutral/Negative percentages based on your analysis of the articles\n"
                "  c) 'badges' widget: title='Data Sources Analyzed', items=['Hacker News (Top 10)', 'Reddit (Top 8)']\n"
                "  d) 'text' widget: heading='Key Takeaways', body=a 2-3 sentence paragraph summarizing the most important finding\n"
                "\n"
                "Tab 2 — 'Top Articles & Analysis' (3 widgets):\n"
                "  a) 'table' widget: title='Highest-Engagement Articles', columns=['#','Source','Title','Engagement']. "
                "Include 5-6 rows with the TOP articles from BOTH sources. Use full article titles (not shortened). "
                "For Score column show '2091 pts' for HN or '3046 upvotes' for Reddit.\n"
                "  b) 'text' widget: heading='Detailed Analysis', body=a detailed 3-4 sentence analysis covering: "
                "what themes dominate the conversation, what concerns exist, how the community feels, and what this means for the market.\n"
                "  c) 'progress_list' widget: title='Community Engagement Metrics', items with label and value(0-100) for: "
                "'Developer Enthusiasm', 'Media Coverage', 'Controversy Level', 'Market Impact' — estimate percentages from the data.\n"
                "\n"
                "6. When done, emit FINAL_ANSWER."
            )

            history: list[str] = []
            for iteration in range(1, MAX_ITERATIONS + 1):
                log_iter(iteration)

                context = "\n".join(history) if history else "(no prior steps)"
                prompt = (
                    f"{system_prompt}\n"
                    f"Task: {task}\n\n"
                    f"Previous steps:\n{context}\n\n"
                    f"What is your next single action? Output ONLY the FUNCTION_CALL line or FINAL_ANSWER line."
                )

                print(f"{'='*50} \n {prompt} \n {'='*50} ")

                if sleep_seconds > 0:
                    print(f"{DIM}  Waiting {sleep_seconds}s before LLM call…{RESET}")
                    await asyncio.sleep(sleep_seconds)

                try:
                    raw = await generate(prompt, mode)
                except (TimeoutError, asyncio.TimeoutError):
                    log_error("LLM timed out after retries — stopping.")
                    break
                except Exception as e:
                    log_error(f"LLM error: {e}")
                    break

                text = first_directive(raw)
                log_llm(text)

                if text.startswith("FINAL_ANSWER:"):
                    log_done(text)
                    break

                if not text.startswith("FUNCTION_CALL:"):
                    log_error("Unexpected response format — stopping.")
                    print(f"{DIM}Raw: {raw[:500]}{RESET}")
                    break

                _, call = text.split(":", 1)
                parts = [p.strip() for p in call.split("|")]
                func_name = parts[0]

                tool = next((t for t in tools if t.name == func_name), None)
                if tool is None:
                    msg = f"Unknown tool {func_name!r}"
                    log_error(msg)
                    history.append(f"Iteration {iteration}: {msg}")
                    continue

                props = (tool.inputSchema or {}).get("properties", {})
                raw_args = parts[1:]

                # If the tool has 1 parameter, all remaining parts belong to it
                # (handles JSON strings that contain '|' characters)
                if len(props) == 1 and len(raw_args) > 1:
                    raw_args = ["|".join(raw_args)]
                # If tool has more params than parts, pad with empty strings
                while len(raw_args) < len(props):
                    raw_args.append("")

                arguments = {}
                for (name, info), val in zip(props.items(), raw_args):
                    arguments[name] = coerce(val, info.get("type", "string"))

                args_preview = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
                log_call(func_name, args_preview[:120])

                try:
                    result = await session.call_tool(func_name, arguments=arguments)
                    payload = (
                        result.content[0].text
                        if result.content and hasattr(result.content[0], "text")
                        else str(result)
                    )
                except Exception as e:
                    payload = f"ERROR: {e}"

                log_result(payload)
                history.append(
                    f"Iteration {iteration}: called {func_name} → {payload}"
                )
            else:
                print(f"\n{YELLOW}Reached MAX_ITERATIONS ({MAX_ITERATIONS}) without FINAL_ANSWER.{RESET}")

            # ── Summary ───────────────────────────────────────────────
            print(f"\n{BOLD}📁 Sandbox contents:{RESET}")
            sandbox = os.path.join(os.path.dirname(__file__), "sandbox")
            if os.path.isdir(sandbox):
                for f in sorted(os.listdir(sandbox)):
                    fp = os.path.join(sandbox, f)
                    sz = os.path.getsize(fp) if os.path.isfile(fp) else 0
                    print(f"   {f}  ({sz:,} bytes)")
            print()


if __name__ == "__main__":
    asyncio.run(main())
