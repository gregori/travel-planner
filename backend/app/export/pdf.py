import markdown as md_lib
from weasyprint import HTML

from app.export.markdown import generate_markdown
from app.models.plan import TripPlan

_CSS = """
@page { size: A4; margin: 2cm; }
body { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 11pt; color: #1a1a1a; line-height: 1.45; }
h1 { font-size: 20pt; margin-bottom: 0.2em; }
h2 { font-size: 15pt; margin-top: 1.2em; border-bottom: 1px solid #ccc; padding-bottom: 0.2em; }
h3 { font-size: 12.5pt; margin-top: 1em; }
table { border-collapse: collapse; width: 100%; margin: 0.6em 0; }
th, td { border: 1px solid #ddd; padding: 4px 8px; text-align: left; font-size: 10pt; }
th { background: #f2f2f2; }
blockquote { background: #fff8e1; border-left: 4px solid #f5c518; margin: 0.8em 0; padding: 0.4em 1em; }
"""


def generate_pdf_bytes(plan: TripPlan) -> bytes:
    """Exporta o plano em PDF formatado a partir do Markdown (RF-31)."""
    md_content = generate_markdown(plan)
    html_body = md_lib.markdown(md_content, extensions=["tables"])
    full_html = f"<html><head><style>{_CSS}</style></head><body>{html_body}</body></html>"
    return HTML(string=full_html).write_pdf()
