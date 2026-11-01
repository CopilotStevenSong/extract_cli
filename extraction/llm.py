"""Thin wrapper around an OpenAI-compatible chat endpoint (Ollama by default)."""
import time

import openai
from openai import OpenAI

from .cost import CallCost, Pricing

DEFAULT_MODEL = "gpt-oss:20b"
DEFAULT_BASE_URL = "http://localhost:11434/v1"
# Low keeps gpt-oss's hidden reasoning short, which is most of the run time on a local model
DEFAULT_REASONING_EFFORT = "low"


class ExtractionError(Exception):
    pass


class LLMClient:
    def __init__(self, model=DEFAULT_MODEL, base_url=DEFAULT_BASE_URL, api_key="ollama", pricing=None,
                 reasoning_effort=DEFAULT_REASONING_EFFORT):
        self.model = model
        self.pricing = pricing or Pricing()
        self.reasoning_effort = reasoning_effort  # "low" | "medium" | "high"
        self._client = OpenAI(base_url=base_url, api_key=api_key)  # Ollama ignores the key

    def parse(self, system, text, schema, step):
        """Ask for a reply matching `schema`; returns (parsed model, CallCost).

        `step` names the call (e.g. "detect", "extract") in the cost breakdown.
        """
        # parse() turns the Pydantic model into a strict json_schema
        # response_format and validates the reply back into that model
        started = time.perf_counter()
        try:
            response = self._client.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": text},
                ],
                response_format=schema,
                reasoning_effort=self.reasoning_effort,
            )
        except openai.LengthFinishReasonError:
            raise ExtractionError("reply was cut off before the JSON was complete")
        except openai.APIStatusError as e:
            raise ExtractionError(f"HTTP {e.status_code}: {e.message}")
        except openai.APIConnectionError as e:
            raise ExtractionError(f"connection failed ({e}); is the server at the base URL running?")

        message = response.choices[0].message
        # The model may decline instead of answering; then parsed is None
        if message.refusal:
            raise ExtractionError(f"model refused: {message.refusal}")
        if message.parsed is None:
            raise ExtractionError("model returned no parseable JSON")
        duration = time.perf_counter() - started
        return message.parsed, CallCost.from_usage(step, self.model, response.usage, self.pricing, duration)
