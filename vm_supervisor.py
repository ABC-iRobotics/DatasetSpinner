import openai
import os
import json
from pydantic import BaseModel
from typing import List, Tuple, Any

# Pydantic model for the supervisor's response
class SupervisorResponse(BaseModel):
    result: str  # "OK" or "INVALID - Reason: ..."

class VM_Supervisor:
    def __init__(self, openai_api_key: str = None, model: str = "gpt-4.1"):
        # Ensure the API key is set in the environment
        if os.getenv('OPENAI_API_KEY') is None:
            raise ValueError("An OpenAI API key must be set in the OPENAI_API_KEY environment variable.")
        self.client = openai.OpenAI()
        self.model = model

    def supervise(
        self,
        instruction_json_pairs: List[Tuple[str, Any]],
        instruction_type: str,
        system_prompt: str = ""
    ) -> Tuple[List[Tuple[str, Any]], List[Tuple[str, str]], str]:
        """
        Perform final, end-to-end validation of each Instruction/JSON pair.
        Returns both valid pairs and invalid pairs with reasons.

        Args:
            instruction_json_pairs: List of (instruction, json) tuples.
            instruction_type: Label for difficulty (e.g., "easy", "medium", "hard").
            system_prompt: The supervisor system prompt.

        Returns:
            A tuple of (valid_pairs, invalid_pairs_with_reason, instruction_type).
        """
        valid_pairs: List[Tuple[str, Any]] = []
        invalid_pairs: List[Tuple[str, str]] = []

        for instruction, orig_json in instruction_json_pairs:
            # Convert Pydantic model to dict if necessary
            provided_json = orig_json if isinstance(orig_json, dict) else orig_json.dict()

            user_prompt = (
                f"Instruction:{instruction}"
                f"Provided JSON:{json.dumps(provided_json, indent=2)}"
            )

            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system",  "content": system_prompt},
                    {"role": "user",    "content": user_prompt}
                ],
                response_format=SupervisorResponse,
            )

            response_message = completion.choices[0].message
            # Skip if refusal
            if hasattr(response_message, "refusal") and response_message.refusal:
                invalid_pairs.append((instruction, f"Refusal: {response_message.refusal}"))
                continue

            try:
                sup_response = response_message.parsed
            except Exception:
                # Fallback to manual parse
                try:
                    sup_response = SupervisorResponse.parse_raw(response_message.content)
                except Exception:
                    invalid_pairs.append((instruction, "Parsing error"))
                    continue

            result = sup_response.result.strip()
            # Keep or record invalid with reason
            if result == "OK":
                valid_pairs.append((instruction, provided_json))
            else:
                invalid_pairs.append((instruction, result))

        return valid_pairs, invalid_pairs, instruction_type
