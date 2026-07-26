"""
LLM backends.

The extraction prompt and the report schema are provider-independent, so the
only thing that varies between vendors is how you hand a Pydantic model to the
model as an output contract. Each backend here does exactly that and returns a
validated `ReportModel`.

Three shapes cover everything worth supporting:

  * gemini      -- google-genai, `response_schema=ReportModel`
  * anthropic   -- messages.parse, `output_format=ReportModel`
  * openai-compatible -- chat.completions.parse, `response_format=ReportModel`
    which also covers Groq, OpenRouter, Ollama and OpenAI itself, since they
    all speak the same wire format and differ only by base_url.

Selection is automatic: the first provider with a usable key wins, in the order
of AUTO_ORDER. `LLM_PROVIDER` forces a specific one. SDK imports are lazy so
you only need the package for the provider you actually use.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .schema import ReportModel

# Loaded here rather than only in llm.py so that importing this module alone --
# from a test, a script, or a different entry point -- still sees .env.
load_dotenv()

# Generation is slow -- a long filing plus a 20k-token structured response is
# minutes, not seconds -- and every SDK here defaults to a much shorter timeout.
TIMEOUT_SECONDS = 900.0
MAX_TOKENS = 32_000


class ExtractionError(Exception):
    pass


@dataclass(frozen=True)
class Backend:
    """A resolved provider: everything needed to make the call."""

    provider: str
    label: str
    model: str
    api_key: str | None = None
    base_url: str | None = None

    def __str__(self) -> str:
        return f"{self.label} ({self.model})"


# `keys` are the env vars that carry credentials for this provider, in
# precedence order. `model` is the default; LLM_MODEL overrides it. A provider
# with model=None has no safe default and must be told which model to use --
# guessing a model id that may not exist produces a worse error than asking.
PRESETS: dict[str, dict] = {
    "gemini": {
        "label": "Gemini",
        "keys": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "model": "gemini-2.5-flash",
        "base_url": None,
        "kind": "gemini",
    },
    "anthropic": {
        "label": "Claude",
        "keys": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
        "model": "claude-opus-5",
        "base_url": None,
        "kind": "anthropic",
    },
    "openai": {
        "label": "OpenAI",
        "keys": ("OPENAI_API_KEY",),
        "model": None,
        "base_url": None,
        "kind": "openai",
    },
    "groq": {
        "label": "Groq",
        "keys": ("GROQ_API_KEY",),
        "model": None,
        "base_url": "https://api.groq.com/openai/v1",
        "kind": "openai",
    },
    "openrouter": {
        "label": "OpenRouter",
        "keys": ("OPENROUTER_API_KEY",),
        "model": None,
        "base_url": "https://openrouter.ai/api/v1",
        "kind": "openai",
    },
    # Local, no key. Only selected when asked for explicitly, since finding the
    # port open is not evidence that a suitable model is pulled.
    "ollama": {
        "label": "Ollama (local)",
        "keys": (),
        "model": None,
        "base_url": "http://localhost:11434/v1",
        "kind": "openai",
    },
}

AUTO_ORDER = ("gemini", "anthropic", "openai", "groq", "openrouter")


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def resolve() -> Backend | None:
    """
    Pick a backend from the environment, or None if nothing is configured.

    Returning None rather than raising is deliberate: the app stays runnable
    without any credentials and falls back to the offline layout preview.
    """
    forced = (os.getenv("LLM_PROVIDER") or "").strip().lower()

    if forced:
        if forced not in PRESETS:
            raise ExtractionError(
                f"Unknown LLM_PROVIDER={forced!r}. "
                f"Choose one of: {', '.join(sorted(PRESETS))}."
            )
        candidates = (forced,)
    else:
        candidates = AUTO_ORDER

    for name in candidates:
        spec = PRESETS[name]
        api_key = _first_env(*spec["keys"]) or _first_env("LLM_API_KEY")

        if spec["keys"] and not api_key:
            if forced:
                raise ExtractionError(
                    f"LLM_PROVIDER={name} but no API key found. "
                    f"Set {spec['keys'][0]} in .env."
                )
            continue

        model = _first_env("LLM_MODEL") or spec["model"]
        if not model:
            raise ExtractionError(
                f"No default model for provider {name!r}. "
                "Set LLM_MODEL in .env to the model id you want to use."
            )

        return Backend(
            provider=name,
            label=spec["label"],
            model=model,
            api_key=api_key,
            base_url=_first_env("LLM_BASE_URL") or spec["base_url"],
        )

    return None


def complete(backend: Backend, system: str, user: str) -> ReportModel:
    """Run the extraction and return a validated report."""
    kind = PRESETS[backend.provider]["kind"]
    if kind == "gemini":
        return _call_gemini(backend, system, user)
    if kind == "anthropic":
        return _call_anthropic(backend, system, user)
    return _call_openai(backend, system, user)


def _missing(package: str, provider: str) -> ExtractionError:
    return ExtractionError(
        f"The {provider} backend needs the {package!r} package: "
        f"pip install {package}"
    )


# --------------------------------------------------------------------------
# gemini
# --------------------------------------------------------------------------


def _schema_text() -> str:
    from pydantic import TypeAdapter

    return json.dumps(TypeAdapter(ReportModel).json_schema())


def _call_gemini(backend: Backend, system: str, user: str) -> ReportModel:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - depends on install
        raise _missing("google-genai", "Gemini") from exc

    client = genai.Client(api_key=backend.api_key)

    # NOTE: deliberately not using `response_schema=ReportModel`.
    #
    # Gemini enforces a response schema with constrained decoding, and this
    # schema is too big for it -- the API rejects it outright with "the
    # specified schema produces a constraint that has too many states for
    # serving". Twenty-odd nested models with unbounded string arrays is past
    # what the decoder's state machine will accept, and trimming the report
    # down to fit would mean letting the vendor dictate the template.
    #
    # Plain JSON mode with the schema in the prompt has no such limit, and the
    # response is validated against the real model on the way out, so a
    # malformed reply still fails loudly rather than silently.
    system = (
        f"{system}\n\n"
        "Return ONLY a JSON object conforming to this JSON Schema. Omit fields "
        "you have no data for rather than emitting null-filled objects.\n\n"
        f"<schema>\n{_schema_text()}\n</schema>"
    )

    # Thinking tokens are drawn from the same budget as the response, so cap
    # them -- left uncapped the model can think past the limit and return an
    # empty candidate with nothing to parse.
    budget = int(os.getenv("GEMINI_THINKING_BUDGET", "4096"))

    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        max_output_tokens=int(os.getenv("LLM_MAX_TOKENS", str(MAX_TOKENS))),
        # Extraction, not prose: the same document should give the same report.
        temperature=0.0,
        thinking_config=types.ThinkingConfig(thinking_budget=budget),
        http_options=types.HttpOptions(timeout=int(TIMEOUT_SECONDS * 1000)),
    )

    try:
        response = client.models.generate_content(
            model=backend.model, contents=user, config=config
        )
    except Exception as exc:  # SDK raises several unrelated error types
        raise ExtractionError(f"Gemini API error: {exc}") from exc

    text = (getattr(response, "text", None) or "").strip()
    if text:
        try:
            return ReportModel.model_validate(json.loads(text))
        except Exception as exc:
            raise ExtractionError(
                f"Gemini returned JSON that did not match the report schema: {exc}"
            ) from exc

    raise ExtractionError(
        "Gemini returned no content. This usually means the token budget was "
        "exhausted -- try a smaller GEMINI_THINKING_BUDGET or a larger "
        f"LLM_MAX_TOKENS. Details: {getattr(response, 'candidates', None)}"
    )


# --------------------------------------------------------------------------
# anthropic
# --------------------------------------------------------------------------


def _call_anthropic(backend: Backend, system: str, user: str) -> ReportModel:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - depends on install
        raise _missing("anthropic", "Claude") from exc

    client = anthropic.Anthropic(api_key=backend.api_key).with_options(
        timeout=TIMEOUT_SECONDS
    )

    try:
        response = client.messages.parse(
            model=backend.model,
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", str(MAX_TOKENS))),
            output_config={"effort": os.getenv("ANTHROPIC_EFFORT", "medium")},
            system=[
                {
                    "type": "text",
                    "text": system,
                    # Byte-stable across every request, so it caches cleanly.
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user}],
            output_format=ReportModel,
        )
    except anthropic.APIError as exc:
        raise ExtractionError(f"Claude API error: {exc}") from exc

    if response.stop_reason == "refusal":
        raise ExtractionError("The model declined to process this document.")

    report = response.parsed_output
    if report is None:
        raise ExtractionError(
            "The model's response did not match the report schema. "
            f"stop_reason={response.stop_reason}"
        )
    return report


# --------------------------------------------------------------------------
# openai-compatible: OpenAI, Groq, OpenRouter, Ollama
# --------------------------------------------------------------------------


def _call_openai(backend: Backend, system: str, user: str) -> ReportModel:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - depends on install
        raise _missing("openai", backend.label) from exc

    client = OpenAI(
        # Ollama needs no credentials but the SDK insists on a non-empty key.
        api_key=backend.api_key or "not-needed",
        base_url=backend.base_url,
        timeout=TIMEOUT_SECONDS,
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    # `parse` graduated out of `beta` mid-2025; support both so the pinned
    # version in requirements.txt isn't the only one that works.
    parse = getattr(client.chat.completions, "parse", None)
    if parse is None:  # pragma: no cover - older SDKs
        parse = client.beta.chat.completions.parse

    try:
        completion = parse(
            model=backend.model,
            messages=messages,
            response_format=ReportModel,
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", str(MAX_TOKENS))),
        )
    except Exception as exc:
        raise ExtractionError(f"{backend.label} API error: {exc}") from exc

    if not completion.choices:
        raise ExtractionError(f"{backend.label} returned no choices.")

    message = completion.choices[0].message
    if getattr(message, "refusal", None):
        raise ExtractionError(f"The model declined to process this document: {message.refusal}")

    report = getattr(message, "parsed", None)
    if isinstance(report, ReportModel):
        return report

    content = (message.content or "").strip()
    if content:
        try:
            return ReportModel.model_validate(json.loads(content))
        except Exception as exc:
            raise ExtractionError(
                f"{backend.label} returned JSON that did not match the report "
                f"schema: {exc}"
            ) from exc

    raise ExtractionError(
        f"{backend.label} returned an empty response "
        f"(finish_reason={completion.choices[0].finish_reason})."
    )
