"""LLM provider abstraction.

Supports OpenAI, Anthropic, and ChatGPT OAuth (the Codex backend that accepts
ChatGPT Plus session JWTs instead of platform API keys). All three expose
`chat(...)` for free-form conversation and `structured(...)` for JSON-shaped
outputs. The OAuth provider additionally exposes `respond(...)` — a single
turn of the Responses API that returns the raw output items so the agent
loop in `services/agent.py` can drive multi-step tool use.
"""
from __future__ import annotations

import base64
import json
import pathlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Protocol
from uuid import uuid4

import httpx
from anthropic import Anthropic
from openai import OpenAI

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int


class LLMProvider(Protocol):
    def chat(self, messages: list[dict[str, str]], **kw: Any) -> LLMResponse: ...

    def structured(
        self, messages: list[dict[str, str]], schema: dict, **kw: Any
    ) -> dict: ...


# ----- OpenAI -----------------------------------------------------------------


class OpenAIProvider:
    def __init__(self) -> None:
        self._client = OpenAI(api_key=settings.llm_api_key)
        self._model = settings.llm_model

    def chat(self, messages: list[dict[str, str]], **kw: Any) -> LLMResponse:
        resp = self._client.chat.completions.create(
            model=kw.get("model", self._model),
            messages=messages,  # type: ignore[arg-type]
            temperature=kw.get("temperature", settings.llm_temperature),
            max_tokens=kw.get("max_tokens", settings.llm_max_tokens),
        )
        choice = resp.choices[0]
        usage = resp.usage
        return LLMResponse(
            content=choice.message.content or "",
            model=resp.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    def structured(
        self, messages: list[dict[str, str]], schema: dict, **kw: Any
    ) -> dict:
        resp = self._client.chat.completions.create(
            model=kw.get("model", self._model),
            messages=messages,  # type: ignore[arg-type]
            temperature=kw.get("temperature", 0.0),
            max_tokens=kw.get("max_tokens", settings.llm_max_tokens),
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        return json.loads(raw)


# ----- Anthropic --------------------------------------------------------------


class AnthropicProvider:
    def __init__(self) -> None:
        self._client = Anthropic(api_key=settings.llm_api_key)
        self._model = settings.llm_model

    def _split_system(self, messages: list[dict[str, str]]) -> tuple[str, list[dict]]:
        system = ""
        rest: list[dict] = []
        for m in messages:
            if m["role"] == "system":
                system += m["content"] + "\n"
            else:
                rest.append({"role": m["role"], "content": m["content"]})
        return system.strip(), rest

    def chat(self, messages: list[dict[str, str]], **kw: Any) -> LLMResponse:
        system, rest = self._split_system(messages)
        resp = self._client.messages.create(
            model=kw.get("model", self._model),
            system=system or "You are a helpful assistant.",
            messages=rest,  # type: ignore[arg-type]
            temperature=kw.get("temperature", settings.llm_temperature),
            max_tokens=kw.get("max_tokens", settings.llm_max_tokens),
        )
        text = "".join(getattr(b, "text", "") for b in resp.content)
        return LLMResponse(
            content=text,
            model=resp.model,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        )

    def structured(
        self, messages: list[dict[str, str]], schema: dict, **kw: Any
    ) -> dict:
        guarded = list(messages) + [
            {
                "role": "user",
                "content": (
                    "Respond ONLY with a single JSON object that conforms to this schema. "
                    "No prose, no markdown:\n" + json.dumps(schema)
                ),
            }
        ]
        resp = self.chat(guarded, **kw)
        return json.loads(resp.content)


# ----- ChatGPT OAuth (Codex backend) -----------------------------------------
#
# ChatGPT Plus sessions can mint JWTs whose audience is `api.openai.com/v1`.
# The Codex backend at `chatgpt.com/backend-api/codex/responses` accepts
# those tokens against the Responses API shape, so calls go against the
# user's ChatGPT subscription instead of a paid platform key.
#
# Caveats:
#   - Token expires roughly every 7 days. When it does, requests start
#     returning 401 — refresh by grabbing a new bearer from the ChatGPT
#     web app DevTools and updating OPENAI_CHATGPT_TOKEN.
#   - This pattern is undocumented. If OpenAI revokes it, swap the env var
#     for a paid platform key and the rest of the code still works.

CODEX_URL = "https://chatgpt.com/backend-api/codex/responses"


class AgentLLMError(Exception):
    """Base for all agent-loop LLM provider errors (OAuth / Gemini / etc.)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ChatGPTOAuthError(AgentLLMError):
    """Raised on Codex backend errors. Includes status + body for debugging."""


class GeminiError(AgentLLMError):
    """Raised on Code Assist / Gemini API errors. Includes status for debugging."""


def _account_id_from_token(token: str) -> str:
    try:
        payload = token.split(".")[1]
        # JWT base64url has no padding; pad before decoding.
        payload += "=" * (-len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
        account_id = decoded.get("https://api.openai.com/auth", {}).get(
            "chatgpt_account_id"
        )
    except Exception as exc:  # noqa: BLE001
        raise ChatGPTOAuthError(
            "Could not parse ChatGPT OAuth token (malformed JWT)."
        ) from exc
    if not account_id:
        raise ChatGPTOAuthError(
            "ChatGPT OAuth token missing chatgpt_account_id claim."
        )
    return account_id


class ChatGPTOAuthProvider:
    """LLM provider that authenticates with a ChatGPT Plus session JWT.

    Uses the Responses API shape via the Codex backend. Supports tool-use
    loops through `respond()`, which returns the parsed output items.
    """

    def __init__(self, token: str | None = None, model: str | None = None) -> None:
        # Prefer the Codex OAuth creds file (access_token + refresh_token +
        # account_id) when configured — it's the only token shape Codex
        # accepts and it can be auto-refreshed. Fall back to the static
        # OPENAI_CHATGPT_TOKEN env var otherwise.
        self._creds_path = self._resolve_creds_path()
        self._refresh_token: str | None = None
        if token:
            self._token = token
            self._account_id = _account_id_from_token(self._token)
        elif self._creds_path and self._creds_path.exists():
            self._load_creds()
        elif settings.openai_chatgpt_token:
            self._token = settings.openai_chatgpt_token
            self._account_id = _account_id_from_token(self._token)
        else:
            raise ChatGPTOAuthError(
                "No Codex credentials. Run scripts/chatgpt_codex_oauth.py to "
                "mint a token, or set OPENAI_CHATGPT_TOKEN / switch LLM_PROVIDER."
            )
        self._model = model or settings.openai_chatgpt_model
        self._effort = settings.openai_chatgpt_effort
        self._timeout = settings.openai_chatgpt_timeout_s

    @staticmethod
    def _resolve_creds_path() -> pathlib.Path | None:
        raw = settings.openai_codex_creds_path
        if not raw:
            return None
        p = pathlib.Path(raw)
        if not p.is_absolute():
            # Relative paths resolve against apps/api (two parents up from here).
            p = pathlib.Path(__file__).resolve().parents[2] / raw
        return p

    def _load_creds(self) -> None:
        data = json.loads(self._creds_path.read_text(encoding="utf-8"))
        self._token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        self._account_id = data.get("account_id") or _account_id_from_token(self._token)

    def _refresh_access_token(self) -> bool:
        """Renew the access token from the refresh_token. Returns True on success.

        Codex tokens come from auth.openai.com; the refresh grant returns a
        fresh access_token (and sometimes a rotated refresh_token). We persist
        the result back to the creds file so the next process start is fresh.
        """
        if not self._refresh_token:
            return False
        body = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": "app_EMoamEEZ73f0CkXaXp7hrann",  # Codex CLI client
            "scope": "openid profile email offline_access",
        }
        try:
            with httpx.Client(timeout=30) as cx:
                r = cx.post("https://auth.openai.com/oauth/token", data=body)
        except httpx.HTTPError as exc:
            log.warning("codex_refresh_network_error", error=str(exc))
            return False
        if r.status_code >= 400:
            log.warning("codex_refresh_failed", status=r.status_code, body=r.text[:200])
            return False
        tok = r.json()
        self._token = tok["access_token"]
        if tok.get("refresh_token"):
            self._refresh_token = tok["refresh_token"]
        # Persist back to the creds file.
        if self._creds_path and self._creds_path.exists():
            try:
                data = json.loads(self._creds_path.read_text(encoding="utf-8"))
                data["access_token"] = self._token
                if tok.get("refresh_token"):
                    data["refresh_token"] = self._refresh_token
                if tok.get("id_token"):
                    data["id_token"] = tok["id_token"]
                self._creds_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                log.warning("codex_refresh_persist_failed", error=str(exc))
        log.info("codex_token_refreshed")
        return True

    # -- Public ---------------------------------------------------------------

    def chat(self, messages: list[dict[str, str]], **kw: Any) -> LLMResponse:
        """Single-turn convenience: collapse to a Responses API call and
        return the assistant text. No tools."""
        instructions, input_items = self._messages_to_input(messages)
        items = self.respond(
            input_items=input_items,
            instructions=instructions,
            tools=None,
            model=kw.get("model"),
        )
        text = self._extract_assistant_text(items)
        return LLMResponse(
            content=text,
            model=kw.get("model", self._model),
            input_tokens=0,
            output_tokens=0,
        )

    def structured(
        self, messages: list[dict[str, str]], schema: dict, **kw: Any
    ) -> dict:
        guarded = list(messages) + [
            {
                "role": "user",
                "content": (
                    "Respond ONLY with a single JSON object that conforms to this schema. "
                    "No prose, no markdown:\n" + json.dumps(schema)
                ),
            }
        ]
        resp = self.chat(guarded, **kw)
        return json.loads(resp.content)

    def respond(
        self,
        *,
        input_items: list[dict],
        instructions: str,
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> list[dict]:
        """Hit the Codex backend once. Returns parsed output items.

        `input_items` is the Responses API input array (messages,
        function_call_output entries, etc.). The agent loop in
        `services/agent.py` builds and grows it across steps.
        """
        body: dict[str, Any] = {
            "model": model or self._model,
            "input": input_items,
            "store": False,
            "stream": True,
            "instructions": instructions,
            "reasoning": {"effort": self._effort},
            "parallel_tool_calls": True,
        }
        if tools:
            body["tools"] = tools

        # One transparent retry: if Codex 401s (token expired), refresh the
        # access token from the refresh_token and replay the request once.
        for attempt in (1, 2):
            headers = {
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "chatgpt-account-id": self._account_id,
                "originator": "codex_cli_rs",
                "User-Agent": "codex_cli_rs/0.40.0",
                "Accept": "text/event-stream",
            }
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    with client.stream(
                        "POST", CODEX_URL, headers=headers, json=body
                    ) as resp:
                        if resp.status_code == 401 and attempt == 1 and self._refresh_token:
                            resp.read()  # drain
                            if self._refresh_access_token():
                                continue  # replay with the fresh token
                        if resp.status_code >= 400:
                            text = resp.read().decode("utf-8", errors="replace")
                            raise ChatGPTOAuthError(
                                f"Codex API {resp.status_code}: {text[:400]}",
                                status_code=resp.status_code,
                            )
                        return list(_parse_codex_stream(resp.iter_lines()))
            except httpx.HTTPError as exc:
                raise ChatGPTOAuthError(f"Codex network error: {exc}") from exc
        # Exhausted retries (only reached if refresh succeeded but 2nd call
        # also 401'd — treat as auth failure).
        raise ChatGPTOAuthError("Codex API 401 after token refresh.", status_code=401)

    # -- Helpers --------------------------------------------------------------

    @staticmethod
    def _messages_to_input(
        messages: list[dict[str, str]],
    ) -> tuple[str, list[dict]]:
        """Split chat-completions-style messages into (instructions, input_items).

        System prompts collapse into the `instructions` field; user/assistant
        messages map to Responses API `message` items.
        """
        instructions_parts: list[str] = []
        items: list[dict] = []
        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if role == "system":
                if isinstance(content, str):
                    instructions_parts.append(content)
                continue
            if role not in ("user", "assistant"):
                continue
            if isinstance(content, str):
                part_type = "input_text" if role == "user" else "output_text"
                items.append(
                    {
                        "type": "message",
                        "role": role,
                        "content": [{"type": part_type, "text": content}],
                    }
                )
            elif isinstance(content, list):
                items.append({"type": "message", "role": role, "content": content})
        return "\n".join(p.strip() for p in instructions_parts if p), items

    @staticmethod
    def _extract_assistant_text(items: list[dict]) -> str:
        for item in items:
            if item.get("type") == "message" and item.get("role") == "assistant":
                content = item.get("content") or []
                texts = [
                    c.get("text", "")
                    for c in content
                    if c.get("type") in ("output_text", "text")
                ]
                joined = "\n".join(t for t in texts if t).strip()
                if joined:
                    return joined
        return ""


def _parse_codex_stream(lines: Iterable[str]) -> Iterable[dict]:
    """Iterate SSE event blocks and yield each `response.output_item.done` item.

    The Codex backend speaks the Responses API SSE shape: events are separated
    by blank lines, each event has at least one `data: <json>` line. We emit
    completed items only — partial deltas are dropped because the agent loop
    operates turn-by-turn, not token-by-token.
    """
    buf = ""
    final_error: str | None = None
    for raw_line in lines:
        if raw_line is None:
            continue
        # httpx iter_lines splits on \r\n; keep accumulating until we hit a
        # blank line which terminates one SSE event.
        if raw_line == "":
            event = buf
            buf = ""
            data_line = next(
                (ln for ln in event.split("\n") if ln.startswith("data: ")),
                None,
            )
            if data_line is None:
                continue
            payload = data_line[6:].strip()
            if payload == "[DONE]":
                continue
            try:
                ev = json.loads(payload)
            except json.JSONDecodeError:
                continue
            ev_type = ev.get("type")
            if ev_type == "response.output_item.done":
                item = ev.get("item")
                if item is not None:
                    yield item
            elif ev_type in ("response.failed", "error"):
                final_error = (
                    ev.get("response", {}).get("error", {}).get("message")
                    or ev.get("error", {}).get("message")
                    or "unknown codex error"
                )
        else:
            buf += raw_line + "\n"
    if final_error:
        raise ChatGPTOAuthError(final_error)


# ----- Gemini (Code Assist API via OAuth bearer) -----------------------------


CODE_ASSIST_URL = "https://cloudcode-pa.googleapis.com"
CODE_ASSIST_API_VERSION = "v1internal"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GeminiProvider:
    """Provider for Google Gemini via the Code Assist API + an OAuth bearer.

    The OAuth credentials are produced by ``scripts/gemini_oauth_login.py``
    and land in ``apps/api/.gemini_oauth.json`` (refresh_token + access_token
    + expiry). This class reads that file, auto-refreshes the access token
    when expired, and translates the Responses-API shape used by
    ``services/agent.py`` into Gemini's ``generateContent`` shape.

    Code Assist is the same backend Gemini CLI uses, which means the
    user's free Gemini quota (tied to their personal Google account)
    is consumed — no GCP billing needed.
    """

    def __init__(self, creds_path: pathlib.Path | str | None = None, model: str | None = None) -> None:
        from app.core.config import settings as _s  # local to avoid cycle

        default = pathlib.Path(__file__).resolve().parents[2] / ".gemini_oauth.json"
        path = creds_path or _s.gemini_creds_path or default
        self._creds_path = pathlib.Path(path)
        if not self._creds_path.exists():
            raise GeminiError(
                f"Gemini credentials not found at {self._creds_path}. "
                "Run `python scripts/gemini_oauth_login.py` once to sign in.",
                status_code=401,
            )
        self._creds = json.loads(self._creds_path.read_text(encoding="utf-8"))
        self._model = model or settings.gemini_model
        self._timeout = settings.gemini_timeout_s

    # ── Token lifecycle ────────────────────────────────────────────────

    def _expired(self) -> bool:
        try:
            expiry = datetime.fromisoformat(self._creds["expiry"])
        except (KeyError, ValueError):
            return True
        return datetime.now(timezone.utc) >= expiry - timedelta(seconds=60)

    def _refresh_access_token(self) -> None:
        rt = self._creds.get("refresh_token")
        if not rt:
            raise GeminiError(
                "Gemini refresh_token missing — re-run scripts/gemini_oauth_login.py.",
                status_code=401,
            )
        body = {
            "grant_type": "refresh_token",
            "refresh_token": rt,
            "client_id": self._creds.get("client_id"),
            "client_secret": self._creds.get("client_secret", ""),
        }
        try:
            with httpx.Client(timeout=30) as cx:
                r = cx.post(GOOGLE_TOKEN_URL, data=body)
        except httpx.HTTPError as exc:
            raise GeminiError(f"Gemini refresh network error: {exc}") from exc
        if r.status_code >= 400:
            raise GeminiError(
                f"Gemini refresh failed ({r.status_code}): {r.text[:300]}",
                status_code=r.status_code,
            )
        tok = r.json()
        self._creds["access_token"] = tok["access_token"]
        expires_in = int(tok.get("expires_in", 3600))
        self._creds["expiry"] = (
            datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        ).isoformat()
        if tok.get("refresh_token"):
            self._creds["refresh_token"] = tok["refresh_token"]
        self._creds_path.write_text(json.dumps(self._creds, indent=2), encoding="utf-8")

    def _headers(self) -> dict[str, str]:
        if self._expired():
            self._refresh_access_token()
        return {
            "Authorization": f"Bearer {self._creds['access_token']}",
            "Content-Type": "application/json",
        }

    # ── Project discovery (free-tier onboarding) ───────────────────────

    def _project_id(self) -> str | None:
        return self._creds.get("project_id")

    def _persist_project_id(self, pid: str) -> None:
        self._creds["project_id"] = pid
        self._creds_path.write_text(json.dumps(self._creds, indent=2), encoding="utf-8")

    def _load_code_assist(self) -> str | None:
        """One-time discovery of the user's free-tier project id."""
        url = f"{CODE_ASSIST_URL}/{CODE_ASSIST_API_VERSION}:loadCodeAssist"
        body = {
            "metadata": {
                "ideType": "IDE_UNSPECIFIED",
                "platform": "PLATFORM_UNSPECIFIED",
                "pluginType": "GEMINI",
            },
        }
        try:
            with httpx.Client(timeout=30) as cx:
                r = cx.post(url, json=body, headers=self._headers())
        except httpx.HTTPError:
            return None
        if r.status_code >= 400:
            return None
        data = r.json()
        return (
            data.get("cloudaicompanionProject")
            or data.get("currentTier", {}).get("cloudaicompanionProject")
        )

    # ── Generate ───────────────────────────────────────────────────────

    def _generate(self, request: dict, model: str | None = None) -> dict:
        import re
        import time

        url = f"{CODE_ASSIST_URL}/{CODE_ASSIST_API_VERSION}:generateContent"
        # Eagerly discover the project_id on first use — Code Assist returns
        # 500 INTERNAL (not a clean 400) when the project field is missing
        # for accounts that require one, so we can't safely rely on retry.
        pid = self._project_id()
        if not pid:
            pid = self._load_code_assist()
            if pid:
                self._persist_project_id(pid)

        wrapped: dict[str, Any] = {
            "model": model or self._model,
            "request": request,
        }
        if pid:
            wrapped["project"] = pid

        def _do_post() -> httpx.Response:
            with httpx.Client(timeout=self._timeout) as cx:
                return cx.post(url, json=wrapped, headers=self._headers())

        try:
            r = _do_post()
        except httpx.HTTPError as exc:
            raise GeminiError(f"Gemini network error: {exc}") from exc

        if r.status_code == 401:
            self._refresh_access_token()
            r = _do_post()

        # Code Assist's free tier rate-limits hard on Pro (~few requests/min)
        # and emits "Your quota will reset after Ns" in the body. Parse it and
        # retry once — better than crashing on a transient throttle.
        if r.status_code == 429:
            m = re.search(r"reset after (\d+)\s*s", r.text)
            wait = min(int(m.group(1)) + 2, 90) if m else 60
            log.warning(
                "gemini_rate_limited",
                wait_s=wait,
                model=wrapped["model"],
            )
            time.sleep(wait)
            r = _do_post()

        if r.status_code >= 400:
            raise GeminiError(
                f"Gemini {r.status_code}: {r.text[:600]}",
                status_code=r.status_code,
            )
        return r.json()

    # ── Public API (matches LLMProvider) ───────────────────────────────

    def chat(self, messages: list[dict[str, Any]], **kw: Any) -> LLMResponse:
        contents, sys_inst = _messages_to_gemini(messages)
        request: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": kw.get("temperature", settings.llm_temperature),
                "maxOutputTokens": kw.get("max_tokens", settings.llm_max_tokens),
            },
        }
        if sys_inst:
            request["systemInstruction"] = {"parts": [{"text": sys_inst}]}
        result = self._generate(request, model=kw.get("model"))
        text = _gemini_extract_text(result)
        usage = _gemini_usage(result)
        return LLMResponse(
            content=text,
            model=kw.get("model", self._model),
            input_tokens=usage[0],
            output_tokens=usage[1],
        )

    def structured(
        self, messages: list[dict[str, Any]], schema: dict, **kw: Any
    ) -> dict:
        contents, sys_inst = _messages_to_gemini(messages)
        request: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": kw.get("temperature", 0.0),
                "maxOutputTokens": kw.get("max_tokens", settings.llm_max_tokens),
                "responseMimeType": "application/json",
                "responseSchema": _clean_schema_for_gemini(schema),
            },
        }
        if sys_inst:
            request["systemInstruction"] = {"parts": [{"text": sys_inst}]}
        result = self._generate(request, model=kw.get("model"))
        raw = _gemini_extract_text(result) or "{}"
        return json.loads(raw)

    def respond(
        self,
        *,
        input_items: list[dict],
        instructions: str,
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> list[dict]:
        """Mirror ChatGPTOAuthProvider.respond — Responses-API shape in & out.

        Internally translates to/from Gemini's `contents` / `functionCall`
        format so the agent loop in services/agent.py doesn't need to know
        which provider is wired in.
        """
        contents = _input_items_to_gemini(input_items)
        request: dict[str, Any] = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": instructions}]},
            "generationConfig": {
                "temperature": settings.llm_temperature,
                "maxOutputTokens": settings.llm_max_tokens,
            },
        }
        if settings.gemini_thinking_budget >= 0:
            request["generationConfig"]["thinkingConfig"] = {
                "thinkingBudget": settings.gemini_thinking_budget,
            }
        if tools:
            request["tools"] = [{"functionDeclarations": _tools_to_gemini(tools)}]
        result = self._generate(request, model=model)
        return _gemini_to_response_items(result)


