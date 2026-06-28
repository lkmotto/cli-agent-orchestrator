"""Simple Perplexity REPL wrapper for CAO custom_cli provider."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def _query_perplexity(prompt: str) -> tuple[str, list[str]]:
    api_key = os.environ.get("PERPLEXITY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PERPLEXITY_API_KEY is not set")

    base_url = os.environ.get("PERPLEXITY_API_BASE", "https://api.perplexity.ai").rstrip("/")
    payload = {
        "model": os.environ.get("CAO_PERPLEXITY_MODEL", "sonar-pro"),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1200,
        "search_mode": "web",
        "reasoning_effort": "medium",
        "return_related_questions": False,
    }
    req = urllib.request.Request(
        f"{base_url}/v1/sonar",
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Perplexity API error {err.code}: {detail[:300]}") from err

    content = ""
    choices = data.get("choices") or []
    if choices:
        content = ((choices[0] or {}).get("message") or {}).get("content", "").strip()
    citations = data.get("citations") or []
    return content, citations


def main() -> int:
    print("Perplexity REPL bridge ready. Type /help or /exit.")
    while True:
        try:
            user_input = input("perplexity> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            return 0

        if not user_input:
            continue
        lowered = user_input.lower()
        if lowered in {"/exit", "exit", "quit"}:
            return 0
        if lowered in {"/help", "help"}:
            print("Assistant: Ask any research question, I will answer with citations.")
            continue

        try:
            answer, citations = _query_perplexity(user_input)
        except Exception as e:
            print(f"Error: {e}")
            continue

        print("Assistant:")
        print(answer or "(no content)")
        if citations:
            print("Sources:")
            for c in citations[:8]:
                print(f"- {c}")


if __name__ == "__main__":
    raise SystemExit(main())
