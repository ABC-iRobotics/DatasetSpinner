# DatasetSpinner

**DatasetSpinner** is a modular, agent-based pipeline for generating synthetic training data. It produces **Instruction/JSON pairs** for instruction decomposition in **outdoor mobile robot navigation**: natural-language instructions converted into sequences of atomic robot actions.

It is the implementation behind the INES 2026 paper [*Optimizing Training Data Diversity with DataSpinner: An LLM-driven Curator-Agent Approach*](https://doi.org/10.1109/INES69513.2026.11661205) (see [Citation](#citation)).

![DatasetSpinner Diagram](img/DatasetSpinner.png)

---

## How it works

1. LLM agents generate new instructions similar to examples sampled from the **seed dataset**.
2. Each new instruction is converted into a JSON list of atomic actions.
3. The Instruction/JSON pairs are checked and corrected for logical and syntactic errors.
4. Validated pairs are added back to the seed dataset, so later generation cycles also draw on them.

The pipeline consists of two modules. Each agent can be configured independently, with its own system prompt (see [`ds_system_prompts.py`](./ds_system_prompts.py)) and its own model. The pipeline currently uses **OpenAI API models** (`gpt-4.1` for generation, `gpt-4.1-mini` for validation).

### 1. Generator Module (GM)

| Agent | File | What it does |
|---|---|---|
| Instruction generator | [`gm_instruction_generator.py`](./gm_instruction_generator.py) | Samples 3–5 seed instructions of a given complexity (*easy*, *medium*, *hard*) and generates a batch of similar new instructions |
| JSON generator | [`gm_json_generator.py`](./gm_json_generator.py) | Uses 2–3 Instruction/JSON pairs from the seed dataset as examples and converts each new instruction into atomic actions in JSON format |

Seed sampling is handled by [`gm_sample_picker.py`](./gm_sample_picker.py).

### 2. Validator Module (VM)

| Agent | File | What it does |
|---|---|---|
| Logic validator | [`vm_logic_validator.py`](./vm_logic_validator.py) | Checks that each JSON matches the logic of its instruction and attempts to fix errors |
| Syntax validator | [`vm_syntax_validator.py`](./vm_syntax_validator.py) | Takes the logically correct pairs and attempts to fix syntax errors |
| ~~Supervisor~~ (disabled) | [`vm_supervisor.py`](./vm_supervisor.py) | Final accept/reject check. Disabled because it rejected too many valid pairs (too many false negatives). Could be extended for additional checks, e.g. how the LLM interprets object quantities |

---

## Quick start

Requires Python 3.10+ and an [OpenAI API key](https://platform.openai.com/api-keys).

```bash
git clone https://github.com/danielhorti/DatasetSpinner.git
cd DatasetSpinner
pip install -r requirements.txt

export OPENAI_API_KEY="sk-..."
jupyter notebook ds_main.ipynb
```

Run the notebook cells in order:

- **Seed setup:** on the first run, the notebook copies the hand-written seed from `true_seed/` into `growing_seed/`. Generated pairs are then appended to `growing_seed/seed_<type>.json`.
- **Settings:** the iteration count per difficulty, `batch_size` and `num_examples` are set at the bottom of the main cell.
- **Logs:** progress is written to `logs/dataspinner.log`.

> **Cost:** every iteration makes several paid OpenAI API calls. The notebook defaults to one iteration per difficulty, so increase the counts gradually.

> Never commit your API key. `openai_key.txt`, `.env` and `logs/` are already listed in `.gitignore`.

---

## Rule-based validator

[`validator/`](./validator) provides a deterministic, script-based validator that doesn't call any LLM. It can be used to check generated or third-party data:

- **Schema check** ([`syntax_validator.py`](./validator/syntax_validator.py)): JSON Schema validation of each plan.
- **Logic check** ([`logic_validator.py`](./validator/logic_validator.py)): simulates the plan step by step, tracking the robot's location and inventory. The rules are described in [`logic_validator.md`](./validator/logic_validator.md).

```python
import json
from validator.validator_api import validate

data = json.load(open("eval_dataset/checked_eval_unseen_dsFormat_qty_detailed_openAI100.json"))
results = validate(data)  # also accepts a single entry or a bare {"instruction": [...]} plan

for r in results:
    if not r.is_valid:
        print(r.errors)
```

---

## Repository layout

| Path | Contents |
|---|---|
| `ds_main.ipynb` | Pipeline entry point (`DataSpinner` class and run loop) |
| `ds_system_prompts.py` | System prompts for every agent |
| `gm_*.py`, `vm_*.py` | Generator and validator agents |
| `validator/` | Rule-based schema and logic validator |
| `true_seed/` | Hand-written seed dataset (easy / medium / hard) |
| `growing_seed/bckp/` | Seed datasets saved after earlier generation runs (`0th`, `1st`) |
| `generated_instructions/` | Generated instructions (instructions only, no JSON) |
| `eval_dataset/` | 100-pair evaluation set of unseen instructions: `eval_unseen_…` (initial version) and `checked_eval_unseen_…_qty_detailed_…` (verified version with detailed quantities) |

---

## Dataset format

Each entry is an Instruction/JSON pair. Every step in the plan has an `action`, a `location`, an `object` list (each item has a `description` and a `num`, where `-1` means an unknown amount) and a `duration`.

<details>
<summary>Example (hard)</summary>

```json
{
    "instruction": "Go to the supply depot and collect 10 power units. Distribute them evenly among charging station 1, charging station 2 and charging station 3. Once all power units are placed, return to the monitoring center.",
    "json": {
        "instruction": [
            {
                "action": "go_to",
                "location": "supply depot",
                "object": null,
                "duration": null
            },
            {
                "action": "wait_for_payload_ready",
                "location": "supply depot",
                "object": [
                    {
                        "description": "power units",
                        "num": "10"
                    }
                ],
                "duration": null
            },
            {
                "action": "go_to",
                "location": "charging station 1",
                "object": null,
                "duration": null
            },
            {
                "action": "wait_for_payload_removal",
                "location": "charging station 1",
                "object": [
                    {
                        "description": "power units",
                        "num": "3"
                    }
                ],
                "duration": null
            },
            {
                "action": "go_to",
                "location": "charging station 2",
                "object": null,
                "duration": null
            },
            {
                "action": "wait_for_payload_removal",
                "location": "charging station 2",
                "object": [
                    {
                        "description": "power units",
                        "num": "3"
                    }
                ],
                "duration": null
            },
            {
                "action": "go_to",
                "location": "charging station 3",
                "object": null,
                "duration": null
            },
            {
                "action": "wait_for_payload_removal",
                "location": "charging station 3",
                "object": [
                    {
                        "description": "power units",
                        "num": "4"
                    }
                ],
                "duration": null
            },
            {
                "action": "go_to",
                "location": "monitoring center",
                "object": null,
                "duration": null
            }
        ]
    }
}
```

</details>

---

## Citation

If you use DatasetSpinner or its datasets, please cite:

```bibtex
@INPROCEEDINGS{11661205,
  author={Horti, Dániel and Sopkovič, Kristián and Hládek, Daniel and Károly, Artúr I.},
  booktitle={2026 IEEE 30th International Conference on Intelligent Engineering Systems (INES)},
  title={Optimizing Training Data Diversity with DataSpinner: An LLM-driven Curator-Agent Approach},
  year={2026},
  pages={483-490},
  doi={10.1109/INES69513.2026.11661205}
}
```

## License

Released under the [MIT License](./LICENSE).
