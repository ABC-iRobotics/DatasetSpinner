import openai
import os
import json
from pydantic import BaseModel
from typing import List, Tuple, Optional, Union, Any, Dict

# Updated Pydantic schema to match the example
class ObjectItem(BaseModel):
    description: str
    num: Union[str, int]  # Either a specific number or "some"

class InstructionStep(BaseModel):
    action: str  # e.g., "go_to", "wait_for_payload_ready", etc.
    location: Optional[str] = None  # May be null if not applicable
    object: Optional[Union[List[ObjectItem], None]] = None  # A list of objects or null
    duration: Optional[int] = None  # Time in seconds, or null if not applicable

class InstructionJSON(BaseModel):
    instruction: List[InstructionStep]  # List of structured robot actions

class InstructionJSONPair(BaseModel):
    instruction: str
    json: InstructionJSON

class GM_JSONGenerator:
    def __init__(self, openai_api_key: str = None, model: str = "gpt-4.1"):
        # Ensure the API key is set in the environment
        if os.getenv('OPENAI_API_KEY') is None:
            raise ValueError("An OpenAI API key must be set in the OPENAI_API_KEY environment variable.")
        # Initialize the OpenAI client using the provided API key.
        self.client = openai.OpenAI()
        self.model = model

    def generate_json(self, new_instructions: List[str], examples: Dict[str, Any], instruction_type: str, system_prompt: str = "") -> Tuple[List[Tuple[str, Any]], str]:
        """
        Convert each instruction from new_instructions into its JSON representation of robotic actions.
        The API call uses a system prompt and includes examples of expected Instruction/JSON pairs (of the same type).
        The expected output is a JSON object that strictly adheres to the following format:
        
        {
          "instruction": "<original instruction>",
          "json": {
            "instruction": [
              { "action": "<action>", "location": "<location or null>", "object": <object or null>, "duration": <duration or null> }
            ]
          }
        }
        
        Args:
            new_instructions (List[str]): A list of instructions to be converted.
            examples (Dict[str, Any]): A dictionary containing example Instruction/JSON pairs.
            instruction_type (str): A label for the type of instructions being processed.
            system_prompt (str): A system prompt that describes the conversion task.
            
        Returns:
            Tuple[List[Tuple[str, Any]], str]: A tuple containing:
                - A list of tuples (instruction, json) where json adheres to the schema above.
                - The instruction_type label.
        """
        conversion_system_prompt = system_prompt
        instruction_JSON_pairs = []

        for instruction in new_instructions:
            user_prompt = (
                f"Here are some examples of Instruction/JSON pairs:\n{json.dumps(examples, indent=2)}\n\n"
                "Please convert the following instruction into a JSON object that strictly adheres to this format:\n\n"
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
                "Make sure the output is valid JSON and does not include any additional text. "
                "The output must include the original instruction in the \"instruction\" field.\n\n"
                f"Instruction to convert:\n{instruction}\n"
            )

            # Call the OpenAI API using the beta chat completions parser and our updated response format.
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": conversion_system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=InstructionJSONPair,
            )

            json_output = completion.choices[0].message

            if hasattr(json_output, "refusal") and json_output.refusal:
                print(f"Refusal: {json_output.refusal}")
                output_pair = {"instruction": instruction, "json": {}}
            else:
                try:
                    output_pair = json_output.parsed.dict()
                except Exception as e:
                    content = json_output.content
                    try:
                        parsed = json.loads(content)
                        output_pair = parsed
                    except Exception:
                        output_pair = {"instruction": instruction, "json": {}}

            # Append the pair as a tuple (instruction, json) to the result list.
            instruction_JSON_pairs.append((output_pair["instruction"], output_pair["json"]))

        return instruction_JSON_pairs, instruction_type
