# syntax_validator.py
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator


NL2ROBOT_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://example.com/nl2robot-instruction.schema.json",
    "title": "NL2Robot Instruction",
    "type": "object",
    "additionalProperties": False,
    "required": ["instruction"],
    "properties": {
        "instruction": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["action", "location", "object", "duration"],
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "go_to",
                            "wait_for_payload_ready",
                            "wait_for_payload_removal",
                            "wait_for_seconds",
                        ],
                    },
                    "location": {"type": ["string", "null"]},
                    "object": {
                        "type": ["null", "array"],
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["description", "num"],
                            "properties": {
                                "description": {"type": "string", "minLength": 1},
                                # num: allowed {-1} or any integer >= 1; disallow 0 and < -1
                                "num": {
                                    "type": "integer",
                                    "anyOf": [
                                        {"const": -1},
                                        {"minimum": 1},
                                    ],
                                },
                            },
                        },
                    },
                    "duration": {"type": ["integer", "null"]},
                },
                "allOf": [
                    # go_to: location must be a string (not null); object/duration must be null
                    {
                        "if": {
                            "properties": {"action": {"const": "go_to"}},
                            "required": ["action"],
                        },
                        "then": {
                            "properties": {
                                "location": {"type": "string", "minLength": 1},
                                "object": {"type": "null"},
                                "duration": {"type": "null"},
                            }
                        },
                    },
                    # pickup: location must be a string (not null); object must be array; duration null
                    {
                        "if": {
                            "properties": {"action": {"const": "wait_for_payload_ready"}},
                            "required": ["action"],
                        },
                        "then": {
                            "properties": {
                                "location": {"type": "string", "minLength": 1},
                                "object": {"type": "array", "minItems": 1},
                                "duration": {"type": "null"},
                            }
                        },
                    },
                    # wait_for_seconds: object null, duration integer and required
                    {
                        "if": {
                            "properties": {"action": {"const": "wait_for_seconds"}},
                            "required": ["action"],
                        },
                        "then": {
                            "properties": {
                                "object": {"type": "null"},
                                "duration": {"type": "integer"},
                            },
                            "required": ["duration"],
                        },
                    },
                ],
            },
        }
    },
}


@dataclass
class SyntaxValidatorConfig:
    # Placeholder for future switches (e.g., verbosity)
    pass


class SyntaxValidator:
    """
    JSON Schema validator with human-friendly, "logic-like" error summaries.

    Usage:
        sv = SyntaxValidator()
        ok, problems = sv.validate(payload)
    """

    def __init__(self, schema: Optional[Dict[str, Any]] = None, config: Optional[SyntaxValidatorConfig] = None) -> None:
        self.schema = schema or NL2ROBOT_SCHEMA
        self.config = config or SyntaxValidatorConfig()
        self.validator = Draft202012Validator(self.schema)

    def validate(self, payload: Dict[str, Any]) -> tuple[bool, List[str]]:
        problems = self._summarize_schema_errors(payload)
        return (len(problems) == 0), problems

    # -------------------------
    # Internals (summarization)
    # -------------------------
    @staticmethod
    def _path_str(path_iter) -> str:
        p = list(path_iter)
        return "/".join(map(str, p)) if p else "<root>"

    @staticmethod
    def _step_context(payload: Dict[str, Any], abs_path: List[Any]) -> str:
        if len(abs_path) >= 2 and abs_path[0] == "instruction" and isinstance(abs_path[1], int):
            i = abs_path[1]
            try:
                action = payload["instruction"][i].get("action")
            except Exception:
                action = None
            return f"step {i} ({action})" if isinstance(action, str) else f"step {i}"
        return ""

    @staticmethod
    def _summarize_anyof_num(err) -> Optional[str]:
        abs_path = list(getattr(err, "absolute_path", []))
        if len(abs_path) >= 1 and abs_path[-1] == "num":
            if getattr(err, "validator", None) in ("anyOf", "oneOf"):
                return "num must be -1 or an integer >= 1"
        return None

    @staticmethod
    def _merge_type_messages(errs_at_path: List[Any]) -> Optional[str]:
        # Prefer "must be null" if schema requires null at this path (common for go_to duration/object).
        want_null_only = any(getattr(e, "validator", None) == "type" and getattr(e, "schema", None) == "null" for e in errs_at_path)
        if want_null_only:
            return "must be null"

        type_errs = [e for e in errs_at_path if getattr(e, "validator", None) == "type"]
        if not type_errs:
            return None

        allowed = set()
        for e in type_errs:
            sch = getattr(e, "schema", None)
            if isinstance(sch, list):
                allowed.update(str(t) for t in sch)
            elif isinstance(sch, str):
                allowed.add(sch)

        if allowed:
            allowed_str = ", ".join(sorted(allowed))
            return f"must be of type: {allowed_str}"
        return type_errs[0].message

    def _summarize_schema_errors(self, payload: Dict[str, Any]) -> List[str]:
        raw = sorted(self.validator.iter_errors(payload), key=lambda e: list(e.path))
        by_path: Dict[tuple, List[Any]] = defaultdict(list)
        for e in raw:
            by_path[tuple(getattr(e, "absolute_path", []))].append(e)

        out: List[str] = []

        for abs_path_t, errs in sorted(by_path.items(), key=lambda kv: list(kv[0])):
            abs_path = list(abs_path_t)
            path = self._path_str(abs_path)

            ctx = self._step_context(payload, abs_path)
            ctx_prefix = f"{ctx}: " if ctx else ""

            # 1) Special-case: anyOf/oneOf for num
            anyof_wrap = next((e for e in errs if getattr(e, "validator", None) in ("anyOf", "oneOf")), None)
            if anyof_wrap:
                rule = self._summarize_anyof_num(anyof_wrap)
                if rule:
                    bad_val = anyof_wrap.instance if hasattr(anyof_wrap, "instance") else None
                    out.append(f"{ctx_prefix}{path}: {rule} (got {bad_val!r})")
                    continue

            # 2) Merge redundant type errors at same path
            merged_type = self._merge_type_messages(errs)
            if merged_type:
                bad_val = errs[0].instance if hasattr(errs[0], "instance") else None
                out.append(f"{ctx_prefix}{path}: {merged_type} (got {bad_val!r})")
                continue

            # 3) Otherwise pick the most “specific” single message
            priority = {
                "additionalProperties": 0,
                "required": 1,
                "enum": 2,
                "const": 3,
                "minimum": 4,
                "maximum": 4,
                "minLength": 5,
                "maxLength": 5,
                "pattern": 6,
                "anyOf": 7,
                "oneOf": 7,
                "allOf": 8,
                "type": 9,
            }
            best = min(errs, key=lambda e: priority.get(getattr(e, "validator", ""), 50))
            bad_val = best.instance if hasattr(best, "instance") else None
            out.append(f"{ctx_prefix}{path}: {best.message} (got {bad_val!r})")

        return out
