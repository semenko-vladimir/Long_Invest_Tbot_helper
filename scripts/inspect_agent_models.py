#!/usr/bin/env python3
"""Rank already downloaded local models for long-context coding agents.

Read-only: Ollama metadata, LM Studio GGUF filenames, and available RAM.
No model is loaded and no inference request is sent.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

GIB = 1024**3
CODE_NAME = re.compile(r"coder|coding|(?:^|[-_.])code(?:[-_.]|$)|devstral|codestral|openhands", re.I)


def api_json(base_url: str, endpoint: str, payload: dict | None = None, timeout: int = 15) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}{endpoint}",
        data=body,
        headers={"Content-Type": "application/json"} if body else {},
    )
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def memory_bytes() -> tuple[int | None, int | None]:
    if os.name != "nt":
        return None, None

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("load_percent", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_pagefile", ctypes.c_ulonglong),
            ("available_pagefile", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None, None
    return status.total_physical, status.available_physical


def declared_context(parameters: str | None) -> int | None:
    match = re.search(r"(?m)^\s*num_ctx\s+(\d+)\s*$", parameters or "")
    return int(match.group(1)) if match else None


def native_context(show: dict, tag: dict) -> int | None:
    for key, value in show.get("model_info", {}).items():
        if key.endswith(".context_length") and isinstance(value, int):
            return value
    value = tag.get("details", {}).get("context_length")
    return value if isinstance(value, int) else None


def weight_key(show: dict, fallback: str) -> str:
    # The first non-comment FROM is the main GGUF blob. Profiles sharing it
    # have identical primary weights even when their Ollama digests differ.
    for line in show.get("modelfile", "").splitlines():
        if line.startswith("FROM "):
            return line[5:].strip().lower()
    return fallback


def verdict(model: dict, target: int, total_ram: int | None, free_ram: int | None) -> str:
    if not model["tools"]:
        return "нет tools"
    if model["native_context"] is None:
        return "контекст неизвестен"
    if model["native_context"] < target:
        return "контекст модели мал"
    if model["allocated_context"] is None:
        return "задать num_ctx"
    if model["allocated_context"] < target:
        return "профиль ограничен"
    if total_ram and model["size"] > total_ram - 4 * GIB:
        return "веса больше RAM"
    if free_ram and model["size"] > free_ram - 3 * GIB:
        return "освободить RAM"
    return "кандидат"


def rank(model: dict, target: int) -> tuple:
    allocated = model["allocated_context"]
    native = model["native_context"] or 0
    if not model["tools"] or native < target:
        readiness = 0
    elif allocated is None:
        readiness = 2  # The model could qualify after a context setting.
    elif allocated >= target:
        readiness = 3
    else:
        readiness = 1  # This profile explicitly limits the context.
    return (
        readiness,
        int(model["code_focused"]),
        model["size"] or 0,
        int(model["thinking"]),
        native,
    )


def gib(value: int | None) -> str:
    return "?" if value is None else f"{value / GIB:.1f}"


def context(value: int | None) -> str:
    return "auto/?" if value is None else f"{value // 1024}K"


def probe_agent(base_url: str, name: str, lines_count: int, ctx: int, timeout: int) -> dict:
    """Exercise read + exact edit with tools against an in-memory large file."""
    path = "virtual_large_module.py"
    old_line = "    return total / count"
    new_line = "    return total / count if count else 0"
    lines = [f"CONSTANT_{index:05d} = {index}" for index in range(lines_count)]
    middle = len(lines) // 2
    lines[middle:middle] = ["def normalized_average(total, count):", old_line, ""]
    lines.append("END_MARKER = 'preserve-me'")
    original = "\n".join(lines) + "\n"
    virtual_file = original
    read_done = False
    edit_done = False
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the complete virtual file before editing it.",
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
                "description": "Replace one exact line in the virtual file; other lines remain unchanged.",
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
    messages = [
        {
            "role": "user",
            "content": (
                f"You are editing {path}, a large virtual Python file. "
                "Call read_file first. Then call replace_line to replace exactly "
                f"{old_line!r} with {new_line!r} inside normalized_average. "
                "Preserve every other line. Do not write an answer until the edit tool succeeds."
            ),
        }
    ]
    result = {"model": name, "read_called": False, "edit_called": False, "passed": False}
    try:
        for _ in range(4):
            response = api_json(
                base_url,
                "/api/chat",
                {
                    "model": name,
                    "messages": messages,
                    "tools": tools,
                    "stream": False,
                    "keep_alive": "5m",
                    "options": {"num_ctx": ctx, "num_predict": 2048},
                },
                timeout=timeout,
            )
            assistant = response.get("message") or {}
            messages.append(assistant)
            calls = assistant.get("tool_calls") or []
            if not calls:
                break
            for call in calls:
                function = call.get("function") or {}
                tool_name = function.get("name")
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except ValueError:
                        arguments = {}
                if tool_name == "read_file":
                    result["read_called"] = True
                    read_done = True
                    content = virtual_file if arguments.get("path") == path else "ERROR: unknown path"
                elif tool_name == "replace_line":
                    result["edit_called"] = True
                    valid = (
                        read_done
                        and arguments.get("path") == path
                        and arguments.get("old_line") == old_line
                        and arguments.get("new_line") == new_line
                        and virtual_file.count(old_line + "\n") == 1
                    )
                    if valid:
                        virtual_file = virtual_file.replace(old_line + "\n", new_line + "\n", 1)
                        edit_done = True
                    content = "EDIT_OK" if valid else "ERROR: invalid or premature edit"
                else:
                    content = "ERROR: unknown tool"
                messages.append({"role": "tool", "tool_name": tool_name, "content": content})
            if edit_done:
                break
        result["passed"] = edit_done and virtual_file == original.replace(old_line + "\n", new_line + "\n", 1)
    except (URLError, OSError, ValueError) as error:
        result["error"] = str(error)
    finally:
        # Ollama can release the model after the probe. Failure here does not
        # change the edit verdict.
        try:
            api_json(base_url, "/api/generate", {"model": name, "keep_alive": 0}, timeout=10)
        except (URLError, OSError, ValueError):
            pass
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-context", type=int, default=65536, metavar="TOKENS")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--lmstudio-dir", type=Path, default=Path.home() / ".lmstudio" / "models")
    parser.add_argument("--probe-model", metavar="NAME", help="test tool use and an in-memory file edit")
    parser.add_argument("--probe-lines", type=int, default=1500, metavar="N")
    parser.add_argument("--probe-context", type=int, default=32768, metavar="TOKENS")
    parser.add_argument("--probe-timeout", type=int, default=600, metavar="SECONDS")
    parser.add_argument("--json", action="store_true", help="print machine-readable report")
    args = parser.parse_args()
    if args.target_context < 1024:
        parser.error("--target-context must be at least 1024")
    if args.probe_lines < 100 or args.probe_context < 2048 or args.probe_timeout < 30:
        parser.error("probe needs at least 100 lines, 2048 context tokens and 30 seconds timeout")

    try:
        tags = api_json(args.ollama_url, "/api/tags").get("models", [])
    except (URLError, OSError, ValueError) as error:
        print(f"Ollama недоступна: {error}", file=sys.stderr)
        return 1

    total_ram, free_ram = memory_bytes()
    server_context = os.getenv("OLLAMA_CONTEXT_LENGTH")
    server_context = int(server_context) if server_context and server_context.isdigit() else None
    models = []
    errors = []
    for tag in tags:
        name = tag.get("name") or tag.get("model")
        if not name:
            continue
        try:
            show = api_json(args.ollama_url, "/api/show", {"model": name})
        except (URLError, OSError, ValueError) as error:
            errors.append(f"{name}: {error}")
            continue
        caps = set(show.get("capabilities") or [])
        explicit = declared_context(show.get("parameters"))
        model = {
            "name": name,
            "size": int(tag.get("size") or 0),
            "quantization": show.get("details", {}).get("quantization_level"),
            "native_context": native_context(show, tag),
            "profile_context": explicit,
            # A client-side environment variable does not prove that the
            # already-running Ollama server inherited the same setting.
            "allocated_context": explicit,
            "tools": "tools" in caps,
            "thinking": "thinking" in caps,
            "code_focused": bool(CODE_NAME.search(name)),
            "weight_key": weight_key(show, tag.get("digest", name)),
        }
        model["verdict"] = verdict(model, args.target_context, total_ram, free_ram)
        models.append(model)
    models.sort(key=lambda model: rank(model, args.target_context), reverse=True)

    lmstudio = []
    if args.lmstudio_dir.is_dir():
        for path in args.lmstudio_dir.rglob("*.gguf"):
            if path.name.lower().startswith("mmproj-"):
                continue
            try:
                lmstudio.append({"path": str(path), "size": path.stat().st_size})
            except OSError as error:
                errors.append(f"{path}: {error}")

    report = {
        "target_context": args.target_context,
        "ram_total_bytes": total_ram,
        "ram_free_bytes": free_ram,
        "server_context_environment": server_context,
        "ollama_profile_count": len(models),
        "distinct_primary_weights": len({item["weight_key"] for item in models}),
        "models": models,
        "lmstudio_models_without_verified_capabilities": lmstudio,
        "errors": errors,
    }
    if args.probe_model:
        if args.probe_model not in {model["name"] for model in models}:
            parser.error(f"model is not installed in Ollama: {args.probe_model}")
        report["probe"] = probe_agent(
            args.ollama_url, args.probe_model, args.probe_lines, args.probe_context, args.probe_timeout
        )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"Цель: {args.target_context:,} токенов контекста для coding agent".replace(",", " "))
    print(f"RAM: {gib(total_ram)} GiB всего, {gib(free_ram)} GiB свободно сейчас")
    print(f"Ollama: {len(models)} профилей, {report['distinct_primary_weights']} наборов основных весов")
    if server_context:
        print(f"OLLAMA_CONTEXT_LENGTH в среде этой программы: {context(server_context)} (сервер проверить отдельно)")
    print()
    print(f"{'Модель':<73} {'Веса':>6} {'Родной':>7} {'Задан':>8} {'Tools':>5}  Итог")
    print("-" * 124)
    for model in models:
        name = model["name"]
        if len(name) > 73:
            name = name[:70] + "..."
        print(
            f"{name:<73} {gib(model['size']):>6} "
            f"{context(model['native_context']):>7} "
            f"{context(model['allocated_context']):>8} "
            f"{'да' if model['tools'] else 'нет':>5}  {model['verdict']}"
        )
    if lmstudio:
        print("\nLM Studio (контекст и tools требуют проверки в LM Studio):")
        for model in lmstudio:
            print(f"  {Path(model['path']).name} — {gib(model['size'])} GiB")
    if models:
        top = models[0]
        print(f"\nПервый кандидат по метаданным: {top['name']} ({top['verdict']}).")
    print("Порядок — по готовности к цели и признакам специализации, не по качеству ответов.")
    print("Это отбор по метаданным, а не проверка качества правок или удержания целевого контекста.")
    print("auto/? означает: профиль не задаёт num_ctx; реальное выделение проверьте в ollama ps.")
    if args.probe_model:
        probe = report["probe"]
        status = "ПРОЙДЕНО" if probe["passed"] else "НЕ ПРОЙДЕНО"
        print(
            f"Проба {args.probe_model}: {status}; чтение={probe['read_called']}, "
            f"правка={probe['edit_called']}, строк={args.probe_lines}, контекст={context(args.probe_context)}."
        )
        if probe.get("error"):
            print(f"Ошибка пробы: {probe['error']}")
    if errors:
        print("Ошибки чтения: " + "; ".join(errors), file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    raise SystemExit(main())
