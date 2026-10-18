"""Run one fresh chat request in memory, keeping evidence separate from chat text."""

from copy import deepcopy
import json
import logging
from time import perf_counter

from pinecone import Pinecone, RetryConfig

from retail_copilot.answering import STATUS_MESSAGES, render_draft, revalidate_pack, validate_draft
from retail_copilot.context import build_context
from retail_copilot.conversation import (acknowledgement_reply, asks_about_own_action, conversation_limits,
                                       requests_execution, resolve_question)
from retail_copilot.documents import PROJECT_ROOT, load_settings
from retail_copilot.generate import generate_answer
from retail_copilot.pinecone_ingest import check_index, prepare_upload
from retail_copilot.plan_names import canonical_plan_names, display_plan_names, plan_aliases
from retail_copilot.policy_lookup import follow_policy_references
from retail_copilot.readiness import read_credential
from retail_copilot.retrieve import retrieval_options, retrieve_question
from retail_copilot.source_guidance import assemble_source_guidance


class ChatError(ValueError):
    """A safe explanation for the UI, never a provider error or previous answer."""


SERVICE_UNAVAILABLE = (
    "I can't access the policy guidance right now. Please try again. "
    "If this continues, contact copilot support."
)


def _natural_text(draft: dict, presentation: str = "model_draft", assembly: dict | None = None) -> str:
    """Use validated answer fields, never parse a rendered source appendix or reasoning."""
    if draft["status"] == "needs_clarification":
        return draft["clarifying_question"].strip()
    paragraphs = []
    if presentation == "source_passages" and draft["status"] == "insufficient_evidence" and draft["claims"]:
        # The model's coverage classification is unverified. Present the actual
        # guidance without inventing either missing evidence or completeness.
        paragraphs.append("Here is the available policy guidance. Please check with the authorised support channel if your situation is not covered.")
    elif STATUS_MESSAGES[draft["status"]]:
        paragraphs.append(STATUS_MESSAGES[draft["status"]])
    if presentation == "source_passages" and draft["claims"] and assembly:
        missing = assembly.get("referenced_policy_ids_without_passages", [])
        if missing:
            paragraphs.append("I don't have the referenced guidance for " + ", ".join(missing)
                              + " here, so I can't confirm those requirements. Please check with the policy owner.")
    paragraphs.extend(claim["text"].strip() for claim in draft["claims"])
    return "\n\n".join(paragraphs)


def _instructions(settings: dict) -> str:
    path = (PROJECT_ROOT / settings["answering"]["system_prompt_file"]).resolve()
    if not path.is_relative_to((PROJECT_ROOT / "prompts").resolve()) or path.suffix != ".md":
        raise ChatError(SERVICE_UNAVAILABLE)
    return path.read_text(encoding="utf-8")


