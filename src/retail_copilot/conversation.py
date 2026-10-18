"""Resolve a follow-up before retrieval, using bounded user questions only.

Conversation is reference context, never policy evidence. Simple independent
questions and explicit noun replies bypass the model; unclear questions ask for
clarification. When needed,
the existing local answering model proposes a standalone question. Schema,
vocabulary and topic checks reject many bad rewrites, but do not prove semantic
equivalence. This conservative English demo may ask unnecessary clarifications;
real model follow-up quality still needs evaluation. No history is persisted here.
"""

import json
import re

from retail_copilot.documents import PROJECT_ROOT
from retail_copilot.generate import generation_options, input_budget, inspect_model
from retail_copilot.ollama_embeddings import request_local_json


class ConversationError(ValueError):
    """A safe explanation of invalid conversation input or configuration."""


_REFERENCES = re.compile(r"\b(it|its|this|that|these|those|they|them|their|one|ones|he|she|him|her|there|same)\b", re.I)
_ELLIPTICAL = re.compile(
    r"^(and\b|also\b|what about\b|how about\b|how (much|long)\b|why\b|"
    r"what (else|should i bring)\b|can (i|we) (replace|return|activate|book)\s*\??$)", re.I)
# Topic words are routing hints, not policy rules or an approved knowledge list.
_TOPICS = {
    "sim": r"\b(?:physical\s+)?sim\b",
    "esim": r"\be-?sim\b",
    "roaming": r"\broaming\b",
    "billing": r"\b(?:bill|billing|payment|charge|fee)s?\b",
    "device": r"\b(?:device|phone|handset|screen)s?\b",
    "collection": r"\b(?:click.and.collect|collection|collect|order)s?\b",
    "plan": r"\b(?:mobile\s+)?plans?\b",
    "identity": r"\b(?:identity|identification|idv-\d+|verification)\b",
    "authority": r"\b(?:authority|ownership|delegation|account|contact)s?\b",
    "appointment": r"\b(?:appointment|booking)s?\b",
}
_GRAMMAR = set("a an the i me my we us our you your he him his she her they them their it its this that these those one ones there same of for to from in on at with by and or but do does did is are was were be been can could should would will may might please about what which how when where why anyway also else".split())
_UNSAFE = re.compile(r"<|>|\[|\]|```|https?://|www\.|[\x00-\x08\x0b-\x1f\x7f]", re.I)
# A request starts with a verb; a label such as "plan change" does not.
# These are language hints only. Downstream answering still cannot take action.
_EXECUTION_VERBS = (
    r"(?:waive|refund|pay|cancel|disconnect|activate|deactivate|replace|return|book|"
    r"change|switch|update|modify|transfer|reset|release|collect|process|apply|"
    r"remove|enable|disable|upgrade|downgrade|unlock|reconnect|renew|send|schedule)"
)
_REQUEST_START = re.compile(
    r"^(?:(?:please|kindly|ok|okay|thanks|thank you)[\s,!.]+)*"
    r"(?:(?:do not|don't|don’t|never)\s+)?"
    rf"(?:{_EXECUTION_VERBS}|check|tell|show|explain|help)\b", re.I)


def requests_execution(question: str) -> bool:
    """Recognise explicit requests to carry out an action, never policy rules.

    This conservative English guard needs both a directed action and a named
    service object. Knowledge questions, quotations, reports and hypothetical
    examples do not by themselves request execution. A False result is not
    permission to act: the answering instructions always prohibit execution.
    """
    if not isinstance(question, str) or not question.strip():
        return False
    # Do not turn quoted examples into commands. Apostrophes inside words,
    # including "don't" and "customer's", are not quotation delimiters.
    text = re.sub(r'''`[^`]*`|"[^"]*"|“[^”]*”|(?<!\w)'[^']*'(?!\w)|‘[^’]*’''', " ", question)
    for sentence in re.split(r"[.!?;\n]+", text):
        sentence = sentence.strip()
        if (re.match(r"^(?:what if|if|suppose|imagine|hypothetically|for example)\b", sentence, re.I)
                or re.match(r"^(?:please\s+)?(?:do not|don't|don’t|never)\b", sentence, re.I)
                or re.match(r"^(?:can|could|would|will)\s+you\s+(?:please\s+)?not\b", sentence, re.I)
                or re.search(r"\b(?:said|says|asked|asks|asking|wrote|writes|reported|example|hypothetical)\b", sentence, re.I)):
            continue
        for clause in re.split(r",|\b(?:and|then|also)\b", sentence, flags=re.I):
            action = re.match(
                r"^\s*(?:(?:please|kindly|ok|okay|thanks|thank you)\s+)*"
                r"(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?|"
                r"i\s+(?:want|need|would like)\s+you\s+to\s+|"
                r"i['’]d\s+like\s+you\s+to\s+)?"
                + _EXECUTION_VERBS + r"\b\s+(?P<object>.+)$", clause, re.I)
            if action is None:
                continue
            target = action.group("object")
            # "Return policy for devices" is a topic label, not an imperative.
            if re.match(r"(?:policy|policies|process|procedure|window|period)\b", target, re.I):
                continue
            if _topics(target):
                return True
    return False


