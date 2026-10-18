"""Preview or generate one local answer from saved, revalidated policy evidence."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from time import perf_counter

from retail_copilot.answering import (AnsweringError, STATUS_MESSAGES, answer_limits,
                                     build_prompt, render_draft, revalidate_pack, validate_draft)
from retail_copilot.context import ContextError
from retail_copilot.documents import PROJECT_ROOT, load_settings
from retail_copilot.ollama_embeddings import LocalOllamaError, installed_model_digest, request_local_json
from retail_copilot.pinecone_ingest import IngestionError, prepare_upload
from retail_copilot.prepare_chunks import save_chunk_export
from retail_copilot.prepare_embeddings import generated_json_path


class GenerationError(ValueError):
    """A safe explanation of why no current answer was accepted."""


def generation_options(settings: dict) -> dict:
    options = deepcopy(settings["generation"])
    if (options["provider"] != "ollama" or not isinstance(options["model"], str)
            or not options["model"].strip() or "cloud" in options["model"].lower()):
        raise GenerationError("Choose an installed local Ollama answering model.")
    for key, lower, upper in (("num_ctx", 4096, 65536), ("num_predict", 128, 8192),
                              ("template_reserve_tokens", 256, 8192)):
        if type(options[key]) is not int or not lower <= options[key] <= upper:
            raise GenerationError("Check the whole-number context, output and template limits.")
    temperature = options["temperature"]
    if type(temperature) not in (int, float) or not math.isfinite(temperature) or not 0 <= temperature <= 1:
        raise GenerationError("Choose a generation temperature from zero to one.")
    if "thinking_when_metadata_missing" in options and type(options["thinking_when_metadata_missing"]) is not bool:
        raise GenerationError("The explicitly reviewed thinking setting must be true or false.")
    return options


def response_schema(pack: dict, settings: dict) -> dict:
    limits = answer_limits(settings)
    return {
        "type": "object", "additionalProperties": False,
        "required": ["status", "claims", "clarifying_question"],
        "properties": {
            "status": {"type": "string", "enum": list(STATUS_MESSAGES)},
            "claims": {"type": "array", "maxItems": limits["max_claims"], "items": {
                "type": "object", "additionalProperties": False, "required": ["text", "source_ids"],
                "properties": {
                    "text": {"type": "string", "minLength": 1, "maxLength": limits["max_claim_characters"]},
                    "source_ids": {"type": "array", "minItems": 1, "uniqueItems": True,
                                   "items": {"type": "string", "enum": list(pack["source_registry"])}}
                }}},
            "clarifying_question": {"type": ["string", "null"], "maxLength": limits["max_claim_characters"]},
        },
    }


def input_budget(messages: list, options: dict) -> dict:
    # A conservative byte-based allowance for the checked byte-BPE model, NOT a token measurement.
    message_bytes = sum(len(message["content"].encode("utf-8")) for message in messages)
    allowance = message_bytes + options["template_reserve_tokens"]
    if allowance + options["num_predict"] > options["num_ctx"]:
        raise GenerationError("The whole prompt and output allowance do not fit. Review the evidence or limits; no passage was cut.")
    return {"message_utf8_bytes": message_bytes, "input_token_allowance": allowance,
            "method": "conservative_utf8_bytes_plus_template_reserve", "exact_input_tokens": None}


def inspect_model(options: dict) -> dict:
    digest = installed_model_digest(options)
    shown = request_local_json(options, "/api/show", {"model": options["model"]})
    capabilities = shown.get("capabilities")
    info, thinking = shown.get("model_info"), shown.get("thinking")
    if (not isinstance(capabilities, list) or not isinstance(info, dict)
            or (thinking is not None and (not isinstance(thinking, dict) or not isinstance(thinking.get("values"), list)))
            or (thinking is None and "thinking" in capabilities
                and type(options.get("thinking_when_metadata_missing")) is not bool)):
        raise GenerationError("Ollama returned incomplete model capability information. Review the installed model.")
    if shown.get("remote_host") or shown.get("remote_model") or "completion" not in capabilities:
        raise GenerationError("The installed model must support local text completion.")
    maximum = info.get(str(info.get("general.architecture")) + ".context_length")
    if type(maximum) is not int or maximum < options["num_ctx"]:
        raise GenerationError("The configured context exceeds the installed model's reported limit.")
    template = shown.get("template")
    if (info.get("tokenizer.ggml.model") != "gpt2" or not isinstance(template, str)
            or len(template.encode("utf-8")) + 256 > options["template_reserve_tokens"]):
        raise GenerationError("Review the tokenizer and template allowance before using this model.")
    # This small lesson supports boolean thinking controls only; never silently guess a control.
    values = thinking["values"] if thinking is not None else [options.get("thinking_when_metadata_missing", False)]
    if any(value is False for value in values):
        think = False
    elif any(value is True for value in values):
        think = True
    else:
        raise GenerationError("Review this model's thinking controls before generating an answer.")
    return {"digest": digest, "maximum_context_tokens": maximum, "think": think,
            "thinking_control_source": "model_metadata" if thinking is not None else "reviewed_configuration_or_non_thinking_capability",
            "tokenizer": "gpt2", "template_sha256": hashlib.sha256(template.encode()).hexdigest()}


def generate_answer(pack: dict, instructions: str, settings: dict, *, keep_alive_seconds: int = 0) -> dict:
    """Caller must revalidate the pack. Persist selected final fields, never the raw response."""
    options = generation_options(settings)
    if type(keep_alive_seconds) is not int or not 0 <= keep_alive_seconds <= 600:
        raise GenerationError("Keep the local model alive for zero to 600 seconds only.")
    preview = build_prompt(pack, instructions, settings)
    result = {
        "schema_version": 1, "artifact_type": "generation_result",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "question": pack["question"], "as_of_date": pack["as_of_date"],
        "context_sha256": preview["context_sha256"], "instructions_sha256": preview["instructions_sha256"],
        "context_text": pack["context_text"], "source_registry": deepcopy(pack["source_registry"]),
        "messages": preview["messages"], "provider": "ollama", "model": options["model"],
        "model_call_made": False, "answer_generated": False,
        "external_request_charge_usd": "0", "local_hardware_cost_usd": None,
        "claim_review_status": "pending", "model_digest": None, "usage": None,
    }
    if preview["empty_context_fallback"] is not None:
        raw = json.dumps(preview["empty_context_fallback"])
        result.update({"draft": validate_draft(raw, pack, settings), "answer": render_draft(raw, pack, settings),
                       "claim_review_status": "no_model_claims", "generation_seconds": 0})
        return result
    budget = input_budget(preview["messages"], options)
    model = inspect_model(options)
    schema = response_schema(pack, settings)
    payload = {"model": options["model"], "messages": preview["messages"], "format": schema,
               "stream": False, "think": model["think"], "keep_alive": f"{keep_alive_seconds}s",
               "options": {key: options[key] for key in ("num_ctx", "num_predict", "temperature")}}
    started = perf_counter()
    response = request_local_json(options, "/api/chat", payload)
    elapsed = perf_counter() - started
    message = response.get("message")
    if (response.get("model") != options["model"] or response.get("done") is not True
            or response.get("done_reason") != "stop" or not isinstance(message, dict)
            or message.get("role") != "assistant" or message.get("tool_calls")):
        raise GenerationError("The local response was incomplete, requested a tool, or used an unexpected model. No draft was accepted.")
    if model["think"] is False and message.get("thinking"):
        raise GenerationError("The model returned unexpected thinking output with thinking disabled. No draft was accepted.")
    prompt_tokens, output_tokens, duration = (response.get(key) for key in
                                            ("prompt_eval_count", "eval_count", "total_duration"))
    if (type(prompt_tokens) is not int or not 0 < prompt_tokens <= budget["input_token_allowance"]
            or type(output_tokens) is not int or not 0 < output_tokens < options["num_predict"]
            or prompt_tokens + output_tokens > options["num_ctx"]
            or type(duration) is not int or duration < 0):
        raise GenerationError("Reported token usage or timing is invalid or reaches a configured limit. No draft was accepted.")
    # Never copy message.thinking, tool calls, or provider error bodies into logs/artifacts.
    raw = message.get("content")
    draft = validate_draft(raw, pack, settings)
    rendered = render_draft(raw, pack, settings)
    result.update({"model_call_made": True, "answer_generated": True, "model_digest": model["digest"],
                   "model_details": model, "options": payload["options"], "response_schema": schema,
                   "keep_alive_seconds": keep_alive_seconds,
                   "input_budget": budget, "draft": draft, "answer": rendered,
                   "usage": {"prompt_tokens": prompt_tokens, "generated_tokens_including_thinking": output_tokens},
                   "generation_seconds": elapsed, "provider_duration_seconds": duration / 1_000_000_000,
                   "done_reason": "stop"})
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Request one answer from local Ollama; otherwise preview without calls.")
    parser.add_argument("--output", help="A new JSON file inside data/processed; existing files are never overwritten.")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
        options = generation_options(settings)
        input_path = generated_json_path(PROJECT_ROOT, settings["answering"]["input_file"])
        output = generated_json_path(PROJECT_ROOT, args.output or options["output_file"])
        protected = {input_path}
        for section, values in settings.items():
            if section != "generation" and isinstance(values, dict):
                protected.update(generated_json_path(PROJECT_ROOT, value) for key, value in values.items()
                                 if key in ("output_file", "report_file", "baseline_output_file"))
        if output in protected or (args.run and output.exists()):
            raise GenerationError("Choose a new output file separate from existing evidence, answers and reports.")
        prompt_path = (PROJECT_ROOT / settings["answering"]["system_prompt_file"]).resolve()
        if not prompt_path.is_relative_to((PROJECT_ROOT / "prompts").resolve()) or prompt_path.suffix != ".md":
            raise GenerationError("Keep answering instructions in a Markdown file inside prompts/.")
        instructions = prompt_path.read_text(encoding="utf-8")
        saved = json.loads(input_path.read_text(encoding="utf-8"))
        pack = revalidate_pack(saved, prepare_upload(PROJECT_ROOT, settings), settings)
        preview = build_prompt(pack, instructions, settings)
        if preview["messages"]:
            input_budget(preview["messages"], options)
        if not args.run:
            print("Local answer: PREVIEW ONLY")
            print(f"Question: {pack['question']}")
            print(f"Configured model: {options['model']}. Sources: {len(pack['source_registry'])}.")
            print("No calls or result file. Use --run for one local draft; model availability is checked then.")
            return 0
        print("Generating one local draft from saved evidence. No new Pinecone or OpenAI request.", flush=True)
        result = generate_answer(pack, instructions, settings)
        result["source_context_file"] = input_path.relative_to(PROJECT_ROOT).as_posix()
        save_chunk_export(result, output)
        print("\nDRAFT FOR REVIEW: source IDs checked; claim support is not automatically verified.\n")
        print(result["answer"]["text"])
        if result["usage"]:
            print(f"\nInput tokens: {result['usage']['prompt_tokens']}; generated tokens (including internal thinking): {result['usage']['generated_tokens_including_thinking']}.")
            print(f"Generation time: {result['generation_seconds']:.1f} seconds.")
        print(f"Saved: {output.relative_to(PROJECT_ROOT).as_posix()}")
        return 0
    except (GenerationError, AnsweringError, ContextError, IngestionError, LocalOllamaError) as error:
        print(f"Generation stopped: {error}")
    except (ValueError, KeyError, TypeError, OSError):
        print("Generation stopped: check local Ollama availability, model controls, saved evidence and settings. Provider details were not logged.")
    print("No current answer was accepted or saved. Existing reports were preserved; a failed local call may still have used computing time.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
