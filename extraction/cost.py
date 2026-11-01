"""Token usage and cost of each model call."""
from dataclasses import dataclass

# DeepSeek V4 Flash, peak cache-miss rates in USD per 1M tokens
# (https://api-docs.deepseek.com/quick_start/pricing, checked 2026-11-01; off-peak is half)
DEFAULT_INPUT_PRICE = 0.30
DEFAULT_OUTPUT_PRICE = 1.20


@dataclass(frozen=True)
class Pricing:
    """USD per 1M tokens. Defaults to DeepSeek V4 Flash; use 0 for a free local model."""
    input_per_million: float = DEFAULT_INPUT_PRICE
    output_per_million: float = DEFAULT_OUTPUT_PRICE

    def cost(self, input_tokens, output_tokens):
        return (input_tokens * self.input_per_million
                + output_tokens * self.output_per_million) / 1_000_000


@dataclass(frozen=True)
class CallCost:
    """One model call: what it was for, tokens used, what it cost and how long it took."""
    step: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    duration_s: float = 0.0

    @property
    def total_tokens(self):
        return self.input_tokens + self.output_tokens

    @classmethod
    def from_usage(cls, step, model, usage, pricing, duration_s=0.0):
        # Some OpenAI-compatible servers omit usage; count those calls as 0 tokens
        input_tokens = (usage.prompt_tokens or 0) if usage else 0
        output_tokens = (usage.completion_tokens or 0) if usage else 0
        return cls(step, model, input_tokens, output_tokens, pricing.cost(input_tokens, output_tokens), duration_s)
