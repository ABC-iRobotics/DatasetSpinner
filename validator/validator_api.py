# validator_api.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Sequence, Tuple, Union

from validator.syntax_validator import SyntaxValidator
from validator.logic_validator import LogicValidator


@dataclass
class ValidationResult:
    payload: Dict[str, Any]                 # the single JSON that was validated
    is_valid: bool
    errors: List[Tuple[str, str]]           # [("<schema>", "..."), ("<logic>", "..."), ...]


class ValidatorAPI:
    """
    Public API wrapper.

    Accepts:
      - a single payload dict ({"instruction":[...]})
      - OR a list of payload dicts
      - OR a dataset-style dict/list that contains entries like {"json": {...}} (optional convenience)

    Returns:
      - a single ValidationResult OR a list[ValidationResult], matching input shape.
    """

    def __init__(self, sv: SyntaxValidator | None = None, lv: LogicValidator | None = None) -> None:
        self.sv = sv or SyntaxValidator()
        self.lv = lv or LogicValidator()

    def validate(
        self,
        data: Union[Dict[str, Any], List[Any]],
    ) -> Union[ValidationResult, List[ValidationResult]]:
        items, single = self._normalize_input(data)
        results: List[ValidationResult] = [self._validate_one(p) for p in items]
        return results[0] if single else results

    def _validate_one(self, payload: Dict[str, Any]) -> ValidationResult:
        _, schema_msgs = self.sv.validate(payload)
        _, logic_msgs = self.lv.validate(payload)

        errors: List[Tuple[str, str]] = [("<schema>", m) for m in schema_msgs] + [("<logic>", m) for m in logic_msgs]
        return ValidationResult(payload=payload, is_valid=(len(errors) == 0), errors=errors)

    @staticmethod
    def _normalize_input(data: Union[Dict[str, Any], List[Any]]) -> Tuple[List[Dict[str, Any]], bool]:
        # Case 1: list input
        if isinstance(data, list):
            payloads: List[Dict[str, Any]] = []
            for x in data:
                if isinstance(x, dict) and "json" in x and isinstance(x["json"], dict):
                    payloads.append(x["json"])
                elif isinstance(x, dict) and "instruction" in x:
                    payloads.append(x)
                else:
                    raise TypeError(f"List item must be a payload dict or a dataset entry with 'json'. Got: {type(x)}")
            return payloads, False

        # Case 2: dict input
        if isinstance(data, dict):
            # dataset-style: {"data":[{"json": {...}}, ...]}  (optional convenience)
            if "data" in data and isinstance(data["data"], list):
                payloads: List[Dict[str, Any]] = []
                for x in data["data"]:
                    if isinstance(x, dict) and "json" in x and isinstance(x["json"], dict):
                        payloads.append(x["json"])
                    elif isinstance(x, dict) and "instruction" in x:
                        payloads.append(x)
                    else:
                        raise TypeError(f"data[] item must be a payload dict or dataset entry with 'json'. Got: {type(x)}")
                return payloads, False

            # dataset entry dict: {"json": {...}}
            if "json" in data and isinstance(data["json"], dict) and "instruction" in data["json"]:
                return [data["json"]], True

            # direct payload dict
            if "instruction" in data:
                return [data], True

        raise TypeError("Input must be a payload dict, a list of payloads, a dataset entry with 'json', or {'data':[...]}.")


# --- convenience function (optional) ---
def validate(data: Union[Dict[str, Any], List[Any]]) -> Union[ValidationResult, List[ValidationResult]]:
    return ValidatorAPI().validate(data)
