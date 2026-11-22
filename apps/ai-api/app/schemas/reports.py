"""Report export extras (owner: backend-a). Markdown/CSV/JSON use common.ReportDocument."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import ApiModel, Disclaimer


class HtmlReport(ApiModel):
    """Print-ready HTML report (open in a browser and use Print -> Save as PDF). Server-side PDF is not built."""

    report_type: str
    title: str
    generated_at: datetime
    as_of: datetime
    filename: str
    html: str = Field(description="Self-contained HTML document (inline CSS, no scripts)")
    disclaimers: list[Disclaimer]
