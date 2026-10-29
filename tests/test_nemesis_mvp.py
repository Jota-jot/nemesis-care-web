import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("nemesis_mvp", Path(__file__).parents[1] / "engine" / "nemesis_mvp.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

class NemesisCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = m.connect(Path(self.tmp.name) / "test.db")
        m.init_db(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_forecast_scoring_and_single_resolution(self):
        fid = m.add_forecast(self.db, "Evento verificable", "2027-01-01", 0.8, "Motivo", "Fuente oficial")
        score = m.resolve_forecast(self.db, fid, True, "https://example.org")
        self.assertAlmostEqual(score["brier"], 0.04)
        self.assertAlmostEqual(score["log_loss"], -__import__("math").log(0.8))
        with self.assertRaises(ValueError):
            m.resolve_forecast(self.db, fid, False, "otra fuente")

    def test_forecast_core_is_immutable(self):
        fid = m.add_forecast(self.db, "Pregunta", "2027-01-01", 0.5, "Motivo", "Regla")
        with self.assertRaises(Exception):
            self.db.execute("UPDATE forecasts SET p_yes=0.7 WHERE id=?", (fid,))
        self.db.rollback()

    def test_projected_income_is_not_cash(self):
        m.record_ledger(self.db, "income", "projected", 1000, "sales", "possible sale")
        m.record_ledger(self.db, "income", "collected", 100, "sales", "paid sale")
        m.record_ledger(self.db, "expense", "paid", 20, "api", "real cost")
        m.set_setting(self.db, "reserve_eur", 30)
        summary = m.financial_summary(self.db)
        self.assertEqual(summary["income_collected_eur"], 100)
        self.assertEqual(summary["income_projected_eur_not_cash"], 1000)
        self.assertEqual(summary["available_after_paid_committed_and_reserve_eur"], 50)

    def test_evidence_requires_valid_confidence(self):
        with self.assertRaises(Exception):
            m.add_evidence(self.db, "claim", "fact", 1.5)

if __name__ == "__main__":
    unittest.main()
