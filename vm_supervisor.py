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
        # Ensure the API key is set
        if openai_api_key:
            os.environ['OPENAI_API_KEY'] = openai_api_key
        if os.getenv('OPENAI_API_KEY') is None:
            raise ValueError("An OpenAI API key must be set in the OPENAI_API_KEY environment variable.")
        self.client = openai.OpenAI()
        self.model = model

    def supervise(
        self,
        instruction_json_pairs: List[Tuple[str, Any]],
        instruction_type: str,
        system_prompt: str = ""
    ) -> Tuple[List[Tuple[str, Any]], str]:
        """
        Perform final, end-to-end validation of each Instruction/JSON pair.
        If the pair is valid, keep it; otherwise discard it.

        Args:
            instruction_json_pairs: List of (instruction, json) tuples.
            instruction_type: Label for difficulty (e.g., "easy", "medium", "hard").
            system_prompt: The supervisor system prompt.

        Returns:
            A tuple of (valid_pairs, instruction_type).
        """
        valid_pairs: List[Tuple[str, Any]] = []

        for instruction, orig_json in instruction_json_pairs:
            user_prompt = (
                f"Instruction:\n{instruction}\n\n"
                f"Provided JSON:\n{json.dumps(orig_json, indent=2)}\n"
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
                continue

            try:
                sup_response = response_message.parsed
            except Exception:
                # Fallback to manual parse
                try:
                    sup_response = SupervisorResponse.parse_raw(response_message.content)
                except Exception:
                    continue

            # Only keep pairs where result == "OK"
            if sup_response.result.strip() == "OK":
                valid_pairs.append((instruction, orig_json))

        return valid_pairs, instruction_type
