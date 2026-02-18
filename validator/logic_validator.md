# Logic Validator (NL2Robot)

The logic validator module adds **logic-level validation** on top of the JSON Schema (syntax) validation for NL→JSON robot plans.

The validator simulates the plan step-by-step and checks that the sequence is **internally consistent** with:
- the robot’s **current location** (set only by `go_to`)
- the robot’s **carried inventory** (tracked by exact `description` string)

> Scope: this is **static, script-based** validation. It does not try to prove objects exist in the real world; it only verifies the plan’s internal logic.

---

## What this validator checks

### 1) Location & ordering (strict)
- The robot must do a `go_to(location)` to establish `current_location`.
- Every non-`go_to` step must have `step.location == current_location`.
- Pickup/drop without a prior `go_to` is invalid.

### 2) Optional quality rule: redundant movement
- If enabled, consecutive `go_to` to the **same** location is flagged as invalid (quality issue).

### 3) Inventory conservation
- The validator maintains an inventory map `carried[description]`.
- Dropping an item that was never picked up is invalid.
- For known numeric quantities, can’t drop more than carried.
- Inventory must never become negative.

### 4) Handling unknown quantity (`num = -1`)
- Pickup with `num = -1` means the robot picked up **some / an unknown amount**.
  - Internally this becomes **unknown** quantity for that `description`.
- Drop with `num = -1` means the robot drops **some**.
  - If the carried amount is **unknown**, repeated “drop some” is always allowed and the amount remains unknown.
  - If the carried amount is **known** (integer), dropping “some” requires at least 1 and the validator decrements by 1 (conservative “at least one was dropped” model).
- If carried is unknown and you drop a concrete number (e.g. 3), it is allowed (cannot statically prove insufficiency).

    > This infinite glitch must be addressed later on!

### 5) Object identity
- Objects are matched **only by exact `description` string equality**.
  - If the model changes wording between pickup and drop, this will be treated as a different item.

---

## API

### Module
`logic_validator.py`

### Class
`LogicValidator`

### Method
`validate(payload: dict) -> tuple[bool, list[str]]`

Returns:
- `ok`: `True` if no problems were found
- `problems`: list of **human-readable** error messages with step indices and details

---

## Usage

```python
from logic_validator import LogicValidator

lv = LogicValidator()
ok, problems = lv.validate(example["json"])  # or lv.validate(payload)

if ok:
    print("✅ Logic valid")
else:
    print("❌ Logic invalid:")
    for p in problems:
        print("  -", p)
```

---

## Configuration

```python
from logic_validator import LogicValidator, LogicValidatorConfig

cfg = LogicValidatorConfig(disallow_consecutive_same_go_to=True)
lv = LogicValidator(cfg)
```

- `disallow_consecutive_same_go_to`:
  - `True`: flags consecutive `go_to` to the same location (quality rule)
  - `False`: allows it