#!/usr/bin/env python3
"""Némesis RADAR: first live web-search adapter; results are leads, not verified facts."""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import nemesis_mvp as core

SEARCH_URL = "https://html.duckduckgo.com/html/"
USER_AGENT = "NemesisRadar/0.1 (+https://github.com/Jota-jot/nemesis-care-web)"


class _ResultsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results = []
        self._current = None
        self._capture = None
        self._buffer = []

    def _finish_current(self):
        if self._current and self._current.get("title"):
            self.results.append(self._current)
        self._current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            self._finish_current()
            self._current = {"title": "", "url": attrs.get("href", ""), "snippet": ""}
            self._capture = "title"
            self._buffer = []
        elif self._current is not None and tag == "a" and "result__snippet" in classes:
            self._capture = "snippet"
            self._buffer = []
        elif self._current is not None and tag == "div" and "result__snippet" in classes:
            self._capture = "snippet"
            self._buffer = []

    def handle_data(self, data):
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if self._capture == "title" and tag == "a" and self._current is not None:
            self._current["title"] = " ".join("".join(self._buffer).split())
            self._capture = None
            self._buffer = []
        elif self._capture == "snippet" and tag == "div" and self._current is not None:
            self._current["snippet"] = " ".join("".join(self._buffer).split())
            self._capture = None
            self._buffer = []

    def close(self):
        super().close()
        self._finish_current()


def search_web(query: str, limit: int = 8, timeout: int = 12) -> list[dict]:
    """Search public web results. Does not fetch or verify the linked pages."""
    query = query.strip()
    if not query:
        raise ValueError("La búsqueda no puede estar vacía.")
    if not 1 <= limit <= 10:
        raise ValueError("limit debe estar entre 1 y 10.")
    request = Request(
        SEARCH_URL + "?" + urlencode({"q": query}),
        headers={"User-Agent": USER_AGENT, "Accept-Language": "es,en;q=0.8"},
    )
    with urlopen(request, timeout=timeout) as response:
        html = response.read(1_500_000).decode("utf-8", errors="replace")
    parser = _ResultsParser()
    parser.feed(html)
    results = []
    for item in parser.results:
        url, title = item.get("url", ""), item.get("title", "")
        if title and url.startswith(("https://", "http://")):
            results.append({"title": title, "url": url, "snippet": item.get("snippet", "")})
        if len(results) >= limit:
            break
    return results


def run_search(db, query: str, limit: int = 8, timeout: int = 12) -> dict:
    results = search_web(query, limit=limit, timeout=timeout)
    task_id = core.add_task(
        title=f"RADAR: {query}",
        objective="Explorar resultados web; verificar manualmente fuentes, fechas y afirmaciones antes de tratarlas como hechos.",
        priority=4,
    )
    saved = []
    for item in results:
        lead = item["title"]
        if item["snippet"]:
            lead += " — " + item["snippet"]
        evidence_id = core.add_evidence(
            db, claim=lead, evidence_type="hypothesis", confidence=0.25,
            source_url=item["url"], source_title=item["title"], task_id=task_id,
            notes="Pista automática de buscador; NO es un hecho verificado. Abrir la fuente, comprobar fecha, autoría y evidencia primaria antes de usarla.",
        )
        saved.append({**item, "evidence_id": evidence_id, "status": "lead_not_verified"})
    return {
        "query": query, "task_id": task_id, "result_count": len(saved), "results": saved,
        "limitations": [
            "Son resultados de búsqueda, no páginas leídas ni hechos confirmados.",
            "El buscador puede bloquear, cambiar el HTML o devolver resultados incompletos.",
            "No se ha comprobado independencia entre fuentes ni actualidad de cada página.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Némesis RADAR — búsqueda web inicial, con registro auditable")
    parser.add_argument("query", help="Pregunta o tema a investigar")
    parser.add_argument("--db", default=str(core.DEFAULT_DB), help="Ruta de la base SQLite")
    parser.add_argument("--limit", type=int, default=8, help="Máximo de resultados (1-10)")
    parser.add_argument("--timeout", type=int, default=12, help="Tiempo máximo de espera en segundos")
    args = parser.parse_args()
    db = core.connect(args.db)
    try:
        core.init_db(db)
        print(json.dumps(run_search(db, args.query, args.limit, args.timeout), ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
