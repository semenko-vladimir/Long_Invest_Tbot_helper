#!/usr/bin/env python3
"""Overnight, resumable benchmark of downloaded models for large-file agent edits.

Runs one model at a time against an in-memory synthetic file. It never edits a
real repository. The run folder retains a fixture, per-attempt event logs,
machine-readable results and a Markdown ranking for later Codex review.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

from inspect_agent_models import api_json, declared_context, memory_bytes, native_context, weight_key

HERE = Path(__file__).resolve().parent
OLD_A = "    return total / count"
NEW_A = "    return total / count if count else 0"
OLD_B = "    return value.strip()"
NEW_B = '    return value.strip() if value is not None else ""'
TASK = (
    "First call read_file on virtual_large_module.py. Then use replace_line to make "
    "exactly these two changes and no others: in normalized_average replace "
    f"{OLD_A!r} with {NEW_A!r}; in clean_label replace {OLD_B!r} with {NEW_B!r}. "
    "The functions are far apart in a large file. Preserve the rest of the file. "
    "Do not claim success before both edit tools report success."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_name(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:55]
    return f"{stem}_{hashlib.sha256(name.encode()).hexdigest()[:8]}"


def write_json(path: Path, value: object) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def log_event(path: Path, kind: str, **fields: object) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at": utc_now(), "kind": kind, **fields}, ensure_ascii=False) + "\n")


def make_fixture(n: int) -> str:
    lines = ["START_MARKER = 'preserve-me'"]
    for index in range(n):
        lines.append(f"CONSTANT_{index:05d} = {index}")
        if index == n // 5:
            lines += ["", "def normalized_average(total, count):", OLD_A, ""]
        if index == 4 * n // 5:
            lines += ["", "def clean_label(value):", OLD_B, ""]
    lines += ["END_MARKER = 'preserve-me'", ""]
    return "\n".join(lines)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file in the virtual workspace. Required before editing.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replace_line",
            "description": "Replace one exact line in a virtual file without changing other lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_line": {"type": "string"},
                    "new_line": {"type": "string"},
                },
                "required": ["path", "old_line", "new_line"],
            },
        },
    },
]


def parse_arguments(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


def initial_options(model: dict, target: int) -> dict:
    native = model.get("native_context")
    return {"num_ctx": min(target, native) if native else target,
            "num_batch": 64, "num_predict": 2048, "temperature": 0}


def next_options(model: dict, run: dict, attempts: list[dict]) -> tuple[dict | None, str]:
    """Choose the next distinct configuration from the observed failure, not a preset list."""
    last = attempts[-1]
    old = last["options"]
    target = run["target_context"]
    native = model.get("native_context")
    max_context = min(native, target * 2) if native else target * 2
    tried = {json.dumps(a["options"], sort_keys=True) for a in attempts}

    def candidate(reason: str, **changes: object) -> tuple[dict | None, str]:
        new = {**old, **changes}
        if json.dumps(new, sort_keys=True) in tried:
            return None, ""
        return new, reason

    error = str(last.get("error", "")).lower()
    resource_error = any(word in error for word in
                         ("memory", "allocate", "allocation", "cuda", "vulkan", "gpu",
                          "insufficient", "resource exhausted", "out of memory", "500"))
    if last.get("status") == "error":
        if resource_error:
            if model["backend"] == "ollama" and old.get("num_batch", 64) > 32:
                return candidate("Ошибка памяти/загрузки: уменьшаю batch.", num_batch=32)
            if model["backend"] == "ollama" and old.get("num_gpu") != 0:
                return candidate("Ошибка памяти/загрузки: пробую CPU.", num_gpu=0)
            if old["num_ctx"] > 2048:
                return candidate("Даже на CPU не загрузилась: проверяю меньший контекст (вне зачёта, если ниже цели).",
                                 num_ctx=max(2048, old["num_ctx"] // 2))
        return None, "Ошибка не похожа на нехватку ресурсов; настройками генерации её не исправить."

    if last.get("passed"):
        return None, "Задание и целевой контекст пройдены."
    if native and native < target:
        return None, "Заявленный максимум контекста модели меньше целевого."
    if last.get("score") == 100 and not last.get("context_exercised", False):
        return None, "Файл слишком мал для целевой доли контекста; нужен больший --fixture-lines."

    context = last.get("actual_context") or old["num_ctx"]
    near_limit = last.get("prompt_tokens", 0) >= int(context * 0.85)
    if (near_limit or not last.get("context_meets_target", True)) and old["num_ctx"] < max_context:
        grown = min(max_context, max(old["num_ctx"] + 2048, int(old["num_ctx"] * 1.5)))
        if grown > old["num_ctx"]:
            return candidate("Запрос приблизился к пределу контекста: увеличиваю окно.", num_ctx=grown)

    if last.get("thinking_only") and model["backend"] == "ollama" and "thinking" in model.get("capabilities", []):
        if old.get("think") is not False:
            return candidate("Ответ оборвался на размышлении: отключаю thinking для пробы.", think=False)

    output_limit = last.get("hit_output_limit") or last.get("thinking_only")
    if output_limit and old["num_predict"] < 8192:
        return candidate("Ответ не дошёл до вызова инструмента: увеличиваю лимит генерации.",
                         num_predict=min(8192, old["num_predict"] * 2))

    if last.get("score", 0) < 100 and old["temperature"] < 0.2:
        return candidate("Контекст поместился, но правки не выполнены: пробую другую генерацию.",
                         temperature=0.2)
    if last.get("score", 0) < 100 and old["temperature"] < 0.4:
        return candidate("Повторная неудача правок: ещё одна генерация с умеренной температурой.",
                         temperature=0.4)
    return None, "Доступные изменения настроек исчерпаны."


def ollama_chat(base: str, name: str, messages: list[dict], options: dict, timeout: int) -> tuple[dict, dict]:
    generation = {key: value for key, value in options.items() if key != "think"}
    payload = {"model": name, "messages": messages, "tools": TOOLS,
               "stream": False, "keep_alive": "5m", "options": generation}
    if "think" in options:
        payload["think"] = options["think"]
    data = api_json(
        base, "/api/chat", payload,
        timeout=timeout,
    )
    return data.get("message") or {}, {
        key: data.get(key) for key in
        ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration",
         "eval_count", "eval_duration", "done_reason")
    }


def lm_chat(base: str, name: str, messages: list[dict], options: dict, timeout: int) -> tuple[dict, dict]:
    data = api_json(
        base, "/v1/chat/completions",
        {"model": name, "messages": messages, "tools": TOOLS,
         "tool_choice": "auto", "stream": False, "temperature": options["temperature"],
         "max_tokens": options["num_predict"]},
        timeout=timeout,
    )
    choice = (data.get("choices") or [{}])[0]
    return choice.get("message") or {}, {**(data.get("usage") or {}),
                                          "done_reason": choice.get("finish_reason")}


def unload_ollama(base: str, name: str) -> None:
    try:
        api_json(base, "/api/generate", {"model": name, "keep_alive": 0}, timeout=15)
    except (HTTPError, URLError, OSError, ValueError):
        try:
            subprocess.run(["ollama", "stop", name], capture_output=True, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass


def lms_binary() -> str | None:
    return shutil.which("lms") or str(Path.home() / ".lmstudio" / "bin" / "lms.exe")


def lm_prepare(path: str, identifier: str, ctx: int, events: Path) -> tuple[bool, str]:
    binary = lms_binary()
    if not binary or not Path(binary).exists():
        return False, "lms CLI не найден"
    try:
        try:
            api_json("http://127.0.0.1:1234", "/v1/models", timeout=3)
            server_running = True
        except (HTTPError, URLError, OSError, ValueError):
            server_running = False
        commands = [] if server_running else [
            [binary, "server", "start", "--port", "1234", "--bind", "127.0.0.1"]]
        commands.append([binary, "load", path, "--identifier", identifier,
                         "--context-length", str(ctx), "--gpu", "off", "--ttl", "600"])
        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
            log_event(events, "lms_command", command=command, exit_code=result.returncode,
                      stdout=result.stdout[-4000:], stderr=result.stderr[-4000:])
            if result.returncode:
                return False, f"lms завершилась с кодом {result.returncode}: {result.stderr[-500:]}"
        return True, ""
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)


def lm_unload(identifier: str) -> None:
    binary = lms_binary()
    if binary and Path(binary).exists():
        try:
            subprocess.run([binary, "unload", identifier], capture_output=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass


def trial(model: dict, run: dict, options: dict, attempt: int, events: Path) -> dict:
    name = model["name"]
    base = run["ollama_url"] if model["backend"] == "ollama" else run["lmstudio_url"]
    fixture = (Path(run["output_dir"]) / "fixture.py").read_text(encoding="utf-8")
    virtual_file = fixture
    read_ok = False
    edits = {"average": False, "label": False}
    prompt_tokens = 0
    actual_context = None
    thinking_only = False
    hit_output_limit = False
    started = time.monotonic()
    result = {"attempt": attempt, "options": options, "score": 0, "passed": False,
              "read_called": False, "edit_calls": 0, "prompt_tokens": 0,
              "actual_context": None, "elapsed_seconds": 0}
    identifier = "codex_benchmark_" + safe_name(name)[:30]
    loaded_here = False
    try:
        if model["backend"] == "lmstudio":
            loaded_here, reason = lm_prepare(model["path"], identifier, options["num_ctx"], events)
            if not loaded_here:
                raise RuntimeError(reason)
        messages = [{"role": "user", "content": TASK}]
        for turn in range(6):
            if model["backend"] == "ollama":
                assistant, usage = ollama_chat(base, name, messages, options, run["request_timeout"])
                if turn == 0:
                    try:
                        loaded = api_json(base, "/api/ps", timeout=8).get("models", [])
                        for item in loaded:
                            if item.get("name") == name:
                                actual_context = item.get("context_length")
                                break
                    except (HTTPError, URLError, OSError, ValueError):
                        pass
                prompt_tokens = max(prompt_tokens, int(usage.get("prompt_eval_count") or 0))
                calls = assistant.get("tool_calls") or []
            else:
                assistant, usage = lm_chat(base, identifier, messages, options, run["request_timeout"])
                prompt_tokens = max(prompt_tokens, int(usage.get("prompt_tokens") or 0))
                calls = assistant.get("tool_calls") or []
            log_event(events, "model_message", attempt=attempt, turn=turn,
                      assistant=assistant, usage=usage)
            messages.append(assistant)
            if not calls and assistant.get("thinking") and not assistant.get("content"):
                thinking_only = True
            if usage.get("done_reason") in ("length", "max_tokens") or (
                int(usage.get("eval_count") or usage.get("completion_tokens") or 0)
                >= options["num_predict"] - 16
            ):
                hit_output_limit = True
            if not calls:
                break
            for call in calls:
                function = call.get("function") or {}
                tool_name = function.get("name")
                arguments = parse_arguments(function.get("arguments"))
                if tool_name == "read_file":
                    result["read_called"] = True
                    read_ok = arguments.get("path") == "virtual_large_module.py"
                    tool_result = virtual_file if read_ok else "ERROR: path not found"
                    logged_result = {"ok": read_ok, "fixture_sha256": hashlib.sha256(virtual_file.encode()).hexdigest()}
                elif tool_name == "replace_line":
                    result["edit_calls"] += 1
                    old, new = arguments.get("old_line"), arguments.get("new_line")
                    valid = (
                        read_ok and arguments.get("path") == "virtual_large_module.py"
                        and isinstance(old, str) and isinstance(new, str)
                        and virtual_file.count(old + "\n") == 1
                    )
                    if valid:
                        virtual_file = virtual_file.replace(old + "\n", new + "\n", 1)
                        edits["average"] |= old == OLD_A and new == NEW_A
                        edits["label"] |= old == OLD_B and new == NEW_B
                    tool_result = "EDIT_OK" if valid else "ERROR: invalid exact-line replacement"
                    logged_result = {"ok": valid, "message": tool_result}
                else:
                    tool_result = "ERROR: unknown tool"
                    logged_result = {"ok": False, "message": tool_result}
                log_event(events, "tool_call", attempt=attempt, turn=turn,
                          tool=tool_name, arguments=arguments, result=logged_result)
                if model["backend"] == "ollama":
                    messages.append({"role": "tool", "tool_name": tool_name, "content": tool_result})
                else:
                    messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": tool_result})
            if all(edits.values()):
                break
        expected = fixture.replace(OLD_A + "\n", NEW_A + "\n", 1).replace(OLD_B + "\n", NEW_B + "\n", 1)
        unchanged_elsewhere = virtual_file == expected if all(edits.values()) else False
        result.update({"average_edit": edits["average"], "label_edit": edits["label"],
                       "unchanged_elsewhere": unchanged_elsewhere,
                       "prompt_tokens": prompt_tokens, "actual_context": actual_context,
                       "thinking_only": thinking_only, "hit_output_limit": hit_output_limit,
                       "score": (20 if read_ok else 0) + (35 if edits["average"] else 0)
                       + (35 if edits["label"] else 0) + (10 if unchanged_elsewhere else 0)})
        context_ok = (actual_context or options["num_ctx"]) >= run["target_context"]
        exercised = prompt_tokens >= int(run["target_context"] * 0.6)
        result["context_exercised"] = exercised
        result["passed"] = result["score"] == 100 and context_ok and exercised
        result["context_meets_target"] = context_ok
        result["status"] = "passed" if result["passed"] else "incomplete"
    except (HTTPError, URLError, OSError, ValueError, RuntimeError) as error:
        result["status"] = "error"
        detail = error.read(3000).decode("utf-8", errors="replace") if isinstance(error, HTTPError) else ""
        result["error"] = f"{error}: {detail}" if detail else str(error)
        log_event(events, "attempt_error", attempt=attempt, error=result["error"])
    finally:
        result["elapsed_seconds"] = round(time.monotonic() - started, 1)
        if model["backend"] == "ollama":
            unload_ollama(base, name)
        elif loaded_here:
            lm_unload(identifier)
        log_event(events, "attempt_end", **result)
    return result


def worker(run_dir: Path, index: int) -> int:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    model = run["models"][index]
    folder = run_dir / "models" / safe_name(model["name"])
    folder.mkdir(parents=True, exist_ok=True)
    events = folder / "events.jsonl"
    log_event(events, "model_start", model=model)
    if model["backend"] == "ollama" and "tools" not in model.get("capabilities", []):
        result = {"model": model, "status": "skipped", "reason": "Ollama не заявляет поддержку tools", "attempts": []}
    else:
        options = initial_options(model, run["target_context"])
        attempts = []
        for n in range(1, run["max_attempts"] + 1):
            attempt = trial(model, run, options, n, events)
            attempts.append(attempt)
            following, reason = next_options(model, run, attempts)
            if n == run["max_attempts"] and following is not None:
                attempt["suggested_options"] = following
                following = None
                reason = "Лимит попыток исчерпан. Рекомендуемое продолжение: " + reason
            attempt["tuning_decision"] = reason
            attempt["next_options"] = following
            log_event(events, "tuning_decision", attempt=n, reason=reason,
                      previous_options=options, next_options=following)
            write_json(folder / "partial.json", {"model": model, "attempts": attempts})
            if following is None:
                break
            options = following
        best = max(attempts, key=lambda item: (item["passed"], item["score"],
                                                item.get("context_meets_target", False)), default=None)
        result = {"model": model, "status": "passed" if best and best["passed"] else "failed",
                  "best": best, "attempts": attempts}
    write_json(folder / "result.json", result)
    return 0


def discover(ollama_url: str, lmstudio_dir: Path, selected: list[str]) -> list[dict]:
    tags = api_json(ollama_url, "/api/tags").get("models", [])
    models = []
    for tag in tags:
        name = tag.get("name") or tag.get("model")
        if selected and name not in selected:
            continue
        try:
            show = api_json(ollama_url, "/api/show", {"model": name})
            models.append({"backend": "ollama", "name": name, "size": tag.get("size"),
                           "native_context": native_context(show, tag),
                           "profile_context": declared_context(show.get("parameters")),
                           "capabilities": show.get("capabilities") or [],
                           "weight_key": weight_key(show, tag.get("digest", name))})
        except (HTTPError, URLError, OSError, ValueError) as error:
            models.append({"backend": "ollama", "name": name, "discovery_error": str(error),
                           "capabilities": [], "native_context": None})
    if lmstudio_dir.is_dir():
        for path in lmstudio_dir.rglob("*.gguf"):
            if path.name.lower().startswith("mmproj-"):
                continue
            name = "lmstudio:" + path.relative_to(lmstudio_dir).as_posix()
            if selected and name not in selected:
                continue
            models.append({"backend": "lmstudio", "name": name, "path": str(path),
                           "size": path.stat().st_size, "native_context": None,
                           "capabilities": ["unknown"]})
    if selected:
        missing = set(selected) - {model["name"] for model in models}
        if missing:
            raise ValueError("Модели не найдены: " + ", ".join(sorted(missing)))
    return models


def summarize(run_dir: Path) -> dict:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    rows = []
    for model in run["models"]:
        folder = run_dir / "models" / safe_name(model["name"])
        result_path = folder / "result.json"
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
        else:
            partial = folder / "partial.json"
            result = json.loads(partial.read_text(encoding="utf-8")) if partial.exists() else {}
            result.update({"model": model, "status": "interrupted"})
        best = result.get("best") or max(result.get("attempts", []),
                                         key=lambda item: (item["passed"], item["score"]), default={})
        rows.append({"name": model["name"], "backend": model["backend"],
                     "status": result.get("status", "interrupted"),
                     "score": best.get("score", 0), "passed": best.get("passed", False),
                     "context": best.get("actual_context") or (best.get("options") or {}).get("num_ctx"),
                     "settings": best.get("options"), "prompt_tokens": best.get("prompt_tokens"),
                     "context_exercised": best.get("context_exercised", False),
                     "reason": result.get("reason") or best.get("error", ""),
                     "attempts": len(result.get("attempts", [])),
                     "log": str(folder / "events.jsonl")})
    rows.sort(key=lambda item: (item["passed"], item["score"], item["context"] or 0), reverse=True)
    leaders = [row for row in rows if row["passed"] and row["score"] == rows[0]["score"]] if rows else []
    summary = {"created_at": run["created_at"], "updated_at": utc_now(),
               "target_context": run["target_context"], "fixture_lines": run["fixture_lines"],
               "models_total": len(rows), "models_passed": sum(row["passed"] for row in rows),
               "best_model": leaders[0] if leaders else None,
               "tied_leaders": [row["name"] for row in leaders], "ranking": rows}
    write_json(run_dir / "summary.json", summary)
    lines = ["# Отчёт о бенчмарке агентного кодинга", "",
             f"Создан: {run['created_at']}. Обновлён: {summary['updated_at']}.",
             f"Цель: {run['target_context']} токенов; виртуальный файл: {run['fixture_lines']} строк.",
             f"Пауза между моделями: {run.get('cooldown_seconds', 600)} секунд.",
             "Тест: прочитать весь файл через инструмент и сделать две точные правки в удалённых функциях.",
             "Для зачёта требуется использование не менее 60% целевого контекста по счётчику токенов API.",
             "Реальные файлы проектов не изменяются. Рейтинг относится только к этой задаче.", "",
             "| Место | Модель | Статус | Балл | Контекст | Токенов в запросе | Настройки | Причина/ошибка |",
             "| ---: | --- | --- | ---: | ---: | ---: | --- | --- |"]
    for index, row in enumerate(rows, start=1):
        settings = json.dumps(row["settings"], ensure_ascii=False) if row["settings"] else "—"
        reason = str(row["reason"]).replace("|", "\\|").replace("\n", " ")[:180]
        lines.append(f"| {index} | {row['name'].replace('|', '/')} | {row['status']} | "
                     f"{row['score']} | {row['context'] or '—'} | {row['prompt_tokens'] or '—'} | `{settings}` | {reason} |")
    if summary["best_model"]:
        best = summary["best_model"]
        heading = ("Один из лидеров" if len(leaders) > 1 else "Лучший прошедший кандидат")
        lines += ["", f"## {heading}: {best['name']}", "",
                  f"Контекст: {best['context']}; настройки: `{json.dumps(best['settings'], ensure_ascii=False)}`."]
        if len(leaders) > 1:
            lines += ["", "Одинаковый балл набрали: " + ", ".join(row["name"] for row in leaders) + "."]
    else:
        lines += ["", "Ни одна модель пока не прошла тест при целевом контексте."]
    lines += ["", "## Проверка каждой модели", "",
              "В каталоге `models` лежат `result.json`, `partial.json` и `events.jsonl` с ответами модели, вызовами инструментов, результатами правок, ошибками, временем и решениями по настройкам. Исходный файл — `fixture.py`.", ""]
    for row in rows:
        result_path = run_dir / "models" / safe_name(row["name"]) / "result.json"
        if not result_path.exists():
            continue
        result = json.loads(result_path.read_text(encoding="utf-8"))
        lines += [f"### {row['name']}", ""]
        for attempt in result.get("attempts", []):
            lines.append(f"- Попытка {attempt['attempt']}: {attempt.get('score', 0)}/100; "
                         f"`{json.dumps(attempt['options'], ensure_ascii=False)}`; "
                         f"{attempt.get('tuning_decision', attempt.get('error', ''))}")
        if not result.get("attempts"):
            lines.append(f"- {result.get('reason', result.get('status', 'нет попыток'))}")
        lines.append("")
    (run_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def prevent_sleep() -> None:
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)


def allow_sleep() -> None:
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", default=[], help="restrict to a model name; repeatable")
    parser.add_argument("--target-context", type=int, default=65536)
    parser.add_argument("--fixture-lines", type=int, default=3000)
    parser.add_argument("--max-attempts", type=int, default=6)
    parser.add_argument("--model-timeout", type=int, default=1800, help="hard seconds per model")
    parser.add_argument("--request-timeout", type=int, default=600)
    parser.add_argument("--cooldown-seconds", type=int, default=600,
                        help="pause between models; default 600 seconds")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--resume", type=Path, help="resume an existing run directory")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--lmstudio-url", default="http://127.0.0.1:1234")
    parser.add_argument("--lmstudio-dir", type=Path, default=Path.home() / ".lmstudio" / "models")
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if (args.target_context < 2048 or args.fixture_lines < 100
            or not 1 <= args.max_attempts <= 12 or args.cooldown_seconds < 0):
        parser.error("target context >= 2048, fixture lines >= 100, max attempts 1..12, cooldown >= 0 required")
    if args.worker_index is not None:
        if not args.output_dir:
            parser.error("worker requires --output-dir")
        return worker(args.output_dir, args.worker_index)
    if args.resume:
        run_dir = args.resume.resolve()
        if not (run_dir / "run.json").exists():
            parser.error("--resume must point to a directory with run.json")
        run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        run["cooldown_seconds"] = args.cooldown_seconds
        write_json(run_dir / "run.json", run)
    else:
        try:
            models = discover(args.ollama_url, args.lmstudio_dir, args.model)
        except (HTTPError, URLError, OSError, ValueError) as error:
            print(f"Не удалось собрать список моделей: {error}", file=sys.stderr)
            return 1
        if not models:
            print("Скачанных моделей не найдено", file=sys.stderr)
            return 1
        run_dir = (args.output_dir or Path.home() / "agent-benchmark-reports" /
                   datetime.now().strftime("%Y%m%d_%H%M%S")).resolve()
        if run_dir.exists() and any(run_dir.iterdir()):
            parser.error("output directory is not empty; use --resume for an existing run")
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "models").mkdir(exist_ok=True)
        fixture = make_fixture(args.fixture_lines)
        (run_dir / "fixture.py").write_text(fixture, encoding="utf-8")
        ram_total, ram_free = memory_bytes()
        run = {"created_at": utc_now(), "output_dir": str(run_dir), "models": models,
               "target_context": args.target_context, "fixture_lines": args.fixture_lines,
               "fixture_sha256": hashlib.sha256(fixture.encode()).hexdigest(),
               "max_attempts": args.max_attempts, "request_timeout": args.request_timeout,
               "model_timeout": args.model_timeout, "cooldown_seconds": args.cooldown_seconds,
               "ollama_url": args.ollama_url,
               "lmstudio_url": args.lmstudio_url, "ram_total": ram_total, "ram_free_at_start": ram_free}
        write_json(run_dir / "run.json", run)
    print(f"Отчёт: {run_dir / 'summary.md'}", flush=True)
    prevent_sleep()
    try:
        for index, model in enumerate(run["models"]):
            folder = run_dir / "models" / safe_name(model["name"])
            if (folder / "result.json").exists():
                continue
            print(f"[{index + 1}/{len(run['models'])}] {model['name']}", flush=True)
            command = [sys.executable, str(Path(__file__).resolve()), "--output-dir", str(run_dir),
                       "--worker-index", str(index)]
            try:
                process = subprocess.run(command, capture_output=True, text=True,
                                         timeout=run["model_timeout"], check=False)
                if process.returncode:
                    folder.mkdir(parents=True, exist_ok=True)
                    write_json(folder / "result.json", {"model": model, "status": "worker_error",
                               "reason": (process.stderr or process.stdout)[-3000:], "attempts": []})
            except subprocess.TimeoutExpired:
                folder.mkdir(parents=True, exist_ok=True)
                partial = folder / "partial.json"
                saved_attempts = (json.loads(partial.read_text(encoding="utf-8"))
                                  .get("attempts", []) if partial.exists() else [])
                write_json(folder / "result.json", {"model": model, "status": "timeout",
                           "reason": f"Превышен лимит {run['model_timeout']} секунд",
                           "attempts": saved_attempts})
                if model["backend"] == "ollama":
                    unload_ollama(run["ollama_url"], model["name"])
            summary = summarize(run_dir)
            current = json.loads((folder / "result.json").read_text(encoding="utf-8"))
            print(f"  статус: {current.get('status')}", flush=True)
            remaining = any(not (run_dir / "models" / safe_name(next_model["name"]) /
                                 "result.json").exists() for next_model in run["models"][index + 1:])
            if remaining and run["cooldown_seconds"] and current.get("status") != "skipped":
                seconds = run["cooldown_seconds"]
                print(f"  охлаждение: пауза {seconds // 60} мин {seconds % 60} с", flush=True)
                log_event(run_dir / "run_events.jsonl", "cooldown_start",
                          after_model=model["name"], seconds=seconds)
                time.sleep(seconds)
                log_event(run_dir / "run_events.jsonl", "cooldown_end",
                          after_model=model["name"])
    except KeyboardInterrupt:
        print("Остановлено; сохранённый прогон можно продолжить с --resume.", file=sys.stderr)
        return 130
    finally:
        summarize(run_dir)
        allow_sleep()
    summary = summarize(run_dir)
    if summary["best_model"]:
        best = summary["best_model"]
        print(f"Лучший прошедший кандидат: {best['name']} ({best['score']}/100)")
    else:
        print("При целевом контексте ни одна модель пока не прошла тест.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    raise SystemExit(main())