def asks_about_own_action(question: str) -> bool:
    """Recognise a narrow self-service policy question, not a request to act.

    This only distinguishes the actor in a clear single question. It does not
    establish eligibility, available evidence or permission to do anything.
    """
    if not isinstance(question, str) or requests_execution(question):
        return False
    text = question.strip()
    if re.search(r"\byou\b", text, re.I) or not _topics(text):
        return False
    return re.fullmatch(
        r"(?:can|could|may)\s+i\s+(?:book|replace|return|collect|request|use|change|"
        r"activate|cancel|upgrade|pay|switch)\b[^.!?;\n]*\??", text, re.I,
    ) is not None


def acknowledgement_reply(question: str) -> str | None:
    """Recognise only complete social acknowledgements, without model calls.

    None means normal question handling should continue. In particular, yes/no
    may answer a clarification, and thanks followed by a request must keep that
    request. Input length and configuration remain the caller's responsibility.
    """
    if not isinstance(question, str):
        return None
    normalized = " ".join(re.sub(r"[.,!?;:]", " ", question.casefold()).split())
    thanks = {"thanks", "thank you", "thanks very much", "thank you very much", "many thanks"}
    acknowledgements = {"ok", "okay", "got it", "understood", "i understand"}
    for prefix in ("ok", "okay", "great", "alright"):
        thanks.update(f"{prefix} {phrase}" for phrase in ("thanks", "thank you"))
    acknowledgements.update(f"{prefix} {phrase}"
                            for prefix in ("ok", "okay") for phrase in ("got it", "understood"))
    if normalized in thanks:
        return "You're welcome!"
    if normalized in acknowledgements:
        return "Of course. Let me know if you have another question."
    return None


def conversation_limits(settings: dict) -> dict:
    """Validate shared bounds before policy resolution or acknowledgement handling."""
    if not isinstance(settings, dict):
        raise ConversationError("Check the conversation settings.")
    defaults = {"max_history_turns": 3, "max_question_characters": 1000, "max_history_characters": 4000}
    options = settings.get("conversation", {})
    if not isinstance(options, dict):
        raise ConversationError("Check the conversation settings section.")
    limits = {name: options.get(name, default) for name, default in defaults.items()}
    for name, lower, upper in (("max_history_turns", 0, 10), ("max_question_characters", 20, 4000),
                               ("max_history_characters", 0, 12000)):
        if type(limits[name]) is not int or not lower <= limits[name] <= upper:
            raise ConversationError("Check the whole-number question and conversation memory limits.")
    return limits


def _recent_questions(history: list, limits: dict) -> list[dict]:
    """Keep complete recent turns only; never skip a gap to revive older topics."""
    if not isinstance(history, list):
        raise ConversationError("Conversation history must be a list of earlier questions.")
    if not limits["max_history_turns"]:
        return []
    selected, used = [], 0
    for turn in reversed(history[-limits["max_history_turns"]:]):
        if not isinstance(turn, dict):
            break
        question = turn.get("question")
        retrieval = turn.get("retrieval_question")
        if not isinstance(question, str) or not question.strip() or len(question) > limits["max_question_characters"]:
            break
        if retrieval is None:
            retrieval = question
        if not isinstance(retrieval, str) or not retrieval.strip() or len(retrieval) > limits["max_question_characters"]:
            break
        if _UNSAFE.search(question + retrieval):
            break
        size = len(question) + len(retrieval)
        if used + size > limits["max_history_characters"]:
            break
        selected.append({"question": question.strip(), "retrieval_question": retrieval.strip()})
        used += size
    return list(reversed(selected))


def _topics(text: str) -> set[str]:
    return {name for name, pattern in _TOPICS.items() if re.search(pattern, text, re.I)}


