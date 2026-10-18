"""Natural chat over the fictional policy library; evidence stays behind the scenes."""

import streamlit as st

from retail_copilot.documents import PROJECT_ROOT, load_settings
from retail_copilot.pipeline import ChatError, run_chat_turn


STARTERS = (
    ("starter_sim", "SIM replacement", "Do I need an appointment for a physical SIM replacement?", ":material/sim_card:"),
    ("starter_authority", "Account authority", "Can a secondary account contact replace a SIM?", ":material/group:"),
    ("starter_roaming", "International roaming", "What should I check before using international roaming?", ":material/public:"),
)
REQUEST_FAILED = (
    "I couldn't complete this reply. Please try again. "
    "If this continues, contact copilot support."
)


def new_chat() -> None:
    """Clear this browser session's conversation, including private evidence records."""
    st.session_state.chat_turns = []
    st.session_state.chat_input = ""


def show_message(role: str, text: str, index: int) -> None:
    # Native plain text prevents user/model Markdown from loading images or HTML.
    with st.container(key=f"{role}_{index}"):
        avatar = ":material/person:" if role == "user" else ":material/forum:"
        with st.chat_message(role, avatar=avatar):
            st.text(text, width="stretch", wrap=True)


def main() -> None:
    st.set_page_config(
        page_title="Retail Copilot", page_icon=":material/forum:",
        layout="centered", initial_sidebar_state="collapsed",
    )
    st.html(PROJECT_ROOT / "assets" / "chat.css")
    try:
        settings = load_settings()
        limits = settings["conversation"]
        maximum = limits["max_question_characters"]
        window = limits["max_history_turns"]
        display_limit = limits["max_display_turns"]
        if (type(maximum) is not int or not 1 <= maximum <= 4000
                or type(window) is not int or not 1 <= window <= 10
                or type(display_limit) is not int or not window <= display_limit <= 100):
            raise ValueError("Invalid chat limits")
    except (ValueError, KeyError, TypeError, OSError):
        st.error("The chat is unavailable right now. Please try again later or contact copilot support.")
        st.stop()

    if "chat_turns" not in st.session_state:
        st.session_state.chat_turns = []

    starter = None
    with st.container(key="copilot"):
        with st.container(key="brand"):
            st.markdown("# Retail Copilot")
            st.caption("Your policy companion")
        with st.container(horizontal=True, vertical_alignment="center", key="chat_navigation"):
            st.button("New chat", key="new_chat", icon=":material/edit_square:", on_click=new_chat)
            st.badge("Policy guidance", color="gray")
        if not st.session_state.chat_turns:
            with st.container(key="welcome"):
                st.markdown("## What would you like to check?")
                st.write("Ask about a policy, then keep the conversation going.")
            with st.container(key="starters"):
                for column, (key, topic, question, icon) in zip(st.columns(3), STARTERS, strict=True):
                    with column:
                        if st.button(topic, key=key, icon=icon, width="stretch"):
                            starter = question
                        st.caption(question)

        with st.container(key="chat_thread"):
            for index, turn in enumerate(st.session_state.chat_turns):
                show_message("user", turn["question"], index)
                show_message("assistant", turn["text"], index)

    typed = st.chat_input("Ask a question or follow up…", key="chat_input", max_chars=maximum)
    question = starter or typed
    if not question or not question.strip():
        return
    question = question.strip()
    if len(question) > maximum:
        st.warning(f"Please keep your question within {maximum} characters.")
        return

    # Use a small window of user requests, never earlier assistant answers as evidence.
    history = []
    for turn in st.session_state.chat_turns[-window:]:
        if turn["status"] == "error":
            # A failed new topic is a boundary, not permission to revive an old one.
            history.clear()
        elif turn["status"] != "acknowledgement":
            history.append({key: turn.get(key) for key in ("question", "retrieval_question", "status")})
    with st.container(key="current_request"):
        show_message("user", question, len(st.session_state.chat_turns))
        with st.chat_message("assistant", avatar=":material/forum:"):
            with st.spinner("Let me check that for you…", show_time=True):
                try:
                    result = run_chat_turn(question, history, settings)
                except ChatError as error:
                    # ChatError contains only deliberately authored safe explanations.
                    result = {"question": question, "text": str(error), "status": "error",
                              "retrieval_question": None, "diagnostics": {}}
                except Exception:
                    # Provider exceptions can contain credentials or raw response bodies.
                    result = {"question": question, "text": REQUEST_FAILED, "status": "error",
                              "retrieval_question": None, "diagnostics": {}}
    st.session_state.chat_turns.append(result)
    st.session_state.chat_turns = st.session_state.chat_turns[-display_limit:]
    st.rerun()


main()
