from __future__ import annotations

from app.models import CollectedPost


def build_stub_analysis(post: CollectedPost) -> dict[str, str]:
    """Deterministic placeholder until the LLM provider is wired.

    This keeps the MVP flow testable without API keys. Later this function will call
    an LLM with the post title, metadata, and policy constraints.
    """

    title = post.title.strip()
    return {
        "summary": f"Potential viral story based on: {title}",
        "core_conflict": "A personal relationship conflict with a clear emotional trigger.",
        "red_flags": "Boundary crossing, delayed honesty, or pressure response may be involved.",
        "debate_point": "Was the main character overreacting, or did they notice the pattern early?",
        "audience_emotion": "anger, shock, sympathy, curiosity",
        "hidden_pattern": "Most people will focus on the event itself. The stronger angle is the repeated pattern behind the choice.",
        "youtube_angle": "Open with the most shocking discovery, then reframe it as a hidden relationship pattern.",
        "risk_notes": "Use as inspiration only. Do not copy the original wording or identifiable details.",
    }


def build_stub_shorts_script(title: str) -> dict[str, str]:
    return {
        "title_options": "\n".join(
            [
                "Everyone Saw Drama. She Saw the Pattern.",
                "They Called Her Dramatic Until the Truth Came Out",
                "This Was Not the Real Problem",
                "She Noticed the Red Flag Early",
                "The Pattern Was There the Whole Time",
            ]
        ),
        "thumbnail_options": "\n".join(
            ["SHE WAS RIGHT", "NOT JUST DRAMA", "RED FLAG?", "THE PATTERN", "TOO LATE" ]
        ),
        "hook_options": "\n".join(
            [
                "She thought it was one small problem. It was not.",
                "Everyone told her she was overreacting. Then the pattern became obvious.",
                "This story looks simple until you notice what keeps repeating.",
            ]
        ),
        "body": (
            "She thought this was just one strange moment.\n\n"
            "But when she looked back, the pattern was already there.\n\n"
            "Every time she noticed something uncomfortable, someone made her feel dramatic for reacting.\n\n"
            "And that is why this story works.\n\n"
            "Most people will argue about the event.\n"
            "But the real question is the pattern behind it.\n\n"
            "So tell me.\n"
            "Was she overreacting, or did she see the future early?"
        ),
        "comment_question": "Was she overreacting, or did she see the future early?",
    }
