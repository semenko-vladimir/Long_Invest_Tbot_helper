"""Export a daily draft from a migrated SQLite cache without network or delivery."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.daily_digest import DigestService
from app.services.user_context import UserContext


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--date", type=date.fromisoformat)
    args = parser.parse_args()
    path = args.database.resolve()
    if not path.is_file():
        parser.error("The database must already exist and be migrated.")
    engine = create_engine(f"sqlite:///file:{path.as_posix()}?mode=ro&uri=true")
    factory = sessionmaker(bind=engine)
    user = UserContext("preview", "Предпросмотр", 0, 0.3, str(path))
    try:
        draft = DigestService(factory, user).build(args.date)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "digest.txt").write_text(draft.text, encoding="utf-8")
        for chart in draft.charts:
            (args.output / (chart.ticker + ".png")).write_bytes(chart.png_bytes)
        (args.output / "coverage.json").write_text(json.dumps(draft.coverage, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"date": draft.report_date, "charts": [chart.ticker for chart in draft.charts], "text_chars": len(draft.text)}, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
