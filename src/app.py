import datetime

import streamlit as st
from agents.orchestrator import run_turn, submit_feedback


AVATARS = {"user": ":material/account_circle:", "assistant": ":material/explore:"}

_TYPE_BADGES = {
    "career": ("Career", "blue"),
    "major": ("Major", "green"),
    "college_pathway": ("College", "orange"),
    "college": ("College", "orange"),
}


def _reset_conversation() -> None:
    st.session_state.messages = []


def _format_timestamp(ts) -> str:
    if not isinstance(ts, datetime.datetime):
        return ""
    return ts.strftime("%I:%M %p").lstrip("0")


def _render_recommendations(recommendations: list[dict]) -> None:
    """One clean 'Recommended paths' section - not a grid of separate cards per career."""
    if not recommendations:
        return

    with st.container(border=True):
        st.markdown("#### :material/route: Recommended paths")

        for i, rec in enumerate(recommendations):
            if i > 0:
                st.divider()

            title = rec.get("title", "")
            rec_type = (rec.get("type") or "").strip().lower()
            badge_label, badge_color = _TYPE_BADGES.get(rec_type, (rec_type.title() or "Option", "gray"))

            header_col, badge_col = st.columns([4, 1], vertical_alignment="center")
            with header_col:
                st.markdown(f"**{title}**")
            with badge_col:
                st.badge(badge_label, color=badge_color)

            why_it_fits = rec.get("why_it_fits", "")
            if why_it_fits:
                st.markdown(f"- **Why it fits:** {why_it_fits}")

            why_exciting = rec.get("why_exciting", "")
            if why_exciting:
                st.markdown(f"- **Why exciting:** {why_exciting}")

            future_outlook = rec.get("future_outlook", "")
            if future_outlook:
                st.markdown(f"- **Future outlook:** {future_outlook}")

            skills_to_build = rec.get("skills_to_build", [])
            if skills_to_build:
                st.markdown(f"- **Skills to build:** {', '.join(skills_to_build)}")

            fun_facts = rec.get("fun_facts", [])
            if fun_facts:
                st.markdown("- **Fun facts:**")
                for fact in fun_facts[:3]:
                    st.markdown(f"  - {fact}")

            opportunities = rec.get("opportunities", [])
            real_world_impact = rec.get("real_world_impact", "")
            related_majors = rec.get("related_majors", [])
            adjacent_paths = rec.get("adjacent_paths", [])
            next_steps = rec.get("next_steps", [])
            risks = rec.get("risks_or_limitations", [])

            if any([opportunities, real_world_impact, related_majors, adjacent_paths, next_steps, risks]):
                with st.expander(f"More about {title}", icon=":material/info:"):
                    if next_steps:
                        st.markdown("**Next steps**")
                        for step in next_steps[:3]:
                            st.markdown(f"- {step}")
                    if opportunities:
                        st.markdown("**Opportunities**")
                        for item in opportunities:
                            st.markdown(f"- {item}")
                    if real_world_impact:
                        st.markdown(f"**Real-world impact:** {real_world_impact}")
                    if related_majors:
                        st.markdown(f"**Related majors:** {', '.join(related_majors)}")
                    if adjacent_paths:
                        st.markdown(f"**Adjacent paths:** {', '.join(adjacent_paths)}")
                    if risks:
                        st.markdown("**Honest limitations**")
                        for item in risks:
                            st.markdown(f"- {item}")


def _render_roadmap(path_plan: dict) -> None:
    if not path_plan:
        return

    selected_path = path_plan.get("selected_path", "")
    heading = ":material/map: Your roadmap"
    if selected_path:
        heading += f" — {selected_path}"
    st.markdown(f"#### {heading}")

    short_term = path_plan.get("short_term_steps", [])
    medium_term = path_plan.get("medium_term_steps", [])
    long_term = path_plan.get("long_term_steps", [])

    if short_term or medium_term or long_term:
        tab_short, tab_medium, tab_long = st.tabs(["Short term", "Medium term", "Long term"])
        with tab_short:
            for step in short_term:
                st.markdown(f"- {step}")
        with tab_medium:
            for step in medium_term:
                st.markdown(f"- {step}")
        with tab_long:
            for step in long_term:
                st.markdown(f"- {step}")

    skills = path_plan.get("skills_to_build", [])
    if skills:
        st.markdown("**Skills to build**")
        with st.container(horizontal=True):
            for skill in skills:
                st.badge(skill, color="violet")

    projects = path_plan.get("suggested_projects", [])
    college_prep = path_plan.get("college_preparation_steps", [])
    if projects or college_prep:
        with st.expander("Project ideas and college preparation", icon=":material/lightbulb:"):
            if projects:
                st.markdown("**Project ideas**")
                for item in projects:
                    st.markdown(f"- {item}")
            if college_prep:
                st.markdown("**College preparation**")
                for item in college_prep:
                    st.markdown(f"- {item}")


