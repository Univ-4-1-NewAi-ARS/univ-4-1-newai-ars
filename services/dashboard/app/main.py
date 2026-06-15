from __future__ import annotations

import html
import time
from datetime import datetime

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    orchestrator_base_url: str = "http://ai-orchestrator:8000"
    stt_base_url: str = "http://stt-service:8100"
    tts_base_url: str = "http://tts-service:8200"
    default_survey_id: str = "campus_opinion_survey"
    health_timeout_sec: float = 3.0


class DashboardClient:
    """Thin async HTTP client over the orchestrator and speech services."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.base_url = settings.orchestrator_base_url.rstrip("/")
        self.client = client

    async def _get_json(self, url: str) -> dict:
        if self.client:
            response = await self.client.get(url)
        else:
            async with httpx.AsyncClient(timeout=self.settings.health_timeout_sec) as client:
                response = await client.get(url)
        response.raise_for_status()
        return response.json()

    async def get_stats(self, survey_id: str) -> dict:
        return await self._get_json(f"{self.base_url}/surveys/{survey_id}/stats")

    async def get_providers(self) -> dict:
        return await self._get_json(f"{self.base_url}/runtime/providers")

    async def get_audit_events(self, limit: int = 50) -> dict:
        return await self._get_json(f"{self.base_url}/audit/events?limit={limit}")

    async def get_insights(self, survey_id: str) -> dict:
        return await self._get_json(f"{self.base_url}/surveys/{survey_id}/insights")

    async def ping(self, name: str, base_url: str) -> dict:
        """Probe a service /health endpoint and capture status + latency."""
        url = f"{base_url.rstrip('/')}/health"
        started = time.perf_counter()
        try:
            payload = await self._get_json(url)
            latency_ms = (time.perf_counter() - started) * 1000
            detail = payload.get("provider") or payload.get("repository") or payload.get("status", "ok")
            return {"name": name, "url": base_url, "ok": True, "latency_ms": latency_ms, "detail": str(detail)}
        except Exception as exc:  # noqa: BLE001 - surface any failure as a down badge
            latency_ms = (time.perf_counter() - started) * 1000
            return {"name": name, "url": base_url, "ok": False, "latency_ms": latency_ms, "detail": type(exc).__name__}


def create_app(settings: Settings | None = None, dashboard_client: DashboardClient | None = None) -> FastAPI:
    resolved = settings or Settings()
    client = dashboard_client or DashboardClient(resolved)
    app = FastAPI(title="ARS Survey Dashboard", version="0.2.0")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "dashboard"}

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return await render_survey(resolved.default_survey_id)

    @app.get("/surveys/{survey_id}", response_class=HTMLResponse)
    async def render_survey(survey_id: str) -> str:
        try:
            stats = await client.get_stats(survey_id)
        except Exception as exc:  # noqa: BLE001
            return _layout("요약", "summary", _error_banner("통계를 불러오지 못했습니다", exc))
        return _layout(f"요약 · {survey_id}", "summary", _summary_body(stats), survey_id=survey_id)

    @app.get("/insights", response_class=HTMLResponse)
    async def insights() -> str:
        return await render_insights(resolved.default_survey_id)

    @app.get("/surveys/{survey_id}/insights", response_class=HTMLResponse)
    async def render_insights(survey_id: str) -> str:
        try:
            data = await client.get_insights(survey_id)
        except Exception as exc:  # noqa: BLE001
            return _layout("의견 종합", "insights", _error_banner("의견 종합을 불러오지 못했습니다", exc))
        return _layout(f"의견 종합 · {survey_id}", "insights", _insights_body(data), survey_id=survey_id)

    @app.get("/services", response_class=HTMLResponse)
    async def services() -> str:
        checks = [
            await client.ping("AI Orchestrator", resolved.orchestrator_base_url),
            await client.ping("STT Service", resolved.stt_base_url),
            await client.ping("TTS Service", resolved.tts_base_url),
        ]
        try:
            providers = await client.get_providers()
        except Exception:  # noqa: BLE001 - providers panel is best-effort
            providers = None
        return _layout("서비스 헬스", "services", _services_body(checks, providers), refresh=10)

    @app.get("/logs", response_class=HTMLResponse)
    async def logs(limit: int = 50) -> str:
        try:
            payload = await client.get_audit_events(limit=limit)
        except Exception as exc:  # noqa: BLE001
            return _layout("중요 로그", "logs", _error_banner("감사 로그를 불러오지 못했습니다", exc), refresh=10)
        return _layout("중요 로그", "logs", _logs_body(payload), refresh=10)

    return app


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #

SENTIMENT_COLORS = {
    "positive": "#16a34a",
    "neutral": "#64748b",
    "negative": "#dc2626",
    "unknown": "#d97706",
}
SEVERITY_COLORS = {
    "info": "#2563eb",
    "debug": "#64748b",
    "warning": "#d97706",
    "warn": "#d97706",
    "error": "#dc2626",
    "critical": "#dc2626",
}

NAV = [
    ("summary", "요약", "/"),
    ("insights", "의견 종합", "/insights"),
    ("services", "서비스 헬스", "/services"),
    ("logs", "중요 로그", "/logs"),
]


def _layout(title: str, active: str, body: str, *, refresh: int | None = None, survey_id: str | None = None) -> str:
    nav = "".join(
        f'<a class="nav-item{" active" if key == active else ""}" href="{href}">{html.escape(label)}</a>'
        for key, label, href in NAV
    )
    refresh_meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    {refresh_meta}
    <title>{html.escape(title)} · ARS Dashboard</title>
    <style>
      :root {{
        --bg: #f1f5f9; --panel: #ffffff; --ink: #0f172a; --muted: #64748b;
        --line: #e2e8f0; --brand: #4f46e5; --brand-ink: #eef2ff;
      }}
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; background: var(--bg); color: var(--ink);
        font-family: -apple-system, system-ui, "Segoe UI", Roboto, "Noto Sans KR", sans-serif; }}
      header {{ background: #111827; color: #fff; padding: 0 28px; display: flex;
        align-items: center; gap: 28px; box-shadow: 0 1px 3px rgba(0,0,0,.2); }}
      header .brand {{ font-weight: 700; font-size: 17px; padding: 16px 0; letter-spacing: .2px; }}
      header .brand span {{ color: #818cf8; }}
      nav {{ display: flex; gap: 4px; }}
      .nav-item {{ color: #cbd5e1; text-decoration: none; padding: 18px 14px; font-size: 14px;
        border-bottom: 3px solid transparent; transition: .15s; }}
      .nav-item:hover {{ color: #fff; }}
      .nav-item.active {{ color: #fff; border-bottom-color: #818cf8; }}
      main {{ max-width: 1040px; margin: 28px auto; padding: 0 24px; }}
      h1 {{ font-size: 22px; margin: 0 0 4px; }}
      .sub {{ color: var(--muted); font-size: 13px; margin: 0 0 22px; }}
      .grid {{ display: grid; gap: 16px; }}
      .cards {{ grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }}
      .svc {{ grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }}
      .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
        padding: 18px 20px; box-shadow: 0 1px 2px rgba(15,23,42,.04); }}
      .metric .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .6px; }}
      .metric .value {{ font-size: 32px; font-weight: 700; margin-top: 6px; }}
      h2 {{ font-size: 15px; margin: 28px 0 12px; color: #334155; }}
      table {{ width: 100%; border-collapse: collapse; background: var(--panel);
        border: 1px solid var(--line); border-radius: 12px; overflow: hidden; font-size: 14px; }}
      th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--line); }}
      th {{ background: #f8fafc; color: var(--muted); font-weight: 600; font-size: 12px;
        text-transform: uppercase; letter-spacing: .4px; }}
      tr:last-child td {{ border-bottom: none; }}
      tbody tr:hover {{ background: #f8fafc; }}
      .bar {{ height: 8px; border-radius: 6px; background: #e2e8f0; overflow: hidden; min-width: 120px; }}
      .bar > span {{ display: block; height: 100%; border-radius: 6px; }}
      .badge {{ display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600;
        padding: 3px 10px; border-radius: 999px; }}
      .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
      .svc-head {{ display: flex; align-items: center; justify-content: space-between; }}
      .svc-name {{ font-weight: 700; font-size: 15px; }}
      .svc-meta {{ color: var(--muted); font-size: 13px; margin-top: 10px; line-height: 1.7; }}
      .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
      .pill {{ background: var(--brand-ink); color: var(--brand); border-radius: 6px; padding: 2px 8px;
        font-size: 12px; font-weight: 600; }}
      .banner {{ background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; padding: 14px 18px;
        border-radius: 12px; }}
      .empty {{ color: var(--muted); padding: 18px; text-align: center; }}
      .cloud {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 4px; }}
      .chip {{ background: var(--brand-ink); color: var(--brand); border-radius: 999px;
        padding: 5px 13px; font-size: 13px; font-weight: 600; }}
      .chip .n {{ opacity: .55; margin-left: 6px; font-weight: 700; }}
      .qhead {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 30px 0 4px; }}
      .qhead h2 {{ margin: 0; font-size: 16px; }}
      .qtype {{ background: #f1f5f9; color: #475569; border-radius: 6px; padding: 2px 9px;
        font-size: 12px; font-weight: 600; }}
      .quote {{ background: var(--panel); border: 1px solid var(--line); border-left: 4px solid #64748b;
        border-radius: 10px; padding: 13px 16px; margin-bottom: 10px; }}
      .quote .txt {{ font-size: 15px; line-height: 1.55; }}
      .quote .meta {{ margin-top: 9px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
      .tag {{ background: #f1f5f9; color: #475569; border-radius: 6px; padding: 2px 8px; font-size: 12px; }}
      footer {{ max-width: 1040px; margin: 8px auto 40px; padding: 0 24px; color: var(--muted); font-size: 12px; }}
    </style>
  </head>
  <body>
    <header>
      <div class="brand">ARS <span>Survey</span> Dashboard</div>
      <nav>{nav}</nav>
    </header>
    <main>
      {body}
    </main>
    <footer>rendered {stamp}{f" · survey: {html.escape(survey_id)}" if survey_id else ""}</footer>
  </body>
</html>
"""