def _is_topic_fragment(question: str) -> bool:
    """A noun phrase identifies the subject but does not state what to ask."""
    return (bool(_topics(question)) and len(question.split()) <= 8
            and not _REQUEST_START.search(question) and not re.search(
                r"\b(what|which|who|how|when|where|why|can|could|would|should|do|does|"
                r"is|are|need|want)\b", question, re.I))


def _needs_context(question: str) -> bool:
    if _is_topic_fragment(question):
        return True
    # Naming a new object does not restate the earlier intent. "What about
    # eSIM?" can carry forward an appointment question about a physical SIM.
    if re.match(r"^(what|how) about\b", question, re.I):
        return True
    references = list(_REFERENCES.finditer(question))
    topics = _topics(question)
    for reference in references:
        word = reference.group().lower()
        # "this SIM" names the object; "replace this" still does not.
        if word in {"this", "that", "these", "those", "one"} and any(
            re.match(r"\s+" + pattern, question[reference.end():], re.I) for pattern in _TOPICS.values()
        ):
            continue
        # "Can I replace my SIM if it is damaged?" names its own referent.
        # A person pronoun or several possible objects still needs context.
        before = question[:reference.start()]
        prior_topics = _topics(before) - {"appointment", "identity", "authority"}
        if (word in {"it", "its"} and len(prior_topics) == 1
                and re.search(r"\b(if|because|when|after)\s*$", before, re.I)):
            continue
        return True
    if topics or re.search(r"\b[A-Z]{2,8}-\d{3,}\b", question, re.I):
        return False
    return bool(_ELLIPTICAL.search(question)) or len(question.split()) < 5


def _clarification(question: str, usage: dict | None = None) -> dict:
    if re.search(r"\breplac(?:e|ing)\b", question, re.I):
        text = "What would you like to replace, and what has happened to it?"
    elif re.search(r"\bbook\b", question, re.I):
        text = "What would you like to book, and which service is it for?"
    else:
        text = "Which item or service do you mean, and what would you like to know about it?"
    return {"question": question, "retrieval_question": None, "clarifying_question": text, "usage": usage}


def _has_competing_topics(history: list[dict]) -> bool:
    # Appointments/identity/account can accompany the main topic. Different
    # main objects (e.g. SIM and handset) remain ambiguous even in one turn.
    main_topics = set().union(*(_topics(turn["retrieval_question"]) for turn in history))
    main_topics -= {"appointment", "identity", "authority"}
    return len(main_topics) > 1


def _complete_pending_reference(question: str, previous: str, maximum: int) -> str | None:
    """Fill one missing object with an explicit noun supplied by the user.

    This narrow path avoids asking a model to join "Can I replace it?" and
    "A physical SIM". Preserve every other word; complex replies still use the
    validated resolver. Never infer an object from an assistant's answer.
    """
    noun = question.strip().rstrip(".?!").strip()
    without_article = re.sub(r"^(?:a|an|the|my|our)\s+", "", noun, flags=re.I)
    if not any(re.fullmatch(pattern, without_article, re.I) for pattern in _TOPICS.values()):
        return None
    references = list(_REFERENCES.finditer(previous))
    if len(references) != 1 or references[0].group().lower() not in {"it", "this", "that", "one"}:
        return None
    noun = re.sub(r"^(?:a|an|the|my|our)\b", lambda match: match.group().lower(), noun, flags=re.I)
    reference = references[0]
    rewritten = previous[:reference.start()] + noun + previous[reference.end():]
    if len(rewritten) > maximum or _needs_context(rewritten):
        return None
    return rewritten


def _schema(maximum: int, history_count: int) -> dict:
    return {"type": "object", "additionalProperties": False,
            "required": ["status", "retrieval_question", "history_turn"],
            "properties": {
                "status": {"type": "string", "enum": ["resolved", "clarify"]},
                "retrieval_question": {"type": ["string", "null"], "maxLength": maximum},
                "history_turn": {"type": ["integer", "null"], "minimum": 0, "maximum": history_count - 1},
            }}


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Repeated resolver field.")
        result[key] = value
    return result


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower()))


