import os

import requests
import streamlit as st
from dotenv import load_dotenv

from quiz_parser import parse_csv_quiz

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
# Local: set TELEGRAM_TOKEN in .env
# Streamlit Cloud: set it in App Settings → Secrets
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN") or st.secrets.get("TELEGRAM_TOKEN", "")

CHANNELS = {
    "🚂 Daily Railway Quiz": "-1003996251605",
    "📘 Test Sarthi":         "@testsarthi1234",
    "📗 Channel 3":           "@channel3username",
}

API_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ── Telegram helpers ──────────────────────────────────────────────────────────
def post_poll(chat_id: str, question: str, options: list, correct_option_id: int, explanation: str) -> dict:
    resp = requests.post(
        f"{API_BASE}/sendPoll",
        json={
            "chat_id":           chat_id,
            "question":          question[:300],
            "options":           [o[:100] for o in options],
            "type":              "quiz",
            "correct_option_id": correct_option_id,
            "explanation":       explanation[:200],
            "is_anonymous":      True,
        },
        timeout=15,
    )
    return resp.json()




# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Quiz Poll Creator",
    page_icon="🎯",
    layout="wide",
)

st.title("🎯 Quiz Poll Creator")
st.caption("Paste pipe-separated questions → preview → post directly to your Telegram channels.")

# ── Sidebar: channel picker ───────────────────────────────────────────────────
st.sidebar.header("📢 Channels")
selected_channels = st.sidebar.multiselect(
    "Post to:",
    options=list(CHANNELS.keys()),
    default=[list(CHANNELS.keys())[0]],
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**With answer:**\n```\nQuestion | A | B | C | D | 2\n```\n"
    "**Without answer** (tab-separated):\n```\nQuestion\tA\tB\tC\tD\n```\n"
    "One question per line."
)

# ── Main: paste area ──────────────────────────────────────────────────────────
col_input, col_preview = st.columns([1, 1], gap="large")

with col_input:
    st.subheader("📋 Paste Questions")
    raw_text = st.text_area(
        label="Questions",
        height=320,
        placeholder=(
            "With answer (pipe):\n"
            "India's capital? | Mumbai | Delhi | Chennai | Kolkata | 2\n\n"
            "Without answer (tab):\n"
            "पहली रेल किनके बीच चली?\tदिल्ली-आगरा\tमुंबई-ठाणे\tचेन्नई-बेंगलुरु\tकोलकाता-दिल्ली"
        ),
        label_visibility="collapsed",
    )

    parse_btn = st.button("🔍 Parse & Preview", use_container_width=True, type="secondary")
    post_btn  = st.button("🚀 Post to Telegram", use_container_width=True, type="primary")

# ── Parse ─────────────────────────────────────────────────────────────────────
if parse_btn or (post_btn and raw_text):
    parsed = parse_csv_quiz(raw_text)
    if parsed:
        st.session_state["questions"] = parsed
    else:
        st.session_state.pop("questions", None)
        with col_preview:
            st.error(
                "❌ Could not parse.\n\n"
                "**Pipe format:** `Question | A | B | C | D | 2`\n\n"
                "**Tab format:** `Question\\tA\\tB\\tC\\tD` (no answer column)"
            )

# ── Preview ───────────────────────────────────────────────────────────────────
questions = st.session_state.get("questions")

needs_answer = questions and any(not q.get("answer_given") for q in questions)

with col_preview:
    if questions:
        st.subheader(f"👁 Preview — {len(questions)} question(s)")
        if needs_answer:
            st.warning("⚠️ No answer column detected — select the correct answer for each question below.")
        for i, q in enumerate(questions, start=1):
            with st.expander(f"Q{i}. {q['question'][:90]}", expanded=True):
                if q.get("answer_given"):
                    for j, opt in enumerate(q["options"]):
                        icon = "✅" if j == q["correct_option_id"] else "◻"
                        st.markdown(f"{icon} **{chr(65+j)}.** {opt}")
                else:
                    st.radio(
                        "Correct answer:",
                        options=q["options"],
                        key=f"answer_{i}",
                        index=0,
                    )
    elif not parse_btn and not post_btn:
        st.info("Paste questions on the left and click **Parse & Preview**.")

# ── Post ──────────────────────────────────────────────────────────────────────
if post_btn:
    if not questions:
        st.warning("⚠️ No questions parsed yet. Fix the format and try again.")
    elif not selected_channels:
        st.warning("⚠️ Select at least one channel in the sidebar.")
    else:
        total_q = len(questions)

        # Apply user-selected answers for questions without an answer column
        final_questions = []
        for i, q in enumerate(questions, start=1):
            q_copy = dict(q)
            if not q.get("answer_given"):
                selected = st.session_state.get(f"answer_{i}", q["options"][0])
                idx = q["options"].index(selected) if selected in q["options"] else 0
                q_copy["correct_option_id"] = idx
                q_copy["explanation"] = f"✅ सही उत्तर: {q['options'][idx]}"
            final_questions.append(q_copy)

        for name in selected_channels:
            chat_id = CHANNELS[name]
            st.subheader(f"📢 {name}")

            slots = [st.empty() for _ in final_questions]

            for i, q in enumerate(final_questions, start=1):
                slots[i - 1].info(f"⏳ Q{i}/{total_q} — posting…")
                numbered = f"Q{i}/{total_q}. {q['question']}"
                result = post_poll(chat_id, numbered, q["options"], q["correct_option_id"], q["explanation"])
                if result.get("ok"):
                    slots[i - 1].success(f"✅ Q{i}/{total_q}. {q['question'][:70]}")
                else:
                    slots[i - 1].error(f"❌ Q{i}/{total_q}. {q['question'][:50]} — {result.get('description', 'unknown error')}")
