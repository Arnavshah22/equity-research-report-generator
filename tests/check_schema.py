"""
Guard the LLM contract: the report schema must survive each provider's
structured-output transform.

Every vendor accepts a slightly different subset of JSON Schema, and the
failure mode is a 400 at request time -- i.e. only visible with an API key and
only after you have already paid for the document tokens. Running the same
transforms the SDKs apply catches a bad schema change locally, for free.

    python -m tests.check_schema
"""

from __future__ import annotations

import json

from pydantic import TypeAdapter

from app.schema import ReportModel


def check_anthropic() -> None:
    from anthropic.lib._parse._transform import transform_schema

    schema = TypeAdapter(ReportModel).json_schema()
    transformed = transform_schema(schema)
    blob = json.dumps(transformed)

    print("  transform_schema         : OK")
    print(f"  schema size              : {len(blob):,} bytes")
    print(f"  $defs                    : {len(transformed.get('$defs', {}))}")
    print(f"  top-level properties     : {len(transformed.get('properties', {}))}")


def check_gemini() -> None:
    # Gemini gets the schema in the prompt rather than as `response_schema`:
    # its constrained decoder rejects a schema this large outright ("too many
    # states for serving"). See the note in app/providers.py::_call_gemini.
    #
    # So the thing to guard here is prompt cost, not decoder compatibility --
    # the schema is resent with every request and is billed every time.
    from app.providers import _schema_text

    blob = _schema_text()
    budget = 16_000
    assert len(blob) < budget, (
        f"schema is {len(blob):,} chars, over the {budget:,} prompt budget -- "
        "it ships in full on every Gemini request"
    )

    print("  prompt-embedded schema   : OK")
    print(f"  schema size              : {len(blob):,} bytes (~{len(blob) // 4:,} tokens)")


def check_openai() -> None:
    from openai.lib._pydantic import to_strict_json_schema

    # Used for OpenAI, Groq, OpenRouter and Ollama alike -- they share the
    # response_format={"type": "json_schema", "strict": true} contract.
    strict = to_strict_json_schema(ReportModel)
    blob = json.dumps(strict)

    assert '"additionalProperties": false' in blob, "strict mode requires closed objects"

    print("  to_strict_json_schema    : OK")
    print(f"  schema size              : {len(blob):,} bytes")
    print(f"  top-level properties     : {len(strict.get('properties', {}))}")


def check_model_invariants() -> None:
    # Every field is optional, so an empty payload must still be a valid report.
    # This is what makes "the document didn't mention it" renderable.
    empty = ReportModel.model_validate({})
    assert empty.header.company_name is None
    assert empty.charts == []
    print("  empty payload validates  : OK")

    # A partially-filled table must not blow up on ragged rows.
    partial = ReportModel.model_validate(
        {
            "header": {"company_name": "Test Co"},
            "profit_loss": {
                "columns": ["FY24A", "FY25A", "FY26E"],
                "rows": [{"label": "Sales", "values": ["100"]}],
            },
        }
    )
    assert partial.profit_loss is not None
    assert len(partial.profit_loss.rows[0].values) == 1  # renderer pads to 3
    print("  ragged row validates     : OK")


CHECKS = [
    ("Gemini", check_gemini),
    ("Anthropic", check_anthropic),
    ("OpenAI-compatible", check_openai),
    ("Model invariants", check_model_invariants),
]


def main() -> int:
    failures = 0
    for name, fn in CHECKS:
        print(f"{name}:")
        try:
            fn()
        except ImportError as exc:
            # Only the provider you use needs to be installed.
            print(f"  skipped                  : {exc.name} not installed")
        except Exception as exc:
            failures += 1
            print(f"  FAILED                   : {type(exc).__name__}: {exc}")
        print()

    if failures:
        print(f"{failures} check(s) failed.")
        return 1

    print("Schema is compatible with structured outputs on all installed backends.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
