import openai
import os
import json
from pydantic import BaseModel
from typing import List, Tuple

# Define the Pydantic schema for generated instructions
class GeneratedInstructions(BaseModel):
    instructions: List[str]

class GM_InstructionGenerator:
    def __init__(self, openai_api_key: str = None, model: str = "gpt-4.1"):
        # Check the API key presence in environment variable
        if os.getenv('OPENAI_API_KEY') is None:
            raise ValueError("An OpenAI API key must be set in the OPENAI_API_KEY environment variable.")

        # Initialize the OpenAI client using the provided example
        self.client = openai.OpenAI()
        self.model = model

    def generate_instructions(self, sample_instructions: List[str], seed_type: str = "", system_prompt: str = "", num_of_new_instructions: int = 20) -> Tuple[List[str], str]:
        """
        Generate new mobile robot instructions based on sample instructions.
        
        Args:
            sample_instructions (List[str]): A list of sample instructions to serve as context.
            system_prompt: A system prompt to use during generation.
            num_of_new_instructions (int): Number of new instructions to generate.
        
        Returns:
            List[str]: A list of generated instruction strings.
        """
        # Create a context string from sample instructions
        sample_text = "\n".join(sample_instructions)
        user_prompt = (
            f"Based on the following sample instructions:\n{sample_text}\n\n"
            f"Generate {num_of_new_instructions} new mobile robot instructions. "
            "Output the result as a JSON object with a single key 'instructions' whose value is a list of instruction strings. "
            "Ensure that the instructions are creative, diverse, and cover a wide range of operational scenarios."
        )
        
        # Call the OpenAI API using the beta chat completions parser
        completion = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=GeneratedInstructions,
        )
        
        # Access parsed output from the first choice
        instruction_dataset = completion.choices[0].message
        
        # If the model refuses to respond, return an empty list
        if hasattr(instruction_dataset, "refusal") and instruction_dataset.refusal:
            print(f"Refusal: {instruction_dataset.refusal}")
            return []
        
        try:
            # Try to get the parsed instructions from the response
            instructions_list = instruction_dataset.parsed.instructions
        except Exception as e:
            # Fallback: manually parse the content if needed
            content = instruction_dataset.content
            try:
                generated = GeneratedInstructions.parse_raw(content)
                instructions_list = generated.instructions
            except Exception:
                instructions_list = [line.strip() for line in content.splitlines() if line.strip() and any(char.isalnum() for char in line)]
        
        # Append the generated instructions to a file
        output_directory = "./generated_instructions"
        os.makedirs(output_directory, exist_ok=True)
        output_file = os.path.join(output_directory, "generated.json")
        
        # Load existing instructions from the file if available
        try:
            if os.path.exists(output_file):
                with open(output_file, "r") as f:
                    data = f.read()
                    if data:
                        existing_data = json.loads(data)
                        if isinstance(existing_data, list):
                            all_instructions = existing_data + instructions_list
                        else:
                            all_instructions = instructions_list
                    else:
                        all_instructions = instructions_list
            else:
                all_instructions = instructions_list
        except Exception as ex:
            all_instructions = instructions_list
        
        # Save the updated instructions list back to the file
        with open(output_file, "w") as f:
            json.dump(all_instructions, f, indent=4)
        
        return instructions_list, seed_type