# ── Gemini ↔ Responses-API translation helpers ──────────────────────────


def _messages_to_gemini(
    messages: list[dict[str, Any]],
) -> tuple[list[dict], str | None]:
    """Convert chat-completions-style messages to Gemini contents + system."""
    sys_parts: list[str] = []
    contents: list[dict] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            if isinstance(content, str):
                sys_parts.append(content)
            continue
        if role not in ("user", "assistant"):
            continue
        gemini_role = "user" if role == "user" else "model"
        parts: list[dict] = []
        if isinstance(content, str):
            parts.append({"text": content})
        elif isinstance(content, list):
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") in ("text", "input_text", "output_text"):
                    parts.append({"text": c.get("text", "")})
        if parts:
            contents.append({"role": gemini_role, "parts": parts})
    return contents, "\n\n".join(sys_parts) if sys_parts else None


def _gemini_extract_text(result: dict) -> str:
    """Pull assistant text from a Code Assist `generateContent` result."""
    cands = (
        result.get("response", {}).get("candidates")
        or result.get("candidates")
        or []
    )
    for c in cands:
        content = c.get("content", {}) or {}
        parts = content.get("parts") or []
        texts = [p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p]
        joined = "\n".join(t for t in texts if t).strip()
        if joined:
            return joined
    return ""


