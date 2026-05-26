from __future__ import annotations

import html

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    orchestrator_base_url: str = "http://ai-orchestrator:8000"
    default_survey_id: str = "campus_opinion_survey"


class DashboardClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.client = client

    async def get_stats(self, survey_id: str) -> dict:
        if self.client:
            response = await self.client.get(f"{self.base_url}/surveys/{survey_id}/stats")
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/surveys/{survey_id}/stats")
        response.raise_for_status()
        return response.json()


def create_app(settings: Settings | None = None, dashboard_client: DashboardClient | None = None) -> FastAPI:
    resolved = settings or Settings()
    client = dashboard_client or DashboardClient(resolved.orchestrator_base_url)
    app = FastAPI(title="ARS Survey Dashboard", version="0.1.0")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "dashboard"}

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return await render_survey(resolved.default_survey_id)

    @app.get("/surveys/{survey_id}", response_class=HTMLResponse)
    async def render_survey(survey_id: str) -> str:
        stats = await client.get_stats(survey_id)
        return _render_html(stats)

    return app


def _render_html(stats: dict) -> str:
    survey_id = html.escape(stats["survey_id"])
    sentiment_rows = "".join(
        f"<tr><td>{html.escape(sentiment)}</td><td>{count}</td></tr>" for sentiment, count in sorted(stats["sentiment_counts"].items())
    )
    option_blocks = []
    for question_id, counts in sorted(stats["option_counts"].items()):
        rows = "".join(f"<tr><td>{html.escape(option)}</td><td>{count}</td></tr>" for option, count in sorted(counts.items()))
        option_blocks.append(f"<h2>{html.escape(question_id)}</h2><table><tbody>{rows}</tbody></table>")
    options = "\n".join(option_blocks) or "<p>No option responses yet.</p>"
    sentiments = sentiment_rows or "<tr><td colspan='2'>No sentiment data yet.</td></tr>"
    return f"""
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8">
    <title>ARS Survey Dashboard</title>
    <style>
      body {{ font-family: system-ui, sans-serif; margin: 32px; color: #18202a; }}
      table {{ border-collapse: collapse; min-width: 280px; }}
      td, th {{ border-bottom: 1px solid #d8dee6; padding: 8px 12px; text-align: left; }}
      .summary {{ display: flex; gap: 24px; margin: 16px 0 28px; }}
      .metric {{ border: 1px solid #d8dee6; border-radius: 6px; padding: 12px 16px; }}
    </style>
  </head>
  <body>
    <h1>{survey_id}</h1>
    <div class="summary">
      <div class="metric"><strong>Sessions</strong><br>{stats["session_count"]}</div>
      <div class="metric"><strong>Responses</strong><br>{stats["response_count"]}</div>
    </div>
    <h2>Sentiment</h2>
    <table><tbody>{sentiments}</tbody></table>
    <h2>Options</h2>
    {options}
  </body>
</html>
"""


app = create_app()

