import os
import html
from playwright.sync_api import sync_playwright

PAGE_CSS = """
    @page { margin: 1in; }
    body {
        font-family: "Noto Sans Bengali", "Noto Sans", Arial, sans-serif;
        font-size: 12px;
        color: #1a1a1a;
    }
    h1 { font-size: 20px; margin-bottom: 20px; }
    .question { font-weight: bold; font-size: 13px; margin-top: 16px; }
    .answer { margin-top: 4px; color: #333333; line-height: 1.5; }
"""


def build_qa_pdf(output_path: str, title: str, qa_pairs: list[dict], language: str = "en"):
    """
    Writes a study-guide PDF to output_path by rendering HTML in headless
    Chromium and printing it to PDF. Works correctly for both English and
    Bengali (or any other script) because Chromium handles text shaping.

    Locally (Windows dev machine) we use the system-installed Google Chrome
    via channel="chrome", since downloading Playwright's own Chromium can be
    unreliable on some networks. On the deployed server (Render), the
    USE_SYSTEM_CHROME env var won't be set, so Playwright's own bundled
    Chromium (installed during the build step) is used instead.
    """
    body_parts = [f"<h1>{html.escape(title)}</h1>"]
    for i, pair in enumerate(qa_pairs, start=1):
        question = html.escape(pair.get("question", ""))
        answer = html.escape(pair.get("answer", ""))
        body_parts.append(f'<div class="question">Q{i}. {question}</div>')
        body_parts.append(f'<div class="answer">{answer}</div>')

    html_content = f"""
    <html>
    <head><meta charset="utf-8"><style>{PAGE_CSS}</style></head>
    <body>{''.join(body_parts)}</body>
    </html>
    """

    use_system_chrome = os.environ.get("USE_SYSTEM_CHROME") == "true"

    with sync_playwright() as p:
        if use_system_chrome:
            browser = p.chromium.launch(channel="chrome")
        else:
            browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content)
        page.pdf(path=output_path, format="A4")
        browser.close()

    return output_path