def _gemini_usage(result: dict) -> tuple[int, int]:
    meta = result.get("response", {}).get("usageMetadata") or result.get("usageMetadata") or {}
    return int(meta.get("promptTokenCount", 0)), int(meta.get("candidatesTokenCount", 0))


def _clean_schema_for_gemini(schema: Any) -> Any:
    """Strip JSON-Schema keywords Gemini's responseSchema rejects."""
    if not isinstance(schema, dict):
        return schema
    drop = {"$schema", "$id", "$ref", "$defs", "definitions", "additionalProperties"}
    out: dict[str, Any] = {}
    for k, v in schema.items():
        if k in drop:
            continue
        if isinstance(v, dict):
            out[k] = _clean_schema_for_gemini(v)
        elif isinstance(v, list):
            out[k] = [_clean_schema_for_gemini(i) if isinstance(i, (dict, list)) else i for i in v]
        else:
            out[k] = v
    return out


def _input_items_to_gemini(items: list[dict]) -> list[dict]:
    """Convert Responses-API input items to Gemini Content[].

    Tracks call_id→name so `function_call_output` items can be tagged with
    the right tool name (Gemini's functionResponse requires it).
    """
    # First pass: build call_id → name map.
    call_to_name: dict[str, str] = {}
    for it in items:
        if it.get("type") == "function_call":
            cid = it.get("call_id")
            if cid:
                call_to_name[cid] = it.get("name", "")

    contents: list[dict] = []
    for it in items:
        t = it.get("type")
        if t == "message":
            role = it.get("role", "user")
            gemini_role = "user" if role == "user" else "model"
            parts: list[dict] = []
            for c in (it.get("content") or []):
                if not isinstance(c, dict):
                    continue
                ctype = c.get("type")
                if ctype in ("input_text", "output_text", "text"):
                    parts.append({"text": c.get("text", "")})
                elif ctype == "input_image":
                    url = c.get("image_url")
                    if not url:
                        continue
                    try:
                        with httpx.Client(timeout=15) as cx:
                            r = cx.get(url)
                        if r.status_code >= 400:
                            continue
                        mime = (r.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
                        b64 = base64.b64encode(r.content).decode("ascii")
                        parts.append({"inlineData": {"mimeType": mime, "data": b64}})
                    except Exception:  # noqa: BLE001
                        pass
            if parts:
                contents.append({"role": gemini_role, "parts": parts})
        elif t == "function_call":
            args_raw = it.get("arguments") or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except Exception:  # noqa: BLE001
                args = {}
            contents.append(
                {
                    "role": "model",
                    "parts": [{"functionCall": {"name": it.get("name", ""), "args": args}}],
                }
            )
        elif t == "function_call_output":
            cid = it.get("call_id")
            name = call_to_name.get(cid, "")
            output = it.get("output", "")
            try:
                payload = json.loads(output) if isinstance(output, str) else output
            except Exception:  # noqa: BLE001
                payload = {"output": str(output)}
            # Gemini's functionResponse wants a dict in `response`. Wrap if needed.
            if not isinstance(payload, dict):
                payload = {"result": payload}
            contents.append(
                {
                    "role": "user",
                    "parts": [{"functionResponse": {"name": name, "response": payload}}],
                }
            )
        # reasoning / other types are dropped.
    return contents


def _tools_to_gemini(tools: list[dict]) -> list[dict]:
    """Convert Responses-API tool defs to Gemini FunctionDeclaration[]."""
    out: list[dict] = []
    for t in tools or []:
        if t.get("type") == "function":
            out.append(
                {
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "parameters": _clean_schema_for_gemini(t.get("parameters") or {}),
                }
            )
        elif "name" in t and "parameters" in t:
            out.append(
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": _clean_schema_for_gemini(t["parameters"]),
                }
            )
    return out


