import openai
import os
import json
from pydantic import BaseModel
from typing import List, Tuple, Optional, Union, Any, Dict

# Pydantic schema definitions (matching the generator's format)
class ObjectItem(BaseModel):
    description: str
    num: Union[str, int]  # Either a specific number or "some"

class InstructionStep(BaseModel):
    action: str  # e.g., "go_to", "wait_for_payload_ready", "wait_for_payload_removal", "wait_for_seconds"
    location: Optional[str] = None  # May be null if not applicable
    object: Optional[Union[List[ObjectItem], None]] = None  # A list of objects or null
    duration: Optional[int] = None  # Time in seconds, or null if not applicable

class InstructionJSON(BaseModel):
    instruction: List[InstructionStep]  # List of structured robot actions

class InstructionJSONPair(BaseModel):
    instruction: str
    json: InstructionJSON

# Pydantic model for the syntax validator's response.
# If the JSON is syntactically correct, the API should return:
#   {"result": "OK"}
# Otherwise, it should return a refined InstructionJSONPair.
class ValidatedSyntax(BaseModel):
    result: Optional[str] = None
    instruction: Optional[str] = None
    json: Optional[InstructionJSON] = None

class VM_SyntaxValidator:
    def __init__(self, openai_api_key: str = None, model: str = "gpt-4.1"):
        # Ensure the API key is set in the environment.
        if os.getenv('OPENAI_API_KEY') is None:
            raise ValueError("An OpenAI API key must be set in the OPENAI_API_KEY environment variable.")
        self.client = openai.OpenAI()
        self.model = model

    def validate_syntax(
        self,
        instruction_json_pairs: List[Tuple[str, Any]],
        instruction_type: str,
        system_prompt: str = ""
    ) -> Tuple[List[Tuple[str, Any]], str]:
        """
        Validate the syntax of each instruction/JSON pair against the required schema.
        For each pair, an API call is made with the following behavior:
          - If the JSON is syntactically correct, the API returns: {"result": "OK"}
          - Otherwise, it returns a refined JSON following InstructionJSONPair format.

        Args:
            instruction_json_pairs (List[Tuple[str, Any]]): List of tuples (instruction, json).
            instruction_type (str): A label for the instruction difficulty.
            system_prompt (str): A system prompt describing the syntax validation task.

        Returns:
            Tuple[List[Tuple[str, Any]], str]:
              - A list of tuples (instruction, validated_json) where validated_json
                is either the original JSON (if valid) or the refined JSON.
              - The instruction_type label.
        """
        syntax_system_prompt = system_prompt
        validated_pairs: List[Tuple[str, Any]] = []

        for instruction, orig_json in instruction_json_pairs:
            user_prompt = (
                "Validate the syntax of the provided JSON against the required schema.\n\n"
                "Instruction:\n"
                f"{instruction}\n\n"
                "Provided JSON:\n"
                f"{json.dumps(orig_json, indent=2)}\n\n"
            )

            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": syntax_system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=ValidatedSyntax,
            )

            response_message = completion.choices[0].message
            
            if hasattr(response_message, "refusal") and response_message.refusal:
                print(f"Refusal: {response_message.refusal}")
                validated_output = {"instruction": instruction, "json": orig_json}
            else:
                try:
                    validated_solution = response_message.parsed
                except Exception:
                    content = response_message.content
                    try:
                        validated_solution = ValidatedSyntax.parse_raw(content)
                    except Exception:
                        validated_solution = ValidatedSyntax(result="Error")

                if validated_solution.result == "OK":
                    validated_output = {"instruction": instruction, "json": orig_json}
                else:
                    if validated_solution.instruction is not None and validated_solution.json is not None:
                        # Use the refined JSON from the validator
                        validated_output = {
                            "instruction": validated_solution.instruction,
                            "json": validated_solution.json
                        }
                    else:
                        validated_output = {"instruction": instruction, "json": orig_json}

            validated_pairs.append((validated_output["instruction"], validated_output["json"]))

        return validated_pairs, instruction_type
