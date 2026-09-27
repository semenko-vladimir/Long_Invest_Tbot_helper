#!/usr/bin/env python3
"""Reproducible local-model benchmark for economic news analysis with a web dashboard.

The news items are synthetic and frozen. Results are comparable across models;
the dashboard is read-only and can be served over a LAN or on a separate host.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit

from agent_benchmark import (allow_sleep, discover, initial_options, lm_prepare, lm_unload,
                             log_event, memory_bytes, prevent_sleep, safe_name, unload_ollama,
                             utc_now, write_json)
from inspect_agent_models import api_json

HERE = Path(__file__).resolve().parent
DEFAULT_CASES = HERE / "economic_news_cases.json"


def public_cases(dataset: dict) -> list[dict]:
    return [{key: value for key, value in case.items() if key != "gold"}
            for case in dataset["cases"]]


def make_prompt(dataset: dict) -> str:
    return (
        "You are comparing fictional economic news releases. Use only the documents below. "
        "For every case, calculate the requested numeric value and select exactly one direction "
        "and one limit from that case's lists. Prefer primary documents over commentary. "
        "Return only a JSON object with an 'answers' array. Each answer must contain: "
        "id, direction, value (number), evidence (array of document IDs), limit, "
        "and explanation (one or two sentences). Do not give investment advice.\n\n"
        + json.dumps({"notice": dataset.get("notice", "Synthetic evaluation data"),
                      "cases": public_cases(dataset)},
                     ensure_ascii=False)
    )


def extract_json(value: str) -> dict | None:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        match = re.search(r"\{.*\}", value or "", re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except ValueError:
            return None
    return parsed if isinstance(parsed, dict) else None


def grade(dataset: dict, answer: dict | None) -> tuple[int, list[dict]]:
    entries = answer.get("answers") if isinstance(answer, dict) else None
    by_id = {item["id"]: item for item in entries
             if isinstance(item, dict) and isinstance(item.get("id"), str)} if isinstance(entries, list) else {}
    details = []
    total = 0
    for case in dataset["cases"]:
        submitted = by_id.get(case["id"], {})
        gold = case["gold"]
        try:
            numeric_ok = abs(float(submitted.get("value")) - gold["value"]) <= 0.11
        except (TypeError, ValueError, OverflowError):
            numeric_ok = False
        citations = submitted.get("evidence", [])
        source_ids = (set(item for item in citations if isinstance(item, str))
                      if isinstance(citations, list) else set())
        checks = {"direction": submitted.get("direction") == gold["direction"],
                  "value": numeric_ok,
                  "evidence": source_ids == set(gold["evidence"]),
                  "limit": submitted.get("limit") == gold["limit"]}
        points = 8 * checks["direction"] + 6 * checks["value"] + 5 * checks["evidence"] + 5 * checks["limit"]
        total += points
        details.append({"id": case["id"], "points": points, "max_points": 24,
                        "checks": checks, "expected": gold, "answer": submitted})
    return round(100 * total / (24 * len(dataset["cases"]))), details


def answer_complete(dataset: dict, answer: dict | None) -> bool:
    entries = answer.get("answers") if isinstance(answer, dict) else None
    expected = {case["id"] for case in dataset["cases"]}
    if not isinstance(entries, list) or len(entries) != len(expected):
        return False
    ids = [entry.get("id") for entry in entries if isinstance(entry, dict)]
    if len(ids) != len(entries) or not all(isinstance(item, str) for item in ids) or set(ids) != expected:
        return False
    for entry in entries:
        try:
            number = float(entry.get("value"))
        except (TypeError, ValueError, OverflowError):
            return False
        if not math.isfinite(number):
            return False
        if not all(isinstance(entry.get(key), str) and entry[key].strip()
                   for key in ("direction", "limit", "explanation")):
            return False
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
            return False
    return True


def next_news_options(model: dict, run: dict, attempts: list[dict]) -> tuple[dict | None, str]:
    last = attempts[-1]
    old = last["options"]
    seen = {json.dumps(a["options"], sort_keys=True) for a in attempts}

    def choose(reason: str, **changes: object) -> tuple[dict | None, str]:
        new = {**old, **changes}
        return (new, reason) if json.dumps(new, sort_keys=True) not in seen else (None, "Настройки уже проверены.")

    error = str(last.get("error", "")).lower()
    if last.get("status") == "error":
        if "timed out" in error or "timeout" in error:
            if "thinking" in model.get("capabilities", []) and old.get("think") is not False:
                return choose("Ответ не уложился в срок: проверяю без длительного thinking.", think=False)
            if old["num_predict"] > 768:
                return choose("Тайм-аут: уменьшаю предел генерации.",
                              num_predict=max(768, old["num_predict"] // 2))
            if model["backend"] == "ollama" and not old.get("format_json"):
                return choose("Тайм-аут: требую компактный JSON-ответ.", format_json=True)
            if old["num_ctx"] > 4096:
                return choose("Тайм-аут: уменьшаю контекст до необходимого объёма.",
                              num_ctx=max(4096, old["num_ctx"] // 2))
            return None, "Не удалось получить ответ в пределах 600 секунд."
        resource = any(x in error for x in ("memory", "allocate", "vulkan", "cuda", "gpu", "500"))
        if not resource:
            return None, "Ошибка не связана с ресурсами; повтор с другой температурой бесполезен."
        if model["backend"] == "ollama" and old.get("num_batch", 64) > 32:
            return choose("Сбой загрузки: уменьшаю batch.", num_batch=32)
        if model["backend"] == "ollama" and old.get("num_gpu") != 0:
            return choose("Сбой загрузки: пробую CPU.", num_gpu=0)
        if old["num_ctx"] > 2048:
            return choose("Сбой загрузки: уменьшаю контекст.", num_ctx=max(2048, old["num_ctx"] // 2))
        return None, "Модель не удалось загрузить даже с уменьшенным контекстом."
    if last.get("prompt_tokens", 0) > old["num_ctx"] * 0.85:
        native = model.get("native_context")
        ceiling = min(native, run["target_context"] * 2) if native else run["target_context"] * 2
        if old["num_ctx"] < ceiling:
            return choose("Новости почти заполнили контекст: увеличиваю окно.",
                          num_ctx=min(ceiling, int(old["num_ctx"] * 1.5)))
    if last.get("thinking_only") and "thinking" in model.get("capabilities", []) and old.get("think") is not False:
        return choose("Модель выдала только размышление: проверяю ответ без thinking.", think=False)
    if last.get("hit_output_limit") and old["num_predict"] < 8192:
        return choose("Ответ оборвался: увеличиваю лимит генерации.",
                      num_predict=min(8192, old["num_predict"] * 2))
    if not last.get("parsed") and model["backend"] == "ollama" and not old.get("format_json"):
        return choose("Ответ не был корректным JSON: включаю JSON-формат.", format_json=True)
    if "thinking" in model.get("capabilities", []) and old.get("think") is not True:
        return choose("Есть ошибки анализа: включаю thinking.", think=True)
    if old["temperature"] < 0.2:
        return choose("Есть ошибки анализа: пробую иную генерацию.", temperature=0.2)
    return None, "Полезные варианты настроек для этого задания исчерпаны."


def speed_options(model: dict, run: dict, attempts: list[dict]) -> tuple[dict, str]:
    valid = [item for item in attempts if item.get("valid")]
    fastest = min(valid, key=lambda item: item["elapsed_seconds"])
    base = fastest["options"]
    seen = {json.dumps(item["options"], sort_keys=True) for item in attempts}
    candidates = []
    if "thinking" in model.get("capabilities", []) and base.get("think") is not False:
        candidates.append(({**base, "think": False}, "Проверяю скорость без thinking."))
    output_tokens = int(fastest.get("output_tokens") or 0)
    if output_tokens and base["num_predict"] > max(768, int(output_tokens * 1.35)):
        candidates.append(({**base, "num_predict": max(768, int(output_tokens * 1.35))},
                           "Сокращаю лимит вывода по фактическому ответу."))
    prompt_tokens = int(fastest.get("prompt_tokens") or 0)
    minimum_context = max(4096, int((prompt_tokens + max(output_tokens * 2, 768)) * 1.25))
    if base["num_ctx"] > minimum_context:
        candidates.append(({**base, "num_ctx": minimum_context},
                           "Уменьшаю контекст с запасом для запроса и ответа."))
    if model["backend"] == "ollama" and base.get("num_batch", 64) != 128:
        candidates.append(({**base, "num_batch": 128}, "Проверяю больший batch."))
    for options, reason in candidates:
        if json.dumps(options, sort_keys=True) not in seen:
            return options, reason
    return dict(base), "Повторяю наиболее быструю успешную конфигурацию для проверки скорости."


def chat(model: dict, run: dict, options: dict, prompt: str) -> tuple[dict, dict]:
    if model["backend"] == "ollama":
        runtime = {key: value for key, value in options.items()
                   if key not in ("think", "format_json", "request_timeout")}
        payload = {"model": model["name"], "messages": [{"role": "user", "content": prompt}],
                   "stream": False, "keep_alive": "5m", "options": runtime}
        if "think" in options:
            payload["think"] = options["think"]
        if options.get("format_json"):
            payload["format"] = "json"
        data = api_json(run["ollama_url"], "/api/chat", payload,
                        timeout=options.get("request_timeout", run["request_timeout"]))
        return data.get("message") or {}, {key: data.get(key) for key in
                                           ("prompt_eval_count", "eval_count", "done_reason",
                                            "total_duration", "load_duration", "eval_duration")}
    payload = {"model": "news_benchmark_" + safe_name(model["name"])[:30],
               "messages": [{"role": "user", "content": prompt}], "stream": False,
               "temperature": options["temperature"], "max_tokens": options["num_predict"]}
    if options.get("format_json"):
        payload["response_format"] = {"type": "json_object"}
    data = api_json(run["lmstudio_url"], "/v1/chat/completions", payload,
                    timeout=options.get("request_timeout", run["request_timeout"]))
    choice = (data.get("choices") or [{}])[0]
    return choice.get("message") or {}, {**(data.get("usage") or {}),
                                          "done_reason": choice.get("finish_reason")}


def trial(model: dict, run: dict, dataset: dict, options: dict, number: int, events: Path) -> dict:
    started = time.monotonic()
    result = {"attempt": number, "options": options, "status": "error", "score": 0,
              "passed": False, "valid": False, "parsed": False, "prompt_tokens": 0}
    identifier = "news_benchmark_" + safe_name(model["name"])[:30]
    loaded = False
    try:
        if model["backend"] == "lmstudio":
            loaded, reason = lm_prepare(model["path"], identifier, options["num_ctx"], events)
            if not loaded:
                raise RuntimeError(reason)
        message, usage = chat(model, run, options, make_prompt(dataset))
        result["response"] = message
        result["usage"] = usage
        result["thinking_only"] = bool(message.get("thinking") and not message.get("content"))
        result["prompt_tokens"] = int(usage.get("prompt_eval_count") or usage.get("prompt_tokens") or 0)
        result["output_tokens"] = int(usage.get("eval_count") or usage.get("completion_tokens") or 0)
        eval_duration = usage.get("eval_duration")
        if eval_duration and result["output_tokens"]:
            result["tokens_per_second"] = round(result["output_tokens"] / (eval_duration / 1e9), 2)
        result["hit_output_limit"] = usage.get("done_reason") in ("length", "max_tokens") or (
            int(usage.get("eval_count") or usage.get("completion_tokens") or 0) >= options["num_predict"] - 16)
        answer = extract_json(message.get("content", ""))
        result["parsed"] = answer is not None
        result["answer"] = answer
        result["score"], result["cases"] = grade(dataset, answer)
        result["valid"] = answer_complete(dataset, answer)
        result["passed"] = result["score"] == 100
        result["status"] = "valid" if result["valid"] else "incomplete"
        log_event(events, "model_answer", attempt=number, response=message, usage=usage,
                  score=result["score"], cases=result["cases"])
    except (HTTPError, URLError, OSError, ValueError, RuntimeError) as error:
        body = error.read(3000).decode("utf-8", errors="replace") if isinstance(error, HTTPError) else ""
        result["error"] = f"{error}: {body}" if body else str(error)
        log_event(events, "attempt_error", attempt=number, error=result["error"])
    finally:
        result["elapsed_seconds"] = round(time.monotonic() - started, 1)
        if model["backend"] == "ollama":
            unload_ollama(run["ollama_url"], model["name"])
        elif loaded:
            lm_unload(identifier)
    return result


def worker(run_dir: Path, index: int) -> int:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    dataset = json.loads((run_dir / "cases.json").read_text(encoding="utf-8"))
    model = run["models"][index]
    folder = run_dir / "models" / safe_name(model["name"])
    folder.mkdir(parents=True, exist_ok=True)
    events = folder / "events.jsonl"
    partial = folder / "partial.json"
    attempts = (json.loads(partial.read_text(encoding="utf-8")).get("attempts", [])
                if partial.exists() else [])
    if model["backend"] == "ollama" and not model.get("capabilities"):
        final = {"model": model, "status": "skipped", "reason": "Нет метаданных модели", "attempts": []}
    else:
        first_valid = next((position for position, item in enumerate(attempts, 1)
                            if item.get("valid")), None)
        limit = min(run["max_attempts"] + run["speed_attempts"],
                    first_valid + run["speed_attempts"]) if first_valid else run["max_attempts"]
        while len(attempts) < limit:
            number = len(attempts) + 1
            if attempts and first_valid is None:
                options, decision = next_news_options(model, run, attempts)
                if options is None:
                    # No useful setting remains. A same-setting retry still counts toward five.
                    options = dict(attempts[-1]["options"])
                    decision = "Повторяю настройки: другие полезные варианты исчерпаны."
            elif first_valid is not None:
                options, decision = speed_options(model, run, attempts)
            else:
                options = initial_options(model, run["target_context"])
                decision = "Исходные настройки модели."
            log_event(events, "tuning_decision", attempt=number, reason=decision,
                      next_options=options)
            plan = folder / f"attempt_plan_{number}.json"
            output = folder / f"attempt_result_{number}.json"
            write_json(plan, {"options": options, "decision": decision})
            command = [sys.executable, str(Path(__file__).resolve()), "--trial-index", str(index),
                       "--trial-number", str(number), "--output-dir", str(run_dir)]
            started = time.monotonic()
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                stdout, stderr = process.communicate(timeout=run["request_timeout"])
                if process.returncode or not output.exists():
                    attempt = {"attempt": number, "options": options, "status": "error", "score": 0,
                               "valid": False, "error": (stderr or stdout or "Нет результата попытки")[-3000:],
                               "elapsed_seconds": round(time.monotonic() - started, 1)}
                else:
                    attempt = json.loads(output.read_text(encoding="utf-8"))
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    if process.stdout:
                        process.stdout.close()
                    if process.stderr:
                        process.stderr.close()
                attempt = {"attempt": number, "options": options, "status": "error", "score": 0,
                           "valid": False, "error": "Hard timeout: 600 seconds per attempt",
                           "elapsed_seconds": round(time.monotonic() - started, 1)}
                if model["backend"] == "ollama":
                    unload_ollama(run["ollama_url"], model["name"])
            attempt["tuning_decision"] = decision
            attempts.append(attempt)
            write_json(folder / "partial.json", {"model": model, "attempts": attempts})
            if first_valid is None and attempt.get("valid"):
                first_valid = number
                limit = min(run["max_attempts"] + run["speed_attempts"],
                            number + run["speed_attempts"])
        valid = [item for item in attempts if item.get("valid")]
        best = max(valid or attempts, key=lambda item: (item.get("score", 0),
                                                        -item.get("elapsed_seconds", float("inf"))), default=None)
        fastest = min(valid, key=lambda item: item["elapsed_seconds"], default=None)
        final = {"model": model, "status": "passed" if valid else "failed",
                 "best": best, "fastest_valid": fastest, "first_valid_attempt": first_valid,
                 "attempts": attempts}
    write_json(folder / "result.json", final)
    return 0


def trial_worker(run_dir: Path, index: int, number: int) -> int:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    dataset = json.loads((run_dir / "cases.json").read_text(encoding="utf-8"))
    model = run["models"][index]
    folder = run_dir / "models" / safe_name(model["name"])
    plan = json.loads((folder / f"attempt_plan_{number}.json").read_text(encoding="utf-8"))
    result = trial(model, run, dataset, plan["options"], number, folder / "events.jsonl")
    write_json(folder / f"attempt_result_{number}.json", result)
    return 0


def summarize(run_dir: Path) -> dict:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    ranking = []
    for model in run["models"]:
        folder = run_dir / "models" / safe_name(model["name"])
        result_path = folder / "result.json"
        partial = folder / "partial.json"
        result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else (
            json.loads(partial.read_text(encoding="utf-8")) if partial.exists() else {})
        attempts = result.get("attempts", [])
        valid = [item for item in attempts if item.get("valid")]
        best = result.get("best") or max(valid or attempts,
                                         key=lambda item: item.get("score", 0), default={})
        fastest = min(valid, key=lambda item: item.get("elapsed_seconds", float("inf")), default={})
        ranking.append({"name": model["name"], "slug": safe_name(model["name"]),
                        "status": result.get("status", "pending"), "score": best.get("score", 0),
                        "settings": best.get("options"), "attempts": len(attempts),
                        "valid_attempts": len(valid), "fastest_seconds": fastest.get("elapsed_seconds"),
                        "fastest_score": fastest.get("score"), "fastest_settings": fastest.get("options"),
                        "tokens_per_second": fastest.get("tokens_per_second"),
                        "elapsed_seconds": sum(a.get("elapsed_seconds", 0) for a in attempts),
                        "reason": result.get("reason") or best.get("error", "")})
    ranking.sort(key=lambda row: (row["status"] == "passed", row["score"],
                                  -(row["fastest_seconds"] or float("inf"))), reverse=True)
    top_score = ranking[0]["score"] if ranking and ranking[0]["status"] == "passed" else 0
    leaders = [row["name"] for row in ranking if top_score and
               row["status"] == "passed" and row["score"] == top_score]
    summary = {"title": "Экономический анализ новостей", "updated_at": utc_now(),
               "dataset": run["dataset_title"], "synthetic": True,
               "running": not all(row["status"] not in ("pending", "interrupted") for row in ranking),
               "models_total": len(ranking), "models_finished": sum(row["status"] not in ("pending", "interrupted") for row in ranking),
               "leaders": leaders, "ranking": ranking}
    write_json(run_dir / "summary.json", summary)
    lines = ["# Бенчмарк экономического анализа новостей", "",
             "Все новости в наборе вымышлены. Рейтинг относится только к этим заданиям.",
             f"Набор: {run['dataset_title']}. Обновлён: {summary['updated_at']}.",
             "Оцениваются направление эффекта, расчёт, источники и предел вывода.", "",
             "| Место | Модель | Лучшее качество | Самый быстрый полный ответ | Качество быстрого | Статус | Попыток | Настройки лучшего качества |",
             "| ---: | --- | ---: | ---: | ---: | --- | ---: | --- |"]
    for index, row in enumerate(ranking, 1):
        settings = json.dumps(row["settings"], ensure_ascii=False) if row["settings"] else "—"
        speed = f"{row['fastest_seconds']} с" if row["fastest_seconds"] is not None else "—"
        lines.append(f"| {index} | {row['name'].replace('|', '/')} | {row['score']} | "
                     f"{speed} | {row['fastest_score'] if row['fastest_score'] is not None else '—'} | "
                     f"{row['status']} | {row['attempts']} | `{settings}` |")
    if leaders:
        lines += ["", "Лидеры с одинаковым баллом: " + ", ".join(leaders) + "."]
    lines += ["", "Подробные ответы, оценки по заданиям и причины подбора настроек "
              "находятся в `models/<модель>/result.json` и `events.jsonl`."]
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    review = ["# Ответы моделей для ручной проверки", "",
              "Сводка по вымышленным новостям. Автоматическая оценка проверяет только поля "
              "direction, value, evidence и limit; текст explanation стоит проверить отдельно.", ""]
    for row in ranking:
        folder = run_dir / "models" / row["slug"]
        result_path = folder / "result.json"
        partial_path = folder / "partial.json"
        source = result_path if result_path.exists() else partial_path
        result = json.loads(source.read_text(encoding="utf-8")) if source.exists() else {}
        best = result.get("best") or max(result.get("attempts", []),
                                         key=lambda item: item.get("score", 0), default={})
        review += [f"## {row['name']}: {row['score']}/100", "",
                   f"Статус: {row['status']}. Настройки лучшей попытки: "
                   f"`{json.dumps(best.get('options'), ensure_ascii=False)}`.", ""]
        if row["fastest_seconds"] is not None:
            review += [f"Самый быстрый полный ответ: {row['fastest_seconds']} с, "
                       f"качество {row['fastest_score']}/100; настройки "
                       f"`{json.dumps(row['fastest_settings'], ensure_ascii=False)}`.", ""]
        for attempt in result.get("attempts", []):
            review.append(f"- Попытка {attempt['attempt']}: {attempt.get('score', 0)}/100; "
                          f"{attempt.get('elapsed_seconds', '—')} с; "
                          f"полный ответ: {'да' if attempt.get('valid') else 'нет'}; "
                          f"{attempt.get('tokens_per_second', '—')} ток/с; "
                          f"настройки `{json.dumps(attempt.get('options'), ensure_ascii=False)}`; "
                          f"{attempt.get('tuning_decision', '')}; {attempt.get('error', '')}")
        review.append("")
        for case in best.get("cases", []):
            review += [f"### {case['id']}: {case['points']}/{case['max_points']}", "",
                       "Проверки: `" + json.dumps(case["checks"], ensure_ascii=False) + "`.",
                       "Ответ: `" + json.dumps(case["answer"], ensure_ascii=False) + "`.",
                       "Ожидалось: `" + json.dumps(case["expected"], ensure_ascii=False) + "`.", ""]
        if best.get("error"):
            review += ["Ошибка: `" + str(best["error"]).replace("`", "'") + "`.", ""]
    (run_dir / "review.md").write_text("\n".join(review) + "\n", encoding="utf-8")
    return summary


class Dashboard(BaseHTTPRequestHandler):
    run_dir: Path

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            self.send_content(b"ok", "text/plain; charset=utf-8")
            return
        if path == "/api/summary":
            summary = self.run_dir / "summary.json"
            self.send_content(summary.read_bytes() if summary.exists() else b"{}", "application/json; charset=utf-8")
            return
        if path == "/report/summary.md":
            report = self.run_dir / "summary.md"
            self.send_content(report.read_bytes() if report.exists() else b"", "text/markdown; charset=utf-8")
            return
        if path == "/report/review.md":
            report = self.run_dir / "review.md"
            self.send_content(report.read_bytes() if report.exists() else b"", "text/markdown; charset=utf-8")
            return
        if path.startswith("/model/"):
            slug = unquote(path.removeprefix("/model/"))
            run = json.loads((self.run_dir / "run.json").read_text(encoding="utf-8"))
            model = next((m for m in run["models"] if safe_name(m["name"]) == slug), None)
            if model is None:
                self.send_error(404)
                return
            result = self.run_dir / "models" / slug / "result.json"
            partial = self.run_dir / "models" / slug / "partial.json"
            data = result if result.exists() else partial
            body = (f"<h1>{html.escape(model['name'])}</h1><p><a href='/'>← К рейтингу</a></p>"
                    + ("<pre>" + html.escape(data.read_text(encoding="utf-8")) + "</pre>"
                       if data.exists() else "<p>Ожидает запуска.</p>"))
            self.send_content(self.page(body).encode(), "text/html; charset=utf-8")
            return
        if path != "/":
            self.send_error(404)
            return
        summary_file = self.run_dir / "summary.json"
        summary = json.loads(summary_file.read_text(encoding="utf-8")) if summary_file.exists() else {"ranking": []}
        state_file = self.run_dir / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
        phase = {"waiting": "ожидание", "running": "тестируется", "cooldown": "охлаждение",
                 "complete": "завершено", "interrupted": "прервано"}.get(
                     state.get("phase", "waiting"), state.get("phase", "waiting"))
        current = state.get("current_model") or state.get("after_model") or "—"
        rows = "".join(
            f"<tr><td>{index}</td><td><a href='/model/{html.escape(row['slug'])}'>{html.escape(row['name'])}</a></td>"
            f"<td>{row['score']}</td><td>{row['fastest_seconds'] if row['fastest_seconds'] is not None else '—'}</td>"
            f"<td>{row['fastest_score'] if row['fastest_score'] is not None else '—'}</td>"
            f"<td>{html.escape(row['status'])}</td><td>{row['attempts']}</td></tr>"
            for index, row in enumerate(summary["ranking"], 1))
        body = ("<h1>Экономический анализ новостей</h1>"
                "<p class='notice'>Вымышленные новости. Рейтинг показывает качество на фиксированных заданиях.</p>"
                f"<p>Завершено: {summary.get('models_finished', 0)} / {summary.get('models_total', 0)}. "
                f"Состояние: {html.escape(phase)}; модель: {html.escape(current)}. "
                f"Обновлено: {html.escape(summary.get('updated_at', '—'))}.</p>"
                "<p><a href='/report/summary.md'>Рейтинг Markdown</a> · "
                "<a href='/report/review.md'>Ответы для Codex</a></p>"
                "<table><thead><tr><th>№</th><th>Модель</th><th>Лучший балл</th><th>Быстрый ответ, с</th><th>Балл быстрого</th><th>Статус</th><th>Попытки</th></tr></thead>"
                f"<tbody>{rows}</tbody></table><p>Страница обновляется каждые 30 секунд.</p>")
        self.send_content(self.page(body, refresh=True).encode(), "text/html; charset=utf-8")

    def page(self, body: str, refresh: bool = False) -> str:
        meta = '<meta http-equiv="refresh" content="30">' if refresh else ""
        return ("<!doctype html><html lang='ru'><head><meta charset='utf-8'>" + meta +
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>Бенчмарк новостей</title><style>body{font:16px system-ui;margin:3rem auto;"
                "max-width:1100px;padding:0 1rem;background:#f7f8fa;color:#17212d}a{color:#1765b3}"
                "table{border-collapse:collapse;width:100%;background:white}th,td{padding:.7rem;border-bottom:1px solid #ddd;text-align:left}"
                ".notice{background:#fff4d6;padding:1rem;border-radius:.5rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;"
                "background:#fff;padding:1rem;border:1px solid #ddd}</style></head><body>" + body + "</body></html>")

    def send_content(self, data: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def run_benchmark(run_dir: Path, retry_timeouts: bool = False,
                  selected: set[str] | None = None) -> None:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    prevent_sleep()
    try:
        for index, model in enumerate(run["models"]):
            if selected and model["name"] not in selected:
                continue
            folder = run_dir / "models" / safe_name(model["name"])
            result_path = folder / "result.json"
            if result_path.exists():
                previous = json.loads(result_path.read_text(encoding="utf-8"))
                if not retry_timeouts or previous.get("status") != "timeout":
                    continue
                log_event(run_dir / "run_events.jsonl", "retry_timeout", model=model["name"])
            print(f"[{index + 1}/{len(run['models'])}] {model['name']}", flush=True)
            write_json(run_dir / "state.json", {"phase": "running", "current_model": model["name"],
                                                "started_at": utc_now()})
            command = [sys.executable, str(Path(__file__).resolve()), "--worker-index", str(index),
                       "--output-dir", str(run_dir)]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                stdout, stderr = process.communicate(timeout=run["model_timeout"])
                if process.returncode:
                    folder.mkdir(parents=True, exist_ok=True)
                    write_json(folder / "result.json", {"model": model, "status": "worker_error",
                               "reason": (stderr or stdout)[-3000:], "attempts": []})
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    # A descendant may still hold a pipe open after the worker is killed.
                    if process.stdout:
                        process.stdout.close()
                    if process.stderr:
                        process.stderr.close()
                folder.mkdir(parents=True, exist_ok=True)
                partial = folder / "partial.json"
                attempts = json.loads(partial.read_text(encoding="utf-8")).get("attempts", []) if partial.exists() else []
                write_json(folder / "result.json", {"model": model, "status": "timeout",
                           "reason": f"Лимит {run['model_timeout']} с", "attempts": attempts})
                if model["backend"] == "ollama":
                    unload_ollama(run["ollama_url"], model["name"])
            except KeyboardInterrupt:
                process.kill()
                try:
                    process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    if process.stdout:
                        process.stdout.close()
                    if process.stderr:
                        process.stderr.close()
                if model["backend"] == "ollama":
                    unload_ollama(run["ollama_url"], model["name"])
                raise
            summarize(run_dir)
            pending = any(not (run_dir / "models" / safe_name(next_model["name"]) /
                               "result.json").exists() for next_model in run["models"][index + 1:])
            if pending and run["cooldown_seconds"]:
                print(f"Пауза для охлаждения: {run['cooldown_seconds']} с", flush=True)
                write_json(run_dir / "state.json", {"phase": "cooldown", "after_model": model["name"],
                                                    "seconds": run["cooldown_seconds"], "started_at": utc_now()})
                log_event(run_dir / "run_events.jsonl", "cooldown_start", after_model=model["name"])
                time.sleep(run["cooldown_seconds"])
                log_event(run_dir / "run_events.jsonl", "cooldown_end", after_model=model["name"])
        write_json(run_dir / "state.json", {"phase": "complete", "updated_at": utc_now()})
    finally:
        summarize(run_dir)
        allow_sleep()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="show a read-only dashboard while benchmarking")
    parser.add_argument("--view-only", action="store_true", help="serve an existing run without starting models")
    parser.add_argument("--prepare-only", action="store_true", help="create a run without starting models")
    parser.add_argument("--retry-timeouts", action="store_true", help="continue timed-out models on --resume")
    parser.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 for access from other machines")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", action="append", default=[])
    parser.add_argument("--cases-file", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--target-context", type=int, default=8192)
    parser.add_argument("--max-attempts", type=int, default=5, help="attempts to obtain a complete answer; must be 5")
    parser.add_argument("--model-timeout", type=int, help="seconds per model; default 6300")
    parser.add_argument("--request-timeout", type=int, help="seconds per attempt; must be 600")
    parser.add_argument("--cooldown-seconds", type=int, default=600)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--lmstudio-url", default="http://127.0.0.1:1234")
    parser.add_argument("--lmstudio-dir", type=Path, default=Path.home() / ".lmstudio" / "models")
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--trial-index", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--trial-number", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.trial_index is not None:
        if not args.output_dir or args.trial_number is None:
            parser.error("trial needs --output-dir and --trial-number")
        return trial_worker(args.output_dir, args.trial_index, args.trial_number)
    if args.worker_index is not None:
        if not args.output_dir:
            parser.error("worker needs --output-dir")
        return worker(args.output_dir, args.worker_index)
    if args.target_context < 2048 or args.max_attempts != 5 or args.cooldown_seconds < 0:
        parser.error("invalid context, attempts or cooldown")
    if args.view_only and (not args.serve or not args.resume):
        parser.error("--view-only requires --serve and --resume")
    if args.prepare_only and (args.serve or args.resume):
        parser.error("--prepare-only creates a new run without --serve or --resume")
    if args.retry_timeouts and not args.resume:
        parser.error("--retry-timeouts requires --resume")
    if (args.model_timeout is not None and args.model_timeout < 6300) or (
            args.request_timeout is not None and args.request_timeout != 600):
        parser.error("use 600 seconds per attempt and at least 6300 seconds per model")
    if args.resume:
        run_dir = args.resume.resolve()
        if not (run_dir / "run.json").exists():
            parser.error("--resume needs a run.json directory")
        run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        missing = set(args.model) - {model["name"] for model in run["models"]}
        if missing:
            parser.error("models not in saved run: " + ", ".join(sorted(missing)))
        if args.model_timeout is not None or args.request_timeout is not None:
            if args.model_timeout is not None:
                run["model_timeout"] = args.model_timeout
            if args.request_timeout is not None:
                run["request_timeout"] = args.request_timeout
            write_json(run_dir / "run.json", run)
    else:
        dataset = json.loads(args.cases_file.read_text(encoding="utf-8"))
        if not dataset.get("cases") or any("gold" not in case for case in dataset["cases"]):
            parser.error("cases file must contain cases with gold answers")
        models = discover(args.ollama_url, args.lmstudio_dir, args.model)
        if not models:
            parser.error("no downloaded models found")
        run_dir = (args.output_dir or Path.home() / "economic-news-reports" /
                   datetime.now().strftime("%Y%m%d_%H%M%S")).resolve()
        if run_dir.exists() and any(run_dir.iterdir()):
            parser.error("output directory is not empty; use --resume")
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "models").mkdir(exist_ok=True)
        write_json(run_dir / "cases.json", dataset)
        ram_total, ram_free = memory_bytes()
        run = {"created_at": utc_now(), "dataset_title": dataset.get("title", "custom"),
               "models": models, "target_context": args.target_context,
               "max_attempts": args.max_attempts, "speed_attempts": 5,
               "model_timeout": args.model_timeout or 6300,
               "request_timeout": args.request_timeout or 600, "cooldown_seconds": args.cooldown_seconds,
               "ollama_url": args.ollama_url, "lmstudio_url": args.lmstudio_url,
               "ram_total": ram_total, "ram_free_at_start": ram_free}
        write_json(run_dir / "run.json", run)
        write_json(run_dir / "state.json", {"phase": "waiting", "updated_at": utc_now()})
    summarize(run_dir)
    if args.prepare_only:
        print(f"Подготовлено: {run_dir}", flush=True)
        return 0
    server = None
    if args.serve:
        handler = type("RunDashboard", (Dashboard,), {"run_dir": run_dir})
        server = ThreadingHTTPServer((args.host, args.port), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"Панель: http://{args.host}:{args.port}/", flush=True)
    print(f"Отчёт: {run_dir / 'summary.md'}", flush=True)
    try:
        if not args.view_only:
            run_benchmark(run_dir, retry_timeouts=args.retry_timeouts,
                          selected=set(args.model) if args.model else None)
        if server:
            print("Панель открыта. Ctrl+C завершит сервер.", flush=True)
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        write_json(run_dir / "state.json", {"phase": "interrupted", "updated_at": utc_now()})
        print("Остановлено. Продолжение: --resume " + str(run_dir), file=sys.stderr)
        return 130
    finally:
        if server:
            server.shutdown()
            server.server_close()
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    raise SystemExit(main())
