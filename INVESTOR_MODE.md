# Investor Mode

Investor mode is the lightweight long-term workflow for this bot. It is sandbox-first, manual-only, and intentionally avoids trading signals, ML, and auto-trading.

## Supported Workflow

1. Start the bot with `/start`.
2. Use `Watchlist` to add tickers you want to follow.
3. Use `Portfolio` to review current positions.
4. Use `Dividends` to check dividend information for watchlist instruments.
5. Use `Buy` or `Sell` for manual orders, or type direct commands:

```text
buy SBER 1
sell SBER 1
```

6. Use `Stats` for basic text statistics about stored manual trading records.
7. Use `Reports` to see reminder settings.
8. Use `Help` or `/help` for the command list.

## Reminders

Daily investor reminders are optional and disabled by default. They do not contain signals, forecasts, or trade advice.

```env
ENABLE_INVESTOR_REMINDERS = "true"
INVESTOR_REMINDER_TIME = "09:00"
```

After changing these values, restart the app. The reminder only prompts you to review portfolio, dividends, watchlist, and stats.

## Intentionally Left Out

- RSI, MACD, EMA, SMA, Bollinger, and other technical signal flows.
- GPT and LSTM integrations.
- Scalping and day-trading menus.
- Signal-driven execution.
- Aggressive automation or production trading defaults.

Production trading remains blocked unless `APP_MODE="prod"`, `TOKEN` is filled, and `ALLOW_PROD_TRADING="true"` is set explicitly.
