import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
CORE_SPEC = importlib.util.spec_from_file_location("nemesis_mvp", ROOT / "engine" / "nemesis_mvp.py")
core = importlib.util.module_from_spec(CORE_SPEC)
import sys
sys.modules["nemesis_mvp"] = core
CORE_SPEC.loader.exec_module(core)

RADAR_SPEC = importlib.util.spec_from_file_location("radar", ROOT / "engine" / "radar.py")
radar = importlib.util.module_from_spec(RADAR_SPEC)
RADAR_SPEC.loader.exec_module(radar)


class RadarTests(unittest.TestCase):
    def test_parser_keeps_multiple_results_and_snippets(self):
        html = """
        <a class="result__a" href="https://example.org/a">Fuente A</a>
        <div class="result__snippet">Primera pista</div>
        <a class="result__a" href="https://example.org/b">Fuente B</a>
        <div class="result__snippet">Segunda pista</div>
        """
        parser = radar._ResultsParser()
        parser.feed(html)
        parser.close()
        self.assertEqual(len(parser.results), 2)
        self.assertEqual(parser.results[0]["title"], "Fuente A")
        self.assertEqual(parser.results[0]["snippet"], "Primera pista")
        self.assertEqual(parser.results[1]["url"], "https://example.org/b")

    def test_search_rejects_empty_query_and_bad_limit(self):
        with self.assertRaises(ValueError):
            radar.search_web("  ")
        with self.assertRaises(ValueError):
            radar.search_web("cuidados", limit=11)

    def test_search_results_are_saved_as_unverified_hypotheses(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = core.connect(Path(tmp) / "radar.db")
            core.init_db(db)
            leads = [{"title": "Convocatoria ejemplo", "url": "https://example.org/convocatoria", "snippet": "Plazo abierto"}]
            with patch.object(radar, "search_web", return_value=leads):
                result = radar.run_search(db, "ayudas cuidados")
            self.assertEqual(result["result_count"], 1)
            row = db.execute("SELECT evidence_type, confidence, source_url, notes FROM evidence").fetchone()
            self.assertEqual(row["evidence_type"], "hypothesis")
            self.assertEqual(row["confidence"], 0.25)
            self.assertEqual(row["source_url"], leads[0]["url"])
            self.assertIn("NO es un hecho verificado", row["notes"])
            db.close()


if __name__ == "__main__":
    unittest.main()