def run_chat_turn(question: str, history: list[dict], settings: dict | None = None) -> dict:
    """Resolve the question, retrieve approved evidence and return a validated draft.

    Ordinary questions and answers are not saved to files. Diagnostics belong to the
    current in-memory turn; prior assistant replies are never retrieval evidence.
    Source validation establishes provenance, not semantic claim support.
    """
    started = perf_counter()
    stage = "question"
    try:
        if not isinstance(question, str) or not question.strip():
            raise ChatError("Please enter a question about the retail policies.")
        if not isinstance(history, list) or any(not isinstance(turn, dict) for turn in history):
            raise ChatError("The conversation could not be read. Start a new chat and try again.")
        question = question.strip()
        stage = "configuration"
        settings = load_settings() if settings is None else deepcopy(settings)
        limits = conversation_limits(settings)
        stage = "question"
        if len(question) > limits["max_question_characters"]:
            raise ChatError("Please shorten your message and try again.")
        acknowledgement = acknowledgement_reply(question)
        if acknowledgement is not None:
            return {
                "question": question, "text": acknowledgement,
                "status": "acknowledgement", "retrieval_question": None,
                "diagnostics": {
                    "original_question": question, "normalized_question": question,
                    "plan_aliases_applied": False, "resolution": None, "retrieval": None,
                    "context": None, "generation": None, "citations": [],
                    "model_call_made": False, "service_calls_made": 0,
                    "total_seconds": perf_counter() - started,
                },
            }
        stage = "configuration"
        aliases = plan_aliases(settings)
        stage = "question"
        normalized_question = canonical_plan_names(question, aliases)
        # Acknowledgements carry no policy topic. First bound the raw window;
        # never reach farther back to replace skipped social or failed turns.
        recent = history[-limits["max_history_turns"]:] if limits["max_history_turns"] else []
        usable = []
        for turn in reversed(recent):
            if turn.get("status") == "error":
                break
            if turn.get("status") != "acknowledgement":
                usable.append(turn)
        usable.reverse()
        # Defence in depth: no assistant text, diagnostics, or retrieved passages go
        # into question resolution, even if a future caller passes entire turns.
        user_history = [
            {key: canonical_plan_names(turn[key], aliases) if isinstance(turn.get(key), str) else turn.get(key)
             for key in ("question", "retrieval_question")}
            for turn in usable
        ]
        resolution = resolve_question(normalized_question, user_history, settings)
        question_names = {"original_question": question, "normalized_question": normalized_question,
                          "plan_aliases_applied": normalized_question != question}
        query = resolution["retrieval_question"]
        clarification = resolution["clarifying_question"]
        if clarification is not None:
            if query is not None or not isinstance(clarification, str) or not clarification.strip():
                raise ChatError("I couldn't understand that question. Please name the policy or item you mean.")
            return {
                "question": question, "text": display_plan_names(clarification.strip(), aliases),
                "status": "needs_clarification", "retrieval_question": None,
                "diagnostics": {**question_names, "resolution": deepcopy(resolution), "retrieval": None,
                                "context": None, "generation": None, "citations": [],
                                "total_seconds": perf_counter() - started},
            }
        if not isinstance(query, str) or not query.strip():
            raise ChatError("I couldn't understand that question. Please name the policy or item you mean.")

        stage = "configuration"
        _, timeout = retrieval_options(settings)
        instructions = _instructions(settings)
        # This checks the existing local corpus only. It never uploads anything.
        prepared = prepare_upload(PROJECT_ROOT, settings)
        key = read_credential("PINECONE_API_KEY", PROJECT_ROOT)
        if not key:
            raise ChatError(SERVICE_UNAVAILABLE)

        stage = "retrieval"
        logging.getLogger("pinecone").setLevel(logging.CRITICAL)
        with Pinecone(api_key=key, timeout=timeout, retry_config=RetryConfig(max_retries=0)) as client:
            info = client.indexes.describe(settings["retrieval"]["index_name"])
            check_index(info, settings, prepared)
            with client.index(host=info.host) as index:
                retrieved = retrieve_question(index, query, prepared, settings)
                retrieved = follow_policy_references(index, retrieved, prepared, settings)
        retrieved["user_question"] = question
        retrieved["query_rewritten"] = query != question

        stage = "evidence"
        pack = revalidate_pack(build_context(retrieved, prepared, settings), prepared, settings)
        stage = "generation"
        generated = generate_answer(pack, instructions, settings)
        # Recheck the final structured draft at the UI boundary. The existing
        # renderer constructs citations from the registry, not from model prose.
        raw = json.dumps(generated["draft"], ensure_ascii=False, allow_nan=False)
        draft = validate_draft(raw, pack, settings)
        model_draft = deepcopy(draft)
        presentation = settings["answering"].get("presentation", "model_draft")
        if presentation not in ("model_draft", "source_passages"):
            raise ChatError(SERVICE_UNAVAILABLE)
        assembly = None
        display_settings = deepcopy(settings)
        if presentation == "source_passages":
            assembled = assemble_source_guidance(draft, pack, settings)
            draft, assembly = assembled["draft"], assembled["trace"]
            display_settings["answering"]["max_claims"] = settings["context"]["max_sources"]
        execution_requested = requests_execution(normalized_question) or requests_execution(query)
        own_action_question = asks_about_own_action(query)
        guidance_status_changed = (presentation == "source_passages" and not execution_requested
                                   and own_action_question and draft["status"] == "action_not_supported")
        if guidance_status_changed:
            # "Can I book?" asks about the user's options. Do not call it an
            # execution request, or promote it to a verified complete answer.
            draft["status"] = "insufficient_evidence"
        # Application capabilities do not depend on the model's chosen status.
        # This capability boundary never supplies missing policy information.
        if execution_requested:
            draft["status"] = "action_not_supported"
            draft["clarifying_question"] = None
        raw = json.dumps(draft, ensure_ascii=False, allow_nan=False)
        sourced_answer = render_draft(raw, pack, display_settings)
        generation_trace = {key: deepcopy(generated.get(key)) for key in (
            "model", "model_digest", "model_call_made", "answer_generated", "usage",
            "generation_seconds", "provider_duration_seconds", "external_request_charge_usd",
            "local_hardware_cost_usd", "claim_review_status", "context_sha256", "instructions_sha256",
        )}
        generation_trace.update({"draft": draft, "model_draft": model_draft,
                                 "presentation": presentation, "source_assembly": assembly,
                                 "model_coverage_status_verified": False,
                                 "guidance_guard": {"asks_about_own_action": own_action_question,
                                                    "status_changed": guidance_status_changed},
                                 "capability_guard": {"execution_requested": execution_requested,
                                                      "status_changed": execution_requested and draft["status"] != model_draft["status"]},
                                 "source_ids_valid": sourced_answer["source_ids_valid"],
                                 "claim_support_checked": sourced_answer["claim_support_checked"],
                                 "action_claims_checked": sourced_answer["action_claims_checked"]})
        return {
            "question": question, "text": display_plan_names(_natural_text(draft, presentation, assembly), aliases), "status": draft["status"],
            "retrieval_question": query,
            "diagnostics": {**question_names, "resolution": deepcopy(resolution), "retrieval": retrieved,
                            "context": pack, "generation": generation_trace,
                            "citations": sourced_answer["citations"],
                            "total_seconds": perf_counter() - started},
        }
    except ChatError:
        raise
    except Exception:
        messages = {
            "question": "I couldn't understand that question. Please name the policy or item you mean and try again.",
            "configuration": SERVICE_UNAVAILABLE,
            "retrieval": "I couldn't check the policy guidance right now. Please try again. If this continues, contact copilot support.",
            "evidence": "I couldn't verify enough guidance to answer reliably. Please consult the policy owner or your support channel.",
            "generation": "I couldn't complete this reply. Please try again. If this continues, contact copilot support.",
        }
        raise ChatError(messages[stage]) from None
