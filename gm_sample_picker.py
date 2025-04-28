import json
import os
import random
from typing import List, Optional, Any, Dict

class SamplePicker:
    def __init__(self, seed_folder: str):
        """
        Initialize the SamplePicker by loading seed files from the given folder.
        Expects the following files in the folder: seed_easy.json, seed_medium.json, seed_hard.json.
        """
        self.seed_folder = seed_folder
        self.seeds: Dict[str, List[Dict[str, Any]]] = {}  # stores the loaded seed data per type
        self.unchosen_indices: Dict[str, List[int]] = {}  # tracks indices that haven't been picked yet

        for seed_type in ["easy", "medium", "hard"]:
            file_path = os.path.join(seed_folder, f"seed_{seed_type}.json")
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                    self.seeds[seed_type] = data
                    # Initialize tracking with all indices available
                    self.unchosen_indices[seed_type] = list(range(len(data)))
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
                    self.seeds[seed_type] = []
                    self.unchosen_indices[seed_type] = []
            else:
                self.seeds[seed_type] = []
                self.unchosen_indices[seed_type] = []

    def get_instructions(self, seed_type: str, num_samples: int) -> Optional[Dict[str, Any]]:
        """
        Returns a JSON object containing a list of sample instructions from the specified seed type.
        Samples are chosen evenly across the unchosen samples. If there are not enough unchosen samples,
        the method returns None.
        """
        if seed_type not in self.seeds:
            print(f"Unknown seed type: {seed_type}")
            return None

        available = sorted(self.unchosen_indices[seed_type])
        total = len(available)
        if total < num_samples:
            return None

        segment = total / num_samples
        chosen = []
        for i in range(num_samples):
            start = int(round(i * segment))
            end = int(round((i + 1) * segment))
            block = available[start:end] or [available[start]]
            idx = random.choice(block)
            chosen.append(idx)

        # mark chosen indices
        self.unchosen_indices[seed_type] = [i for i in self.unchosen_indices[seed_type] if i not in chosen]

        samples = [self.seeds[seed_type][i]["instruction"] for i in chosen]
        return {"samples": samples}

    def get_full_examples(self, seed_type: str, num_examples: int) -> Optional[Dict[str, Any]]:
        """
        Returns a JSON object containing full instruction+json entries for the specified seed type.
        Samples are chosen evenly across unchosen; returns None if insufficient.
        """
        if seed_type not in self.seeds:
            print(f"Unknown seed type: {seed_type}")
            return None

        available = sorted(self.unchosen_indices[seed_type])
        total = len(available)
        if total < num_examples:
            return None

        segment = total / num_examples
        chosen = []
        for i in range(num_examples):
            start = int(round(i * segment))
            end = int(round((i + 1) * segment))
            block = available[start:end] or [available[start]]
            idx = random.choice(block)
            chosen.append(idx)

        self.unchosen_indices[seed_type] = [i for i in self.unchosen_indices[seed_type] if i not in chosen]

        examples = []
        for i in chosen:
            entry = self.seeds[seed_type][i]
            examples.append({"instruction": entry["instruction"], "json": entry["json"]})
        return {"examples": examples}

    def reset(self, seed_type: Optional[str] = None):
        """
        Reset the tracking of chosen samples. If seed_type is provided, only that type is reset;
        otherwise, all types are reset.
        """
        if seed_type:
            if seed_type in self.seeds:
                self.unchosen_indices[seed_type] = list(range(len(self.seeds[seed_type])))
        else:
            for st in self.seeds:
                self.unchosen_indices[st] = list(range(len(self.seeds[st])))

    def append_new_pairs(self, seed_type: str, new_pairs: List[Dict[str, Any]]) -> None:
        """
        Append new instruction/JSON pairs to the seed database for the given type.
        New entries are written to disk and marked as unchosen, while previously chosen remain marked.
        """
        if seed_type not in self.seeds:
            raise ValueError(f"Unknown seed type: {seed_type}")

        # Current length before appending
        current_len = len(self.seeds[seed_type])
        # Append in-memory
        self.seeds[seed_type].extend(new_pairs)

        # Write back to seed file
        file_path = os.path.join(self.seed_folder, f"seed_{seed_type}.json")
        os.makedirs(self.seed_folder, exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(self.seeds[seed_type], f, indent=4)

        # Mark new indices as unchosen
        new_indices = list(range(current_len, current_len + len(new_pairs)))
        self.unchosen_indices[seed_type].extend(new_indices)