def _validated_rewrite(raw, question: str, history: list[dict], maximum: int) -> str | None:
    if not isinstance(raw, str) or len(raw) > maximum * 2 + 200:
        return None
    result = json.loads(raw, object_pairs_hook=_unique_fields)
    if not isinstance(result, dict) or set(result) != {"status", "retrieval_question", "history_turn"}:
        return None
    if result["status"] == "clarify":
        return None
    index, rewritten = result["history_turn"], result["retrieval_question"]
    if (result["status"] != "resolved" or type(index) is not int or not 0 <= index < len(history)
            or not isinstance(rewritten, str) or not 1 <= len(rewritten) <= maximum
            or _UNSAFE.search(rewritten) or "\n" in rewritten or "\r" in rewritten or not rewritten.rstrip().endswith("?")):
        return None
    prior = history[index]
    allowed = _words(question + " " + prior["question"] + " " + prior["retrieval_question"]) | _GRAMMAR
    words = _words(rewritten)
    # Vocabulary containment is deliberately conservative. Never import a new
    # policy fact or silently drop user terms such as 'not', 'lost' or 'stolen'.
    required = _words(question) - _GRAMMAR
    if _is_topic_fragment(question):
        # A reply such as "A physical SIM" completes the immediately preceding
        # unresolved request. Preserve that request's action and conditions.
        if index != len(history) - 1:
            return None
        required |= _words(prior["question"]) - _GRAMMAR
    if not words <= allowed or not required <= words:
        return None
    if _needs_context(rewritten):
        return None
    return rewritten.strip()


def resolve_question(question: str, history: list[dict], settings: dict) -> dict:
    """Return a standalone retrieval question OR a safe clarification, never both.

    History entries require only question/retrieval_question. The caller must
    clear history for New chat and retrieve fresh approved evidence after a
    successful resolution. A failure here must not trigger retrieval.
    """
    if not isinstance(settings, dict):
        raise ConversationError("Check the conversation settings.")
    limits = conversation_limits(settings)
    if not isinstance(question, str) or not question.strip():
        raise ConversationError("Please enter a question about the fictional retail policies.")
    if len(question) > limits["max_question_characters"]:
        raise ConversationError("Please shorten your question to fit the configured character limit.")
    question = question.strip()
    recent = _recent_questions(history, limits)
    if _UNSAFE.search(question):
        return _clarification(question)
    if not _needs_context(question):
        return {"question": question, "retrieval_question": question, "clarifying_question": None, "usage": None}
    if not recent:
        return _clarification(question)
    pending_reply = _is_topic_fragment(question) and history[-1].get("retrieval_question") is None
    if pending_reply:
        rewritten = _complete_pending_reference(question, recent[-1]["question"], limits["max_question_characters"])
        if rewritten is not None:
            return {"question": question, "retrieval_question": rewritten, "clarifying_question": None, "usage": None}
    if _has_competing_topics(recent) or (_is_topic_fragment(question) and not pending_reply):
        return _clarification(question)

    usage = None
    try:
        options = generation_options(settings)
        instructions = (PROJECT_ROOT / "prompts" / "conversation.md").read_text(encoding="utf-8")
        schema = _schema(limits["max_question_characters"], len(recent))
        messages = [
            {"role": "system", "content": instructions + "\nResponse schema:\n" + json.dumps(schema)},
            {"role": "user", "content": json.dumps({"previous_user_questions": recent, "current_question": question})},
        ]
        budget = input_budget(messages, options)
        model = inspect_model(options)
        response = request_local_json(options, "/api/chat", {
            "model": options["model"], "messages": messages, "format": schema,
            "stream": False, "think": model["think"], "keep_alive": "60s",
            "options": {key: options[key] for key in ("num_ctx", "num_predict", "temperature")},
        })
        if not isinstance(response, dict):
            return _clarification(question)
        message = response.get("message")
        if (response.get("model") != options["model"] or response.get("done") is not True
                or response.get("done_reason") != "stop" or not isinstance(message, dict)
                or message.get("role") != "assistant" or message.get("tool_calls")
                or (model["think"] is False and message.get("thinking"))):
            return _clarification(question)
        prompt_tokens, generated_tokens = response.get("prompt_eval_count"), response.get("eval_count")
        if (type(prompt_tokens) is not int or not 0 < prompt_tokens <= budget["input_token_allowance"]
                or type(generated_tokens) is not int or not 0 < generated_tokens < options["num_predict"]
                or prompt_tokens + generated_tokens > options["num_ctx"]):
            return _clarification(question)
        usage = {"prompt_tokens": prompt_tokens, "generated_tokens_including_thinking": generated_tokens}
        rewritten = _validated_rewrite(message.get("content"), question, recent, limits["max_question_characters"])
        if rewritten is not None:
            return {"question": question, "retrieval_question": rewritten, "clarifying_question": None, "usage": usage}
    except (ValueError, KeyError, TypeError, OSError):
        # No raw response, exception text, assistant content or thinking escapes.
        pass
    return _clarification(question, usage)
