"""Shared instrument notes, explicitly owned by the resolved local user."""

from dataclasses import dataclass

from app.backend.models.accounts import utc_now
from app.backend.models.stocks import StockNote


@dataclass(frozen=True)
class NoteView:
    id: int
    instrument_key: str
    ticker: str
    text: str
    created_at: object
    updated_at: object


class StockNotesService:
    def __init__(self, factory, user):
        self.factory, self.user = factory, user

    def list(self, key=None):
        with self.factory() as db:
            query = db.query(StockNote).filter_by(user_id=self.user.user_id)
            if key is not None:
                query = query.filter_by(instrument_key=key)
            return tuple(self._view(row) for row in query.order_by(StockNote.created_at.desc(), StockNote.id.desc()))

    def add(self, key, ticker, text):
        if not key or len(key) > 64:
            raise ValueError("Не удалось определить инструмент.")
        with self.factory() as db:
            row = StockNote(user_id=self.user.user_id, instrument_key=key, ticker=ticker, text=self._text(text))
            db.add(row)
            db.commit()
            return self._view(row)

    def edit(self, note_id, text):
        with self.factory() as db:
            row = self._owned(db, note_id)
            row.text, row.updated_at = self._text(text), utc_now()
            db.commit()
            return self._view(row)

    def get(self, note_id):
        with self.factory() as db:
            return self._view(self._owned(db, note_id))

    def delete(self, note_id):
        with self.factory() as db:
            row = self._owned(db, note_id)
            db.delete(row)
            db.commit()

    def _owned(self, db, note_id):
        row = db.query(StockNote).filter_by(id=note_id, user_id=self.user.user_id).first()
        if not row:
            raise ValueError("Заметка недоступна.")
        return row

    @staticmethod
    def _text(text):
        text = str(text or "").strip()
        if not 1 <= len(text) <= 3000:
            raise ValueError("Введите текст заметки от 1 до 3000 символов.")
        return text

    @staticmethod
    def _view(row):
        return NoteView(row.id, row.instrument_key, row.ticker, row.text, row.created_at, row.updated_at)
