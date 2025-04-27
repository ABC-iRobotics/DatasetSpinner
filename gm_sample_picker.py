import json
import os
import random
from typing import List, Optional, Any

class SamplePicker:
    def __init__(self, seed_folder: str):
        """
        Initialize the SamplePicker by loading seed files from the given folder.
        Expects the following files in the folder: seed_easy.json, seed_medium.json, seed_hard.json.
        """
        self.seed_folder = seed_folder
        self.seeds = {}  # stores the loaded seed data per type
        self.unchosen_indices = {}  # tracks indices that haven't been picked yet

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

    def get_instructions(self, seed_type: str, num_samples: int) -> Optional[dict]:
        """
        Returns a JSON object containing a list of sample instructions from the specified seed type.
        Samples are chosen evenly across the unchosen samples. If there are not enough unchosen samples,
        the method returns None.

        Args:
            seed_type (str): The type of seed to pick from ("easy", "medium", "hard").
            num_samples (int): The number of samples to return.

        Returns:
            Optional[dict]: A JSON object with key "samples" containing a list of instruction strings,
                            or None if there are insufficient unchosen samples.
        """
        if seed_type not in self.seeds:
            print(f"Unknown seed type: {seed_type}")
            return None

        available_indices = sorted(self.unchosen_indices[seed_type])
        total_available = len(available_indices)
        if total_available < num_samples:
            # Not enough unchosen samples remain
            return None

        # Divide available indices into roughly equal segments and choose one index per segment.
        segment_size = total_available / num_samples
        chosen_indices = []
        for i in range(num_samples):
            start = int(round(i * segment_size))
            end = int(round((i + 1) * segment_size))
            # Ensure we have a non-empty segment
            segment = available_indices[start:end]
            if not segment:
                segment = [available_indices[start]]
            chosen_index = random.choice(segment)
            chosen_indices.append(chosen_index)

        # Remove the chosen indices from the unchosen tracker.
        self.unchosen_indices[seed_type] = [
            idx for idx in self.unchosen_indices[seed_type] if idx not in chosen_indices
        ]

        # Build a list of instruction strings from the chosen samples.
        samples = [self.seeds[seed_type][idx]["instruction"] for idx in chosen_indices]
        return {"samples": samples}

    def get_full_examples(self, seed_type: str, num_examples: int) -> Optional[dict[str, Any]]:
        """
        Returns a JSON object containing a list of full (instruction + json) entries 
        from the specified seed type. Entries are chosen evenly across the unchosen 
        samples. If there are not enough unchosen samples, the method returns None.
    
        Args:
            seed_type (str): The type of seed to pick from ("easy", "medium", "hard").
            num_examples (int): The number of examples to return.
    
        Returns:
            Optional[dict]: A JSON object with key "samples" containing a list of 
                            objects with "instruction" and "json" fields,
                            or None if there are insufficient unchosen samples.
        """
        # Ensure the seed type exists
        if seed_type not in self.seeds:
            print(f"Unknown seed type: {seed_type}")
            return None
    
        # Get the current unchosen indices for this seed type
        available_indices = sorted(self.unchosen_indices[seed_type])
        total_available = len(available_indices)
        
        if total_available < num_examples:
            # Not enough unchosen samples remain
            return None
    
        # Divide available indices into roughly equal segments and choose one index per segment.
        segment_size = total_available / num_examples
        chosen_indices = []
        for i in range(num_examples):
            start = int(round(i * segment_size))
            end = int(round((i + 1) * segment_size))
            # Ensure we have a non-empty segment
            segment = available_indices[start:end] or [available_indices[start]]
            chosen_index = random.choice(segment)
            chosen_indices.append(chosen_index)
    
        # Remove the chosen indices from the unchosen tracker.
        self.unchosen_indices[seed_type] = [
            idx for idx in self.unchosen_indices[seed_type] if idx not in chosen_indices
        ]
    
        # Build a list of {"instruction": ..., "json": ...} from the chosen samples.
        chosen_entries = []
        for idx in chosen_indices:
            entry = self.seeds[seed_type][idx]
            chosen_entries.append({
                "instruction": entry["instruction"],
                "json": entry["json"]
            })
        return {"examples": chosen_entries}

    def reset(self, seed_type: Optional[str] = None):
        """
        Reset the tracking of chosen samples. If a seed_type is provided, only that type is reset;
        otherwise, all types are reset.
        """
        if seed_type:
            if seed_type in self.seeds:
                self.unchosen_indices[seed_type] = list(range(len(self.seeds[seed_type])))
        else:
            for st in self.seeds:
                self.unchosen_indices[st] = list(range(len(self.seeds[st])))