def _error_banner(message: str, exc: Exception) -> str:
    return (
        f'<h1>{html.escape(message)}</h1>'
        f'<div class="banner">{html.escape(type(exc).__name__)}: {html.escape(str(exc))}</div>'
    )


def _bar(pct: float, color: str) -> str:
    pct = max(0.0, min(100.0, pct))
    return f'<div class="bar"><span style="width:{pct:.1f}%;background:{color}"></span></div>'


def _summary_body(stats: dict) -> str:
    survey_id = html.escape(stats["survey_id"])
    sessions = stats["session_count"]
    responses = stats["response_count"]

    cards = (
        '<div class="grid cards">'
        f'<div class="panel metric"><div class="label">Sessions</div><div class="value">{sessions}</div></div>'
        f'<div class="panel metric"><div class="label">Responses</div><div class="value">{responses}</div></div>'
        '</div>'
    )

    sentiments = stats.get("sentiment_counts") or {}
    total = sum(sentiments.values()) or 1
    if sentiments:
        rows = ""
        for name, count in sorted(sentiments.items(), key=lambda kv: kv[1], reverse=True):
            color = SENTIMENT_COLORS.get(name, "#64748b")
            pct = count / total * 100
            rows += (
                f"<tr><td><span class='badge' style='background:{color}1a;color:{color}'>"
                f"<span class='dot' style='background:{color}'></span>{html.escape(name)}</span></td>"
                f"<td>{count}</td><td>{_bar(pct, color)}</td><td class='mono'>{pct:.0f}%</td></tr>"
            )
        sentiment_html = (
            "<table><thead><tr><th>Sentiment</th><th>Count</th><th>Share</th><th></th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
    else:
        sentiment_html = '<div class="panel empty">아직 감정 분석 데이터가 없습니다.</div>'

    option_counts = stats.get("option_counts") or {}
    if option_counts:
        blocks = ""
        for question_id, counts in sorted(option_counts.items()):
            q_total = sum(counts.values()) or 1
            rows = ""
            for option, count in sorted(counts.items()):
                pct = count / q_total * 100
                rows += (
                    f"<tr><td>{html.escape(option)}</td><td>{count}</td>"
                    f"<td>{_bar(pct, '#4f46e5')}</td><td class='mono'>{pct:.0f}%</td></tr>"
                )
            blocks += (
                f"<h2>{html.escape(question_id)}</h2>"
                "<table><thead><tr><th>Option</th><th>Count</th><th>Share</th><th></th></tr></thead>"
                f"<tbody>{rows}</tbody></table>"
            )
        options_html = blocks
    else:
        options_html = '<div class="panel empty">아직 선택지 응답이 없습니다.</div>'

    return (
        f'<h1>{survey_id}</h1>'
        '<p class="sub">설문 응답 요약</p>'
        f'{cards}'
        '<h2>Sentiment</h2>'
        f'{sentiment_html}'
        '<h2>Options</h2>'
        f'{options_html}'
    )


def _services_body(checks: list[dict], providers: dict | None) -> str:
    healthy = sum(1 for c in checks if c["ok"])
    cards = ""
    for c in checks:
        ok = c["ok"]
        color = "#16a34a" if ok else "#dc2626"
        label = "정상" if ok else "오류"
        cards += (
            '<div class="panel">'
            '<div class="svc-head">'
            f'<span class="svc-name">{html.escape(c["name"])}</span>'
            f'<span class="badge" style="background:{color}1a;color:{color}">'
            f'<span class="dot" style="background:{color}"></span>{label}</span>'
            '</div>'
            '<div class="svc-meta">'
            f'<div class="mono">{html.escape(c["url"])}</div>'
            f'<div>응답 {c["latency_ms"]:.0f} ms · {html.escape(c["detail"])}</div>'
            '</div></div>'
        )
    grid = f'<div class="grid svc">{cards}</div>'

    providers_html = ""
    if providers:
        rows = ""
        for layer in ("llm", "stt", "tts"):
            cfg = providers.get(layer) or {}
            extras = ", ".join(
                f"{html.escape(k)}={html.escape(str(v))}"
                for k, v in cfg.items()
                if k not in {"provider", "status"}
            )
            rows += (
                f"<tr><td><span class='pill'>{layer.upper()}</span></td>"
                f"<td><strong>{html.escape(str(cfg.get('provider', '—')))}</strong></td>"
                f"<td class='mono'>{html.escape(str(cfg.get('status', '—')))}</td>"
                f"<td class='mono'>{extras}</td></tr>"
            )
        providers_html = (
            "<h2>Provider 런타임 구성</h2>"
            "<table><thead><tr><th>Layer</th><th>Provider</th><th>Status</th><th>Settings</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )

    return (
        '<h1>서비스 헬스</h1>'
        f'<p class="sub">{healthy}/{len(checks)} 정상 · 10초마다 자동 새로고침</p>'
        f'{grid}'
        f'{providers_html}'
    )


def _logs_body(payload: dict) -> str:
    events = payload.get("events") or []
    if not events:
        return (
            '<h1>중요 로그</h1>'
            '<p class="sub">감사 이벤트 (audit_events)</p>'
            '<div class="panel empty">아직 기록된 이벤트가 없습니다.</div>'
        )
    rows = ""
    for ev in events:
        sev = (ev.get("severity") or "info").lower()
        color = SEVERITY_COLORS.get(sev, "#64748b")
        created = html.escape(str(ev.get("created_at", ""))[:19].replace("T", " "))
        session = ev.get("session_id")
        session_html = f'<span class="mono">{html.escape(str(session)[:8])}</span>' if session else "—"
        details = ev.get("details") or {}
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        rows += (
            f"<tr><td class='mono'>{created}</td>"
            f"<td><span class='badge' style='background:{color}1a;color:{color}'>"
            f"<span class='dot' style='background:{color}'></span>{html.escape(sev)}</span></td>"
            f"<td><strong>{html.escape(str(ev.get('event_type', '')))}</strong></td>"
            f"<td>{session_html}</td>"
            f"<td class='mono'>{html.escape(detail_str)}</td></tr>"
        )
    return (
        '<h1>중요 로그</h1>'
        f'<p class="sub">최근 감사 이벤트 {len(events)}건 · 10초마다 자동 새로고침</p>'
        "<table><thead><tr><th>시각</th><th>심각도</th><th>이벤트</th><th>세션</th><th>상세</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _sentiment_table(sentiments: dict, empty: str) -> str:
    total = sum(sentiments.values()) or 1
    if not sentiments:
        return f"<div class='panel empty'>{empty}</div>"
    rows = ""
    for name, count in sorted(sentiments.items(), key=lambda kv: kv[1], reverse=True):
        color = SENTIMENT_COLORS.get(name, "#64748b")
        pct = count / total * 100
        rows += (
            f"<tr><td><span class='badge' style='background:{color}1a;color:{color}'>"
            f"<span class='dot' style='background:{color}'></span>{html.escape(name)}</span></td>"
            f"<td>{count}</td><td>{_bar(pct, color)}</td><td class='mono'>{pct:.0f}%</td></tr>"
        )
    return (
        "<table><thead><tr><th>Sentiment</th><th>Count</th><th>Share</th><th></th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _keyword_cloud(keywords: dict, limit: int) -> str:
    if not keywords:
        return ""
    chips = "".join(
        f"<span class='chip'>{html.escape(str(k))}<span class='n'>{v}</span></span>"
        for k, v in list(keywords.items())[:limit]
    )
    return f"<div class='cloud'>{chips}</div>"


def _insights_body(data: dict) -> str:
    survey_id = html.escape(data["survey_id"])
    response_count = data.get("response_count", 0)

    keywords = data.get("keyword_counts") or {}
    keyword_html = _keyword_cloud(keywords, 20) or "<div class='panel empty'>아직 추출된 키워드가 없습니다.</div>"
    sentiment_html = _sentiment_table(data.get("sentiment_counts") or {}, "아직 감정 데이터가 없습니다.")

    blocks = ""
    for q in data.get("questions", []):
        qid = html.escape(str(q["question_id"]))
        qtext = html.escape(str(q["text"]))
        atype = str(q["answer_type"])
        blocks += (
            f"<div class='qhead'><h2>{qid}. {qtext}</h2>"
            f"<span class='qtype'>{html.escape(atype)}</span>"
            f"<span class='qtype'>{q.get('response_count', 0)} 응답</span></div>"
        )
        if atype == "single_choice":
            option_counts = q.get("option_counts") or {}
            if option_counts:
                q_total = sum(option_counts.values()) or 1
                rows = ""
                for label, count in sorted(option_counts.items(), key=lambda kv: kv[1], reverse=True):
                    pct = count / q_total * 100
                    rows += (
                        f"<tr><td>{html.escape(str(label))}</td><td>{count}</td>"
                        f"<td>{_bar(pct, '#4f46e5')}</td><td class='mono'>{pct:.0f}%</td></tr>"
                    )
                blocks += (
                    "<table><thead><tr><th>선택</th><th>응답</th><th>비율</th><th></th></tr></thead>"
                    f"<tbody>{rows}</tbody></table>"
                )
            else:
                blocks += "<div class='panel empty'>아직 선택 응답이 없습니다.</div>"
        else:
            blocks += _keyword_cloud(q.get("keyword_counts") or {}, 12)
            opinions = q.get("opinions") or []
            if opinions:
                for op in opinions:
                    sentiment = str(op.get("sentiment", "unknown"))
                    color = SENTIMENT_COLORS.get(sentiment, "#64748b")
                    tags = "".join(f"<span class='tag'>{html.escape(str(k))}</span>" for k in op.get("keywords", []))
                    conf = op.get("confidence")
                    conf_html = f"<span class='tag'>conf {conf:.2f}</span>" if isinstance(conf, (int, float)) else ""
                    blocks += (
                        f"<div class='quote' style='border-left-color:{color}'>"
                        f"<div class='txt'>{html.escape(str(op.get('text', '')))}</div>"
                        f"<div class='meta'><span class='badge' style='background:{color}1a;color:{color}'>"
                        f"<span class='dot' style='background:{color}'></span>{html.escape(sentiment)}</span>"
                        f"{tags}{conf_html}</div></div>"
                    )
            else:
                blocks += "<div class='panel empty'>아직 자유 의견이 없습니다.</div>"

    return (
        "<h1>의견 종합</h1>"
        f"<p class='sub'>{survey_id} · 총 {response_count}개 응답 종합</p>"
        "<h2>핵심 키워드</h2>"
        f"{keyword_html}"
        "<h2>전체 감정 분포</h2>"
        f"{sentiment_html}"
        f"{blocks}"
    )


app = create_app()
