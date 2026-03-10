from __future__ import annotations

from openai import OpenAI

from app.core.config import OPENAI_API_KEY


def generate_company_summary(company_name: str, articles: list[dict]) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required to generate summaries")

    client = OpenAI(api_key=OPENAI_API_KEY)

    articles_lines = []
    for a in articles:
        title = (a.get("title") or "").strip()
        snippet = (a.get("snippet") or "").strip()
        content_text = (a.get("content_text") or "").strip()
        source = (a.get("source") or "").strip()
        published_at = a.get("published_at")

        if content_text:
            content_text = content_text[:4000]
        if snippet:
            snippet = snippet[:500]
        articles_lines.append(
            "- Title: "
            + title
            + "\n  Source: "
            + source
            + "\n  Published: "
            + str(published_at)
            + "\n  Snippet: "
            + snippet
            + "\n  ArticleText: "
            + (content_text if content_text else "(not available)")
        )

    prompt = (
        "You are summarizing recent news about a startup company.\n\n"
        f"Company: {company_name}\n\n"
        "Articles:\n"
        + "\n".join(articles_lines)
        + "\n\n"
        "Each article may contain:\n"
        "- Title\n"
        "- Source\n"
        "- Published date\n"
        "- Snippet\n"
        "- ArticleText (full extracted article text)\n\n"
        "Instructions:\n"
        "Use the article text as the primary source of information when available. Titles and snippets may be used only if the article text is missing.\n\n"
        "Write a concise 2–3 sentence summary describing the company's recent developments.\n\n"
        "Focus only on factual updates such as:\n"
        "- product launches\n"
        "- funding\n"
        "- partnerships\n"
        "- acquisitions\n"
        "- expansions\n"
        "- strategic announcements\n\n"
        "Do not speculate or invent information.\n\n"
        "If the articles do not contain clear business developments, respond with:\n"
        '"No clear recent company announcements were reported in the available articles."'
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("Empty summary response")
    return text
