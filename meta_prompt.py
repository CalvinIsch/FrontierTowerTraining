"""
Lab 09 — Meta Prompting  (Step 1)

build_prompt() turns a one-line task description into a structured,
model-ready prompt with role, constraints, output schema, and example slots.
"""


def build_prompt(task: str) -> str:
    """Turn a one-line task into a structured, model-ready prompt."""
    return f"""\
## Role
You are an expert classifier. Your only job is to {task}.

## Constraints
- Return ONLY JSON. Every field required. Use null if unsure.
- Do not add explanation, markdown fences, or prose outside the JSON.
- Choose the single most appropriate label from the categories listed.

## Output Schema
{{
  "label":      "<category string>",
  "confidence": <float 0.0–1.0>,
  "reason":     "<one sentence>"
}}

## Examples
{{
  "input": "<EXAMPLE_INPUT_1>",
  "output": {{"label": "<LABEL>", "confidence": 0.9, "reason": "<WHY>"}}
}}

## Input
{{{{input}}}}"""


if __name__ == "__main__":
    print(build_prompt("classify support tickets"))
