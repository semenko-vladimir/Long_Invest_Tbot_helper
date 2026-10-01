import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.backend.models.accounts import BrokerConnection, InvestmentAccount, PortfolioSnapshot, PositionSnapshot
from app.backend.models.database import Base
from app.services.accounts import InvestmentAccountContext, StrategyProfileContext
from app.services.news_analysis import ModelNewsPrefilter
from app.services.news_llm_config import NewsLLMConfig
from app.services.news_sources import NewsItem
from app.services.ollama_news_analysis import NewsAnalysisUnavailable, OllamaNewsAnalyzer, _plain_summary
from app.services.user_context import UserContext


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"done": True, "message": {"content": json.dumps(self.content, ensure_ascii=False)}}


class FakeHTTP:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []
        self.trust_env = True

    def post(self, url, *, json, timeout):
        self.calls.append((url, json, timeout))
        if self.error:
            raise self.error
        result = self.result(json) if callable(self.result) else self.result
        return FakeResponse(result)


class OllamaNewsAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        self.user = UserContext("u", "User", 123, 0.3, "unused")
        self.item = NewsItem("cbr_press", "ЦБ повысил ключевую ставку", "https://www.cbr.ru/press/42",
                             datetime.now(timezone.utc), "Банк России повысил ставку до 18 процентов.")
        with self.factory() as db:
            connection = BrokerConnection(provider_key="t-invest", connection_key="default", display_name="T-Invest")
            db.add(connection)
            db.flush()
            for index in (1, 2):
                db.add(InvestmentAccount(broker_connection_id=connection.id, external_account_id=str(index),
                                         display_name=f"Счёт {index}", status="open", enabled=True))
            db.flush()
            snapshot = PortfolioSnapshot(investment_account_id=1, captured_at=datetime.now(timezone.utc).replace(tzinfo=None),
                                         total_value=1000, currency="RUB", source="test")
            db.add(snapshot)
            db.flush()
            db.add(PositionSnapshot(portfolio_snapshot_id=snapshot.id, investment_account_id=1,
                                    ticker="SBER", quantity=2, currency="RUB"))
            db.commit()

    def tearDown(self):
        self.engine.dispose()

    def account(self, account_id):
        strategy = StrategyProfileContext(account_id, "Рост" if account_id == 1 else "Доход",
                                          None, "Акции" if account_id == 1 else "Облигации", {}, None)
        return InvestmentAccountContext(self.user.user_id, account_id, 1, "t-invest", "default",
                                        str(account_id), f"Счёт {account_id}", None, "open", None, strategy)

    def result(self, account_id=1, *, impact="unknown", **changes):
        value = {
            "investment_account_id": account_id,
            "relevant": True,
            "impact": impact,
            "reason": "Может изменить оценку риска счёта.",
            "fact_ids": ["headline", "summary"],
            "uncertainty": "Полный текст публикации не проверен.",
            "insufficient_data": impact == "unknown",
            "source_url": self.item.url,
        }
        value.update(changes)
        return value

    def test_same_news_can_produce_account_specific_results(self):
        def answer(request):
            account_id = json.loads(request["messages"][1]["content"])["investment_account"]["id"]
            return self.result(account_id, impact="positive" if account_id == 1 else "negative")

        http = FakeHTTP(answer)
        config = NewsLLMConfig(enabled=True)
        analyzer = OllamaNewsAnalyzer(config, self.factory, self.user, http_session=http)
        first = analyzer.assess(self.item, {"SBER": "Сбербанк"}, (self.account(1),))
        second = analyzer.assess(self.item, {}, (self.account(2),))
        self.assertEqual((first.analysis.impact, second.analysis.impact), ("positive", "negative"))
        self.assertEqual((first.analysis.investment_account_id, second.analysis.investment_account_id), (1, 2))
        self.assertTrue(first.important and second.important)
        self.assertIn("состав счёта неизвестен", second.analysis.limitations[1])
        first_input = json.loads(http.calls[0][1]["messages"][1]["content"])
        second_input = json.loads(http.calls[1][1]["messages"][1]["content"])
        self.assertTrue(any(fact["id"] == "position_1" for fact in first_input["available_facts"]))
        self.assertFalse(any(fact["id"].startswith("position_") for fact in second_input["available_facts"]))
        self.assertEqual(first_input["investment_account"]["positions_status"], "snapshot_available")
        self.assertEqual(second_input["investment_account"]["positions_status"], "unknown")
        self.assertTrue(any(fact["id"] == "positions_unknown" for fact in second_input["available_facts"]))
        self.assertEqual(http.calls[0][0], "http://127.0.0.1:11434/api/chat")
        self.assertEqual(http.calls[0][2], (5, 420))
        self.assertEqual(http.calls[0][1]["options"],
                         {"num_ctx": 8192, "num_batch": 64, "num_predict": 2048, "temperature": 0})
        self.assertIs(http.calls[0][1]["think"], False)
        self.assertIs(http.trust_env, False)

    def test_invalid_response_is_rejected(self):
        invalid = [
            self.result(2),
            self.result(fact_ids=["unknown_fact"]),
            self.result(source_url="https://example.com/other"),
            self.result(impact="positive", insufficient_data=True),
            self.result(reason=""),
        ]
        for value in invalid:
            with self.subTest(value=value):
                analyzer = OllamaNewsAnalyzer(NewsLLMConfig(enabled=True), self.factory, self.user,
                                              http_session=FakeHTTP(value))
                with self.assertRaises(NewsAnalysisUnavailable):
                    analyzer.assess(self.item, {}, (self.account(1),))

    def test_headline_alone_cannot_claim_direction(self):
        headline_only = NewsItem(self.item.source, self.item.title, self.item.url, self.item.published_at)
        response = self.result(impact="positive", fact_ids=["headline"], insufficient_data=False)
        analyzer = OllamaNewsAnalyzer(NewsLLMConfig(enabled=True), self.factory, self.user,
                                      http_session=FakeHTTP(response))
        with self.assertRaises(NewsAnalysisUnavailable):
            analyzer.assess(headline_only, {}, (self.account(1),))

    def test_official_article_text_allows_cited_direction_without_rss_summary(self):
        item = NewsItem(self.item.source, self.item.title, self.item.url, self.item.published_at,
                        full_text="Банк России повысил ключевую ставку до 18 процентов.")
        response = self.result(impact="negative", fact_ids=["headline", "article_text"],
                               insufficient_data=False)
        http = FakeHTTP(response)
        analyzer = OllamaNewsAnalyzer(NewsLLMConfig(enabled=True), self.factory, self.user,
                                      http_session=http)
        assessment = analyzer.assess(item, {}, (self.account(1),))
        payload = json.loads(http.calls[0][1]["messages"][1]["content"])
        self.assertEqual(assessment.analysis.evidence_scope, "official_article")
        self.assertIn("article_text", [fact["id"] for fact in payload["available_facts"]])
        self.assertNotIn("полный текст не проверен", assessment.analysis.limitations[0])

    def test_timeout_and_wrong_account_context_fail(self):
        http = FakeHTTP(error=requests.Timeout("local model timeout"))
        analyzer = OllamaNewsAnalyzer(NewsLLMConfig(enabled=True), self.factory, self.user, http_session=http)
        with self.assertRaises(NewsAnalysisUnavailable):
            analyzer.assess(self.item, {}, (self.account(1),))
        other = InvestmentAccountContext("another-user", 1, 1, "t-invest", "default", "1", "Other",
                                         None, "open", None)
        with self.assertRaises(ValueError):
            analyzer.assess(self.item, {}, (other,))
        self.assertEqual(len(http.calls), 1)

    def test_config_defaults_off_and_rejects_nonlocal_endpoint(self):
        with patch.dict("os.environ", {"NEWS_LLM_ENABLED": "false"}, clear=True):
            self.assertFalse(NewsLLMConfig.from_env().enabled)
        with patch.dict("os.environ", {"NEWS_LLM_ENABLED": "true", "NEWS_OLLAMA_BASE_URL": "https://example.com:11434"}, clear=True):
            with self.assertRaises(ValueError):
                NewsLLMConfig.from_env()
        self.assertNotEqual(NewsLLMConfig(model="model-a").analyzer_version,
                            NewsLLMConfig(model="model-b").analyzer_version)

    def test_rss_summary_html_is_reduced_to_plain_text(self):
        summary = '<p>Ставка&nbsp;18%.</p><script>ignore me</script><p>Проверка <b>риска</b>.</p>'
        self.assertEqual(_plain_summary(summary), "Ставка 18%. Проверка риска.")

    def test_model_prefilter_skips_routine_moex_items_but_keeps_account_and_market_news(self):
        prefilter = ModelNewsPrefilter()
        routine = NewsItem("moex_listing", "О регистрации выпуска биржевых облигаций",
                           "https://www.moex.com/news/1", self.item.published_at)
        self.assertFalse(prefilter.assess(routine, {}, (self.account(1),)).important)
        self.assertTrue(prefilter.assess(routine, {}, ()).important)  # Rules remain available without an account.
        mentioned = NewsItem("moex_listing", routine.title, routine.url, routine.published_at,
                             "Публикация касается SBER")
        self.assertEqual(prefilter.assess(mentioned, {"SBER": "Сбербанк"}, (self.account(1),)).ticker,
                         "SBER")
        ordinary_halt = NewsItem("moex_main", "О приостановке торгов ценными бумагами",
                                 "https://www.moex.com/news/2", self.item.published_at)
        self.assertTrue(prefilter.assess(ordinary_halt, {}, (self.account(1),)).important)
        self.assertTrue(prefilter.needs_security_match(ordinary_halt))
        critical = NewsItem("moex_main", "О приостановке всех торгов на рынке",
                            "https://www.moex.com/news/2", self.item.published_at)
        self.assertTrue(prefilter.assess(critical, {}, (self.account(1),)).important)
        self.assertTrue(prefilter.assess(self.item, {}, (self.account(1),)).important)


if __name__ == "__main__":
    unittest.main()
