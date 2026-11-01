"""One extractor per input kind (strategy pattern), plus the kind detector.

To support a new kind, add a schema and an Extractor subclass, then list it
in EXTRACTORS.
"""
from .schemas import DocKind, EmailRecord, LogRecord, TicketRecord

DETECT_CHARS = 2000  # how much text the auto-detect call looks at

# Appended to every prompt; small local models need the plain-text reminder
RULES = (
    " Today is {today}. Resolve relative dates against the date the text was written when it is known."
    " Write summaries as one plain sentence without markdown. Use null or an empty list for anything"
    " the text does not state; do not guess."
)


class Extractor:
    """Base class: subclasses set kind, schema and prompt."""
    kind = None
    schema = None
    prompt = None

    def __init__(self, llm):
        self.llm = llm

    def system_prompt(self, today):
        return self.prompt + RULES.format(today=today)

    def extract(self, text, today):
        """Returns (record, CallCost) where record is an instance of self.schema."""
        return self.llm.parse(self.system_prompt(today), text, self.schema, step="extract")


class EmailExtractor(Extractor):
    kind = "email"
    schema = EmailRecord
    prompt = "Extract the key details from the email below."


class LogExtractor(Extractor):
    kind = "log"
    schema = LogRecord
    prompt = ("Parse the log excerpt below into structured events, one per log entry."
              " The summary describes the outcome of the whole excerpt, not its first line.")


class TicketExtractor(Extractor):
    kind = "ticket"
    schema = TicketRecord
    prompt = "Extract the support ticket details from the text below."


EXTRACTORS = [EmailExtractor, LogExtractor, TicketExtractor]


class KindDetector:
    prompt = "Classify the text as an email, a log excerpt, or a support ticket."

    def __init__(self, llm):
        self.llm = llm

    def detect(self, text):
        """Returns (kind, CallCost)."""
        result, call = self.llm.parse(self.prompt, text[:DETECT_CHARS], DocKind, step="detect")
        return result.kind, call
