from __future__ import annotations

from pathlib import Path

from app.models import SurveyStatsResponse


class MarkdownReportExporter:
    def __init__(self, report_dir: Path):
        self.report_dir = report_dir

    def export(self, stats: SurveyStatsResponse) -> Path:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = stats.generated_at.strftime("%Y%m%d_%H%M%S")
        path = self.report_dir / f"{timestamp}_{stats.survey_id}_summary.md"
        path.write_text(self._render(stats), encoding="utf-8")
        return path

    def _render(self, stats: SurveyStatsResponse) -> str:
        lines = [
            f"# Survey Report — {stats.survey_id}",
            "",
            f"- Generated at: {stats.generated_at.isoformat()}",
            f"- Sessions: {stats.session_count}",
            f"- Responses: {stats.response_count}",
            "",
            "## Option Counts",
            "",
        ]
        if not stats.option_counts:
            lines.append("No option responses yet.")
        for question_id, counts in stats.option_counts.items():
            lines.append(f"### {question_id}")
            for option, count in sorted(counts.items()):
                lines.append(f"- {option}: {count}")
            lines.append("")

        lines.extend(["## Sentiment Counts", ""])
        if not stats.sentiment_counts:
            lines.append("No sentiment data yet.")
        for sentiment, count in sorted(stats.sentiment_counts.items()):
            lines.append(f"- {sentiment}: {count}")
        lines.append("")
        return "\n".join(lines)
