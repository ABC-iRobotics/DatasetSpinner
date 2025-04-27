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

# Pydantic model for the validator's response.
# If the JSON is logically correct, the API should return:
#   {"result": "OK"}
# Otherwise, it should return a refined InstructionJSONPair.
class ValidatedSolution(BaseModel):
    result: Optional[str] = None
    instruction: Optional[str] = None
    json: Optional[InstructionJSON] = None

class VM_LogicValidator:
    def __init__(self, openai_api_key: str = None):
        # Ensure the API key is set in the environment.
        if os.getenv('OPENAI_API_KEY') is None:
            raise ValueError("An OpenAI API key must be set in the OPENAI_API_KEY environment variable.")
        self.client = openai.OpenAI()

    def validate_logic(self, instruction_json_pairs: List[Tuple[str, Any]], instruction_type: str, system_prompt: str = "") -> Tuple[List[Tuple[str, Any]], str]:
        """
        Validate each instruction/JSON pair to ensure that the JSON logically fulfills the instruction.
        For each pair, an API call is made with the following behavior:
          - If the JSON is logically correct, the API returns: {"result": "OK"}
          - Otherwise, the API returns a refined JSON following the InstructionJSONPair format.
        
        Args:
            instruction_json_pairs (List[Tuple[str, Any]]): List of tuples (instruction, json) as produced by GM_JSONGenerator.
            instruction_type (str): A label for the type of instructions (e.g., "easy", "medium", "hard").
            system_prompt (str): A system prompt describing the logic validation task.
        
        Returns:
            Tuple[List[Tuple[str, Any]], str]: A tuple containing:
                - A list of tuples (instruction, validated_json), where validated_json is either the original JSON (if valid) or the refined JSON.
                - The instruction_type label.
        """
        logic_system_prompt = system_prompt
        validated_pairs = []

        for instruction, orig_json in instruction_json_pairs:
            user_prompt = (
                "Check if the following JSON logically fulfills the instruction.\n\n"
                "Instruction:\n"
                f"{instruction}\n\n"
                "Provided JSON:\n"
                f"{json.dumps(orig_json, indent=2)}\n\n"
                "If the JSON is logically correct and satisfies the instruction, reply with exactly:\n"
                "```json\n"
                "{\n"
                "  \"result\": \"OK\"\n"
                "}\n"
                "```\n"
                "If not, provide a refined version that follows this exact format:\n\n"
                "```json\n"
                "{\n"
                "  \"instruction\": \"<original instruction>\",\n"
                "  \"json\": {\n"
                "    \"instruction\": [\n"
                "      { \"action\": \"<action>\", \"location\": \"<location or null>\", \"object\": <object or null>, \"duration\": <duration or null> }\n"
                "    ]\n"
                "  }\n"
                "}\n"
                "```\n\n"
                "Return only the JSON response without any extra text."
            )

            # Call the OpenAI API (using beta chat completions parser) for logic validation.
            completion = self.client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": logic_system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=ValidatedSolution,
            )

            response_message = completion.choices[0].message

            if hasattr(response_message, "refusal") and response_message.refusal:
                print(f"Refusal: {response_message.refusal}")
                validated_output = {"instruction": instruction, "json": orig_json}
            else:
                try:
                    validated_solution = response_message.parsed
                except Exception as e:
                    content = response_message.content
                    try:
                        validated_solution = ValidatedSolution.parse_raw(content)
                    except Exception:
                        validated_solution = ValidatedSolution(result="Error")
                
                # If the output is {"result": "OK"}, the JSON is logically correct.
                if validated_solution.result == "OK":
                    validated_output = {"instruction": instruction, "json": orig_json}
                else:
                    # Otherwise, use the refined version returned by the API.
                    if validated_solution.instruction is not None and validated_solution.json is not None:
                        validated_output = {"instruction": validated_solution.instruction, "json": validated_solution.json}
                    else:
                        validated_output = {"instruction": instruction, "json": orig_json}

            validated_pairs.append((validated_output["instruction"], validated_output["json"]))

        return validated_pairs, instruction_type