def _render_notes(result: dict) -> None:
    risk_level = result.get("guardrail_risk_level", "low")
    revisions = result.get("guardrail_required_revisions", [])
    requires_more_info = result.get("evaluation_requires_revision", False)

    if risk_level == "high":
        st.warning(
            "I want to keep this guidance realistic and exploratory. Final college or career "
            "decisions should be discussed with a counselor, parent, or trusted advisor.",
            icon=":material/shield:",
        )
    elif risk_level == "medium" and revisions:
        st.caption(":material/info: Keep in mind: " + " ".join(revisions))

    if requires_more_info:
        st.caption(
            ":material/info: This guidance may need more information to be more precise. "
            "Sharing GPA, location, budget, or preferred learning style can improve the recommendation."
        )


def _render_feedback_buttons(log_id) -> None:
    """Thumbs-up / thumbs-down feedback, wired to ObservabilityRepository.save_feedback()."""
    if log_id is None:
        return

    if "feedback_given" not in st.session_state:
        st.session_state.feedback_given = {}

    given = st.session_state.feedback_given.get(log_id)
    if given:
        st.caption(f"Thanks for your feedback ({given}).")
        return

    with st.container(horizontal=True):
        if st.button("👍 Helpful", key=f"feedback_helpful_{log_id}"):
            submit_feedback(log_id, helpful=True)
            st.session_state.feedback_given[log_id] = "helpful"
            st.rerun()
        if st.button("👎 Not Helpful", key=f"feedback_not_helpful_{log_id}"):
            submit_feedback(log_id, helpful=False)
            st.session_state.feedback_given[log_id] = "not helpful"
            st.rerun()


def _render_trace_summary(trace: dict) -> None:
    """Always-visible, plain-language summary shown above the collapsed technical details."""
    badge = trace.get("quality_badge", "not_evaluated")
    score = trace.get("evaluation_score", 0)
    doc_count = trace.get("retrieved_document_count", 0)
    risk_level = trace.get("guardrail_risk_level", "low")

    badge_icon = {"green": "✅", "amber": "⚠️", "red": "❌"}.get(badge, "ℹ️")
    badge_label = badge.capitalize() if badge != "not_evaluated" else "Not evaluated"
    source_icon = "✅" if doc_count else "⚠️"
    guardrail_icon = "✅" if risk_level == "low" else "⚠️"
    guardrail_label = "Passed" if risk_level == "low" else "Flagged"

    st.markdown(
        f"{source_icon} Grounded in {doc_count} source{'s' if doc_count != 1 else ''}  \n"
        f"{badge_icon} Quality: {badge_label} ({score}/30)  \n"
        f"{guardrail_icon} Guardrails: {guardrail_label}"
    )


def _render_trace(trace: dict) -> None:
    badge = trace.get("quality_badge", "not_evaluated")
    score = trace.get("evaluation_score", 0)
    flags = trace.get("guardrail_flags", [])
    guardrail_risk_level = trace.get("guardrail_risk_level", "low")
    guardrail_required_revisions = trace.get("guardrail_required_revisions", [])
    doc_count = trace.get("retrieved_document_count", 0)
    documents = trace.get("retrieved_documents", [])
    recommendations = trace.get("recommendations", [])
    profile = trace.get("profile", {})
    missing_information = trace.get("missing_information", [])
    next_question = trace.get("next_question", "")
    evaluation_scores = trace.get("evaluation_scores", {})
    evaluation_feedback = trace.get("evaluation_feedback", [])
    input_guardrail_flags = trace.get("input_guardrail_flags", [])
    revision_attempted = trace.get("revision_attempted", False)

    badge_col, score_col = st.columns(2)
    with badge_col:
        if badge == "green":
            st.success("Quality badge: green")
        elif badge == "amber":
            st.warning("Quality badge: amber")
        elif badge == "red":
            st.error("Quality badge: red")
        else:
            st.info(f"Quality badge: {badge}")
    with score_col:
        st.metric("Evaluation score", f"{score}/30")

    if revision_attempted:
        st.caption(
            ":material/autorenew: This response was automatically regenerated once because "
            "the initial quality score was below the pass threshold."
        )

    if evaluation_scores:
        st.write(
            "**RASCEF scores:** "
            + ", ".join(f"{dim}: {val}" for dim, val in evaluation_scores.items())
        )
    if evaluation_feedback:
        st.write(f"**Evaluation feedback:** {' | '.join(evaluation_feedback)}")

    st.write(f"**Input guardrail flags:** {', '.join(input_guardrail_flags) if input_guardrail_flags else 'none'}")
    st.write(f"**Guardrail risk level:** {guardrail_risk_level}")
    st.write(f"**Guardrail flags:** {', '.join(flags) if flags else 'none'}")
    if guardrail_required_revisions:
        st.write(f"**Required revisions:** {' | '.join(guardrail_required_revisions)}")
    st.write(f"**Retrieved documents:** {doc_count}")

    if documents:
        st.table(
            [
                {
                    "Title": doc.get("title", ""),
                    "Doc Type": doc.get("doc_type", ""),
                    "Score": round(doc.get("score", 0.0), 4),
                }
                for doc in documents
            ]
        )

    st.write(f"**Recommendations generated:** {len(recommendations)}")
    if recommendations:
        st.table(
            [
                {
                    "Title": rec.get("title", ""),
                    "Type": rec.get("type", ""),
                    "Confidence": round(rec.get("confidence", 0.0), 2),
                }
                for rec in recommendations
            ]
        )

    st.markdown("**Student profile (known so far)**")
    interests = profile.get("interests", [])
    strengths = profile.get("strengths", [])
    gpa = profile.get("gpa")
    favorite_careers = profile.get("favorite_careers", [])

    st.write(f"- Interests: {', '.join(interests) if interests else 'none yet'}")
    st.write(f"- Strengths: {', '.join(strengths) if strengths else 'none yet'}")
    if gpa not in (None, ""):
        st.write(f"- GPA: {gpa}")
    if favorite_careers:
        st.write(f"- Favorite careers: {', '.join(favorite_careers)}")
    if missing_information:
        st.write(f"- Missing information: {', '.join(missing_information)}")
    if next_question:
        st.write(f"- Next question to ask: {next_question}")


