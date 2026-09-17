# Multi-account investment foundation

## Ownership and identity

The active hierarchy is:

```text
User (one local per-user database)
└── BrokerConnection (provider-neutral, secret-free)
    └── InvestmentAccount (stable external broker account ID)
        ├── StrategyProfile
        └── PortfolioSnapshot
            └── PositionSnapshot
```

`BrokerConnection` identifies a logical credential-backed connection without storing the credential. For T-Invest, the token continues to come from `.env` or `users.json`. `InvestmentAccount` is unique by broker connection plus external account ID; names, list positions, and the current number of accounts are not identity.

Account discovery is read-only and upserts metadata returned by the broker. Reordering does not change identity, future accounts such as an IIS are added on the next sync, and an account missing from one response is not deleted or automatically disabled. Generic discovery never opens a sandbox account.

## Runtime boundary

`InvestmentAccountContext` is immutable and contains the safe user, broker connection, account, and optional strategy data needed by downstream services. Portfolio reads require its explicit external account ID. There is no mutable process-global current account.

The aggregate portfolio is a derived view: it sums successful account totals and retains one account view for each enabled account. Positions are never merged canonically across accounts. A failed account is represented on its own account view and marks the aggregate partial, so the remaining total is not silently presented as complete.

Successful portfolio reads create an account-scoped portfolio snapshot and account-scoped position rows. Existing legacy order, statistics, investment-plan, watchlist, and price-candle tables are intentionally unchanged in this foundation migration; they require separate product decisions before any future account-specific behavior uses them.

## Strategy, notifications, and analysis

Each investment account can have one strategy profile containing a title, free-form key, thesis/description, extensible JSON settings, and a future analysis-profile key. `AccountRegistryService.save_strategy_profile` validates the account context and creates or updates only that account's profile. No strategy scoring, monitoring, RAG, or LLM inference is implemented here.

Future account-specific work must use this boundary:

```text
InvestmentAccountContext + StrategyProfile + account data
    -> account-specific calculation/notification/analysis
```

Every future notification must identify the user, broker connection, account display name, and account strategy context. The same instrument can have different conclusions on different accounts. Deterministic portfolio calculations remain Python services; an LLM must not become the sole calculation layer.

## Trading safety

This foundation adds no automatic order path. With `APP_MODE="prod"` and `ALLOW_PROD_TRADING="false"`, production portfolio reads remain available while Telegram hides Buy/Sell actions and `OrderService` continues to reject forced execution callbacks. Existing order architecture is not made account-aware by this migration and must not infer a production target account for new features. The legacy anti-greedy policy is skipped when an aggregate contains more than one account because its order path has no explicit account target.

## Migration and rollback

Alembic revision `f7a4c2e9b103` adds only new tables and indexes. It does not drop or rewrite legacy data and does not migrate credentials. Downgrade removes only the five foundation tables, so rollback is the code revert plus downgrade to `e6a3b7c9d1f2`. Disposable databases are used for destructive migration checks.
