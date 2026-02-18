# logic_validator.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class LogicValidatorConfig:
    # Quality rule (optional)
    disallow_consecutive_same_go_to: bool = True


class LogicValidator:
    """
    Logic validator for NL2Robot JSON payloads.

    Assumes JSON Schema validation already ran, but remains defensive.
    """

    def __init__(self, config: Optional[LogicValidatorConfig] = None) -> None:
        self.config = config or LogicValidatorConfig()

    def validate(self, payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
        problems: List[str] = []

        steps = payload.get("instruction")
        if not isinstance(steps, list) or not steps:
            return False, ['Payload must contain a non-empty "instruction" list.']

        current_location: Optional[str] = None
        last_action: Optional[str] = None

        # Inventory: description -> int count, or None for "unknown (some/unspecified) amount"
        carried: Dict[str, Optional[int]] = {}

        for idx, step in enumerate(steps):
            step_label = f"step {idx}"
            if not isinstance(step, dict):
                problems.append(f"{step_label}: Step must be an object/dict.")
                continue

            action = step.get("action")
            location = step.get("location")
            obj = step.get("object")

            if not isinstance(action, str):
                problems.append(f"{step_label}: Missing/invalid 'action'.")
                continue

            # ----- C) Location coherence (strict) -----
            if action == "go_to":
                if location is None or not isinstance(location, str) or not location.strip():
                    problems.append(f"{step_label} (go_to): 'location' must be a non-empty string (got {location!r}).")
                else:
                    if (
                        self.config.disallow_consecutive_same_go_to
                        and last_action == "go_to"
                        and current_location == location
                    ):
                        problems.append(
                            f"{step_label} (go_to): Consecutive go_to to the same location {location!r} is disallowed."
                        )
                    current_location = location
            else:
                # Strict: every non-go_to step must happen at current_location
                if current_location is None:
                    problems.append(
                        f"{step_label} ({action}): No prior go_to; current_location is undefined, "
                        f"but step location is {location!r}."
                    )
                else:
                    if location != current_location:
                        problems.append(
                            f"{step_label} ({action}): Location mismatch. current_location={current_location!r}, "
                            f"step.location={location!r}."
                        )

                if location is None:
                    problems.append(f"{step_label} ({action}): 'location' must not be null under strict coherence.")

            # ----- A) Temporal/ordering consistency -----
            if action in ("wait_for_payload_ready", "wait_for_payload_removal"):
                if current_location is None:
                    problems.append(
                        f"{step_label} ({action}): Pickup/drop requires a preceding go_to; current_location is undefined."
                    )

            # ----- B) Inventory conservation -----
            if action == "wait_for_payload_ready":
                self._validate_pickup(idx, obj, carried, problems)
            elif action == "wait_for_payload_removal":
                self._validate_drop(idx, obj, carried, problems)

            last_action = action

        # Never carry negative quantities (post-check, defensive)
        for desc, qty in carried.items():
            if qty is not None and qty < 0:
                problems.append(f"inventory: Negative carried quantity for {desc!r}: {qty} (this should never happen).")

        return (len(problems) == 0), problems

    def _validate_pickup(
        self,
        idx: int,
        obj: Any,
        carried: Dict[str, Optional[int]],
        problems: List[str],
    ) -> None:
        step_label = f"step {idx} (wait_for_payload_ready)"

        if not isinstance(obj, list) or not obj:
            problems.append(f"{step_label}: 'object' must be a non-empty list for pickup.")
            return

        for j, entry in enumerate(obj):
            if not isinstance(entry, dict):
                problems.append(f"{step_label}: object[{j}] must be an object/dict.")
                continue

            desc = entry.get("description")
            num = entry.get("num")

            if not isinstance(desc, str) or not desc.strip():
                problems.append(f"{step_label}: object[{j}].description must be a non-empty string.")
                continue
            if not isinstance(num, int):
                problems.append(f"{step_label}: object[{j}].num must be an integer.")
                continue

            # num semantics: -1 means "some (unknown)"; 0 is illogical for pickup
            if num == 0:
                problems.append(f"{step_label}: object[{j}] {desc!r} has num=0 (pickup of zero is illogical).")
                continue
            if num < -1:
                problems.append(f"{step_label}: object[{j}] {desc!r} has invalid num={num} (< -1).")
                continue

            # Update carried
            if num == -1:
                carried[desc] = None  # unknown dominates
            else:
                prev = carried.get(desc)
                if prev is None:
                    carried[desc] = None  # already unknown
                else:
                    carried[desc] = (prev or 0) + num

    def _validate_drop(
        self,
        idx: int,
        obj: Any,
        carried: Dict[str, Optional[int]],
        problems: List[str],
    ) -> None:
        step_label = f"step {idx} (wait_for_payload_removal)"

        if not isinstance(obj, list) or not obj:
            problems.append(f"{step_label}: 'object' must be a non-empty list for drop.")
            return

        for j, entry in enumerate(obj):
            if not isinstance(entry, dict):
                problems.append(f"{step_label}: object[{j}] must be an object/dict.")
                continue

            desc = entry.get("description")
            num = entry.get("num")

            if not isinstance(desc, str) or not desc.strip():
                problems.append(f"{step_label}: object[{j}].description must be a non-empty string.")
                continue
            if not isinstance(num, int):
                problems.append(f"{step_label}: object[{j}].num must be an integer.")
                continue

            if num == 0:
                problems.append(f"{step_label}: object[{j}] {desc!r} has num=0 (drop of zero is illogical).")
                continue
            if num < -1:
                problems.append(f"{step_label}: object[{j}] {desc!r} has invalid num={num} (< -1).")
                continue

            if desc not in carried:
                problems.append(
                    f"{step_label}: Dropping {desc!r} (num={num}) but it was never picked up (not in inventory)."
                )
                continue

            have = carried[desc]  # int or None(unknown)

            if num == -1:
                # num=-1 means "drop some". If we ever picked up with num=-1, carried is unknown,
                # and repeated "drop some" must always be allowed (do NOT set carried to 0).
                if have is None:
                    carried[desc] = None
                else:
                    # Finite inventory case: require at least 1 and decrement by 1.
                    if have <= 0:
                        problems.append(
                            f"{step_label}: Dropping some of {desc!r} (num=-1) but carried quantity is {have}."
                        )
                    else:
                        carried[desc] = have - 1
                continue

            # num is concrete positive
            if have is None:
                # Unknown carried amount: cannot prove insufficiency -> allow, keep unknown
                carried[desc] = None
            else:
                if num > have:
                    problems.append(
                        f"{step_label}: Dropping {desc!r} (num={num}) exceeds carried amount (have={have})."
                    )
                else:
                    carried[desc] = have - num
                    if carried[desc] < 0:
                        problems.append(f"{step_label}: Inventory for {desc!r} became negative ({carried[desc]}).")