def _render_assistant_response(result: dict) -> None:
    student_name = result.get("student_name", "")
    summary = (result.get("recommendation_summary") or "").strip()
    follow_up = (result.get("follow_up_question") or "").strip()
    recommendations = result.get("recommendations", [])
    path_plan = result.get("path_plan", {})

    intro = f"Thanks, {student_name}!" if student_name else "Thanks!"
    if summary:
        intro = f"{intro} {summary}"
    st.write(intro)

    _render_recommendations(recommendations)

    _render_roadmap(path_plan)

    if follow_up:
        st.markdown(f"**{follow_up}**")

    _render_notes(result)

    _render_feedback_buttons(result.get("observability_log_id"))

    _render_trace_summary(result)
    with st.expander("Technical details", icon=":material/analytics:"):
        _render_trace(result)


st.set_page_config(page_title="PathFinder AI", page_icon=":material/explore:", layout="wide")

# --- Session state ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "student_name" not in st.session_state:
    st.session_state.student_name = ""

# --- Sidebar ---
with st.sidebar:
    st.markdown("## :material/explore: PathFinder AI")
    st.caption(
        "Career discovery and college pathway guidance for high school students, "
        "parents, and school counselors."
    )

    st.text_input(
        "Your name",
        key="student_name",
        placeholder="Enter your name to get started",
        icon=":material/person:",
    )

    st.button(
        "New conversation",
        icon=":material/add_comment:",
        on_click=_reset_conversation,
        width="stretch",
    )

# --- Main page ---
st.title("PathFinder AI")
st.caption("A conversational counselor for exploring careers, majors, and college pathways.")

if not st.session_state.messages:
    st.info(
        "Tell me what you're into — subjects, hobbies, anything — and I'll help you explore "
        "career and college directions that might fit.",
        icon=":material/explore:",
    )

# Render existing chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar=AVATARS.get(msg["role"])):
        if msg["role"] == "assistant" and "trace" in msg:
            _render_assistant_response(msg["trace"])
        else:
            st.write(msg["content"])
        timestamp = _format_timestamp(msg.get("timestamp"))
        if timestamp:
            st.caption(timestamp)

# Handle new message
user_message = st.chat_input("Ask PathFinder AI anything about careers, majors, or college pathways...")

if user_message:
    name = st.session_state.student_name.strip() if st.session_state.student_name.strip() else "Student"
    user_timestamp = datetime.datetime.now()

    st.session_state.messages.append({"role": "user", "content": user_message, "timestamp": user_timestamp})
    with st.chat_message("user", avatar=AVATARS["user"]):
        st.write(user_message)
        st.caption(_format_timestamp(user_timestamp))

    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        with st.spinner("Thinking..."):
            result = run_turn(student_name=name, user_message=user_message)
        _render_assistant_response(result)
        assistant_timestamp = datetime.datetime.now()
        st.caption(_format_timestamp(assistant_timestamp))

    st.session_state.messages.append({
        "role": "assistant",
        "content": result["response"],
        "trace": result,
        "timestamp": assistant_timestamp,
    })
