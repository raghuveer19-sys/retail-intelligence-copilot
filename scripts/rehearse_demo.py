"""Preview or rehearse real chat turns with Streamlit AppTest, without fake answers."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from time import perf_counter
from unittest.mock import patch

from retail_copilot.documents import load_settings
from retail_copilot.evaluate import configuration, fingerprint
from retail_copilot.evaluate_chat import METRICS, measured_usage, output_directory, write_new


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = "data/processed/demo-rehearsal-2026-10-18"
QUESTIONS = (
    "Do I need an appointment for a physical SIM replacement?",
    "Can I book one anyway?",
    "OK thanks",
    "Can I replace it?",
    "A physical SIM",
    "Waive my outstanding bill now.",
)


def input_hashes(settings: dict) -> dict[str, str]:
    paths = [PROJECT_ROOT / "app.py", Path(__file__).resolve(),
             PROJECT_ROOT / "config/settings.toml", PROJECT_ROOT / ".streamlit/config.toml",
             PROJECT_ROOT / "assets/chat.css", PROJECT_ROOT / "prompts/conversation.md",
             PROJECT_ROOT / settings["answering"]["system_prompt_file"]]
    paths.extend(sorted((PROJECT_ROOT / "src/retail_copilot").glob("*.py")))
    if any(not path.resolve().is_relative_to(PROJECT_ROOT) for path in paths):
        raise ValueError("Rehearsal inputs must remain within the project.")
    return {path.relative_to(PROJECT_ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def response_route_checks(result: dict, required_status: str | None) -> dict[str, bool]:
    """Check routing/payload only; a model status does not prove semantic correctness."""
    if required_status is not None:
        return {"required_response_boundary": result.get("status") == required_status}
    generation = (result.get("diagnostics") or {}).get("generation") or {}
    claims = (generation.get("draft") or {}).get("claims")
    return {"guidance_returned_with_policy_claims": (
        result.get("status") in ("supported", "insufficient_evidence")
        and isinstance(claims, list) and bool(claims)
    )}


def rehearse(output: Path) -> int:
    # Import AppTest only for an explicitly requested live rehearsal.
    from streamlit.testing.v1 import AppTest
    from retail_copilot.pipeline import run_chat_turn

    settings = load_settings()
    hashes = input_hashes(settings)
    manifest = {"schema_version": 1, "artifact_type": "live_app_rehearsal_manifest",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "entrypoint": "app.py -> retail_copilot.pipeline.run_chat_turn",
                "configuration": configuration(settings), "input_file_sha256": hashes,
                "questions": list(QUESTIONS), "fake_pipeline_responses": False,
                "history_policy": "actual_app_state_with_explicit_new_chat_boundaries",
                "scope": "Real services through AppTest; not browser rendering or independent semantic review."}
    output.mkdir(parents=False, exist_ok=True)
    write_new(output / "manifest.json", manifest)
    records, lifecycle = [], []

    # wraps records invocations while still calling the real pipeline unchanged.
    with patch("retail_copilot.pipeline.run_chat_turn", wraps=run_chat_turn) as calls:
        app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=900).run()
        if app.exception:
            raise RuntimeError("The interface could not initialize.")
        lifecycle.append({"check": "welcome_has_no_pipeline_calls", "passed": calls.call_count == 0})

        def submit(number: int, required_status: str | None, expected_turns: int) -> None:
            question = QUESTIONS[number - 1]
            print(f"Turn {number}: running the real chat...", flush=True)
            before = calls.call_count
            started = perf_counter()
            app.chat_input(key="chat_input").set_value(question).run()
            elapsed = perf_counter() - started
            if app.exception:
                raise RuntimeError("The interface did not finish this turn.")
            turns = deepcopy(app.session_state["chat_turns"])
            if not turns or calls.call_count != before + 1:
                raise RuntimeError("The interface did not record exactly one current pipeline call.")
            result = turns[-1]
            call = calls.call_args
            history = [{key: item.get(key) for key in ("question", "retrieval_question", "status")}
                       for item in call.args[1]]
            actual_text = "\n".join(element.value for element in app.chat_message[-1].get("text"))
            diagnostics = result.get("diagnostics", {})
            checks = {**response_route_checks(result, required_status),
                      "question_preserved": result.get("question") == question,
                      "expected_visible_turn_count": len(turns) == expected_turns,
                      "all_messages_visible": len(app.chat_message) == 2 * len(turns),
                      "display_matches_saved_answer": actual_text == result.get("text"),
                      "no_source_expanders": not bool(app.get("expander")),
                      "history_excludes_assistant_text": all(set(item) <= {"question", "retrieval_question", "status"} for item in call.args[1])}
            if number in (3, 4):
                checks["no_retrieval_or_generation"] = diagnostics.get("retrieval") is None and diagnostics.get("generation") is None
            else:
                checks["fresh_retrieval_returned"] = isinstance(diagnostics.get("retrieval"), dict)
                checks["retrieval_uses_resolved_question"] = (diagnostics.get("retrieval") or {}).get("question") == result.get("retrieval_question")
                checks["context_uses_resolved_question"] = (diagnostics.get("context") or {}).get("question") == result.get("retrieval_question")
            if number == 2:
                query = result.get("retrieval_question") or ""
                checks["appointment_followup_resolved"] = "appointment" in query.lower() and "sim" in query.lower()
                checks["prior_question_in_history"] = any(item["question"] == QUESTIONS[0] for item in history)
            if number == 5:
                query = result.get("retrieval_question") or ""
                checks["replacement_intent_preserved"] = bool(re.search(r"\breplac(?:e|ement|ing)\b", query, re.I) and re.search(r"\bsim\b", query, re.I))
                checks["clarification_in_history"] = any(item["question"] == QUESTIONS[3] for item in history)
            usage = ({**{name: None for name in METRICS}, "elapsed_seconds": elapsed}
                     if result.get("status") == "error" else measured_usage(result, elapsed))
            record = {"schema_version": 1, "artifact_type": "live_app_rehearsal_turn", "turn_number": number,
                      "question": question, "actual_input_history": history,
                      "result": result, "result_sha256": fingerprint(result),
                      "displayed_answer": actual_text, "checks": checks, "usage": usage,
                      "semantic_review": "pending; inspect displayed guidance against actual supplied evidence"}
            write_new(output / f"turn-{number:02d}.json", record)
            records.append(record)
            print(f"Turn {number}: {result.get('status')}; behavior checks {'passed' if all(checks.values()) else 'need review'}.", flush=True)

        def reset_chat(label: str) -> None:
            before = calls.call_count
            app.button(key="new_chat").click().run()
            if app.exception:
                raise RuntimeError("The interface did not finish New chat.")
            lifecycle.append({"check": label, "passed": calls.call_count == before
                              and app.session_state["chat_turns"] == [] and len(app.chat_message) == 0})

        # Guidance may be qualified. Review relevance, completeness and the
        # model's uncertainty separately from these lifecycle/routing checks.
        submit(1, None, 1)
        submit(2, None, 2)
        submit(3, "acknowledgement", 3)
        before, saved = calls.call_count, deepcopy(app.session_state["chat_turns"])
        app.run()
        lifecycle.append({"check": "plain_rerun_retains_history_without_pipeline_call",
                          "passed": not app.exception and calls.call_count == before
                          and app.session_state["chat_turns"] == saved and len(app.chat_message) == 6})
        reset_chat("new_chat_clears_prior_conversation_without_pipeline_call")
        submit(4, "needs_clarification", 1)
        submit(5, None, 2)
        reset_chat("second_new_chat_clears_prior_conversation_without_pipeline_call")
        submit(6, "action_not_supported", 1)
        call_count = calls.call_count

    lifecycle.append({"check": "code_and_configuration_unchanged_during_run", "passed": input_hashes(settings) == hashes})
    summary = {"schema_version": 1, "artifact_type": "live_app_rehearsal_summary",
               "completed_turns": len(records), "pipeline_calls": call_count,
               "turn_behavior_checks_passed": sum(all(record["checks"].values()) for record in records),
               "lifecycle_checks": lifecycle, "semantic_review": "pending",
               "browser_rendering_verified": False,
               "usage": {}}
    for metric in METRICS:
        known = [record["usage"][metric] for record in records if record["usage"][metric] is not None]
        unknown = [record["turn_number"] for record in records if record["usage"][metric] is None]
        subtotal = sum(known) if known else None
        summary["usage"][metric] = {"reported_subtotal": subtotal, "complete_total": subtotal if not unknown else None,
                                    "unknown_turn_numbers": unknown}
    passed = all(all(record["checks"].values()) for record in records) and all(row["passed"] for row in lifecycle)
    summary["automated_behavior_checks_passed"] = passed
    write_new(output / "summary.json", summary)
    print(f"Saved six actual turns and lifecycle checks to {output.relative_to(PROJECT_ROOT).as_posix()}. Semantic review remains separate.")
    return 0 if passed else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Make real local-model/Pinecone requests through the app and save this rehearsal.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT, help="New empty direct child of data/processed; never overwritten or resumed.")
    args = parser.parse_args(argv)
    try:
        output = output_directory(PROJECT_ROOT, args.output_dir)
        if not args.run:
            print("Demo rehearsal: PREVIEW ONLY. No service requests, AppTest session or output files.")
            for number, question in enumerate(QUESTIONS, 1):
                print(f"{number}: {question}")
            print("New chat precedes turns 4 and 6; ordinary rerun follows turn 3.")
            print("Four turns can use retrieval/generation. Real answers need separate semantic review.")
            print(f"Output: {output.relative_to(PROJECT_ROOT).as_posix()}. Use --run for live execution.")
            return 0
        return rehearse(output)
    except Exception:
        # Do not persist provider bodies, framework exceptions, credentials or internal reasoning.
        if args.run and "output" in locals() and output.is_dir() and not (output / "failure.json").exists():
            try:
                write_new(output / "failure.json", {"artifact_type": "live_app_rehearsal_failure",
                          "message": "The rehearsal did not complete. Existing turn records were preserved; failed-call usage is unknown."})
            except OSError:
                pass
        print("Rehearsal could not complete. Check the local inputs/output directory; no successful full run is claimed. Existing results were preserved.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