def _gemini_to_response_items(result: dict) -> list[dict]:
    """Convert a Gemini generateContent result to Responses-API output items."""
    cands = (
        result.get("response", {}).get("candidates")
        or result.get("candidates")
        or []
    )
    items: list[dict] = []
    for c in cands:
        content = c.get("content", {}) or {}
        parts = content.get("parts") or []
        text_chunks: list[str] = []
        for p in parts:
            if not isinstance(p, dict):
                continue
            if "functionCall" in p:
                fc = p["functionCall"] or {}
                args = fc.get("args") or {}
                if not isinstance(args, str):
                    try:
                        args_str = json.dumps(args, ensure_ascii=False)
                    except Exception:  # noqa: BLE001
                        args_str = "{}"
                else:
                    args_str = args
                items.append(
                    {
                        "type": "function_call",
                        "name": fc.get("name", ""),
                        "call_id": f"call_{uuid4().hex[:16]}",
                        "arguments": args_str,
                    }
                )
            elif "text" in p:
                text_chunks.append(p.get("text", "") or "")
        if text_chunks:
            joined = "\n".join(t for t in text_chunks if t).strip()
            if joined:
                items.append(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": joined}],
                    }
                )
    return items


# ----- Factory ---------------------------------------------------------------


def get_llm_provider() -> LLMProvider:
    p = settings.llm_provider
    if p == "openai" or p == "azure-openai":
        return OpenAIProvider()
    if p == "anthropic":
        return AnthropicProvider()
    if p == "chatgpt-oauth":
        return ChatGPTOAuthProvider()
    if p == "gemini":
        return GeminiProvider()
    raise ValueError(f"Unknown LLM provider: {p}")


def get_oauth_provider() -> ChatGPTOAuthProvider:
    """DEPRECATED — use ``get_agent_provider()`` so the choice is config-driven.

    Retained for callers that explicitly want the OAuth (Codex) provider.
    """
    return ChatGPTOAuthProvider()


def get_agent_provider() -> "ChatGPTOAuthProvider | GeminiProvider":
    """Return whichever provider drives the agent loop, per AGENT_PROVIDER.

    Both providers implement the same ``respond(input_items, instructions, tools)``
    signature and raise ``AgentLLMError`` on failure, so the agent loop is
    provider-agnostic.
    """
    p = settings.agent_provider
    if p == "gemini":
        return GeminiProvider()
    return ChatGPTOAuthProvider()
