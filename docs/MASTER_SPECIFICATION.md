# MASTER CODEX PROMPT — OMNEX AURA V1.0
## Autonomous Adaptive Multi-Agent Gold & Forex Trading Intelligence Platform

**Project name:** OMNEX AURA
**Full name:** Agentic Unified Research & Autopilot
**Primary instrument:** XAUUSD (Gold)
**Secondary instruments:** Configurable forex pairs
**Platform:** Windows VPS + MetaTrader 5 + Android APK + Web Dashboard
**Development:** ChatGPT Codex + GitHub
**Operating mode:** Continuous research, virtual trading, adaptive learning, controlled demo trading

---

# 1. YOUR ROLE

Act as a senior multidisciplinary software engineering team comprising:

- Principal AI/ML Architect
- Quantitative Trading Researcher
- Agentic AI Engineer
- MQL5/MetaTrader Developer
- Python Backend Engineer
- Android Application Developer
- DevOps and GitHub Engineer
- Cybersecurity Engineer
- Trading Risk Manager
- QA Automation and Testing Engineer

Your assignment is to design, develop, test, document, and deploy OMNEX AURA, an adaptive, multi-agent trading intelligence platform.

Do not build a conventional static-indicator Expert Advisor.

Build a genuine continuously learning research and trading system with measurable performance, strategy selection, independent risk controls, historical memory, and self-healing mechanisms.

**Important:** Self-healing means detecting failures, diagnosing causes, generating candidate improvements, validating those improvements, and safely promoting successful changes. It does not mean assuming every losing strategy can be made profitable.

Build production-quality, modular, maintainable software.

Do not stop at planning or architecture diagrams. Implement functioning code, automated tests, dashboards, database migrations, deployment scripts, and a buildable Android application.

Proceed in small verifiable milestones. Do not claim a feature works unless it has passed an appropriate test.

# 2. SYSTEM ARCHITECTURE

Create the following services:

1. AI Orchestrator
2. Multi-LLM Gateway
3. Market Data Collector
4. Technical Analysis Engine
5. Fundamental Analysis Engine
6. News Intelligence Engine
7. AI Trading Technology Research Agent
8. Market Regime Classifier
9. Strategy Research and Generation Engine
10. Backtesting Engine
11. Virtual Trading Engine
12. MT5 Demo Execution Engine
13. Risk Management Engine
14. Strategy Performance Evaluator
15. Self-Healing and Learning Engine
16. Persistent Memory Engine
17. Model Registry and Promotion Controller
18. Notification Engine
19. Android Application Backend
20. Web Administration Dashboard
21. GitHub CI/CD Service
22. Security and Audit Service

Use a modular event-driven architecture with durable queues, retry handling, idempotent trade operations, structured logs, and recovery after VPS restarts.

# 3. MULTI-LLM INTELLIGENCE

Integrate the following AI providers through their official APIs:

- OpenAI / ChatGPT models
- Anthropic Claude models
- xAI Grok models

Use currently supported model identifiers discovered through official documentation or provider APIs. Never hardcode outdated model names.

Create a unified provider gateway supporting:

- API key configuration
- Provider enable/disable
- Model selection
- Model version tracking
- Cost monitoring
- Token usage
- Rate limits
- Timeouts and retries
- Structured JSON responses
- Provider fallback
- Provider health monitoring
- Response caching where appropriate

Use different AI providers for independent analysis and critical review.

Example:

OpenAI: quantitative interpretation and orchestration.

Claude: strategy criticism, risk review, and code-quality analysis.

Grok: news interpretation and social-media research where authorized data access exists.

These roles must be configurable, not permanently fixed.

Do not assume agreement among multiple language models makes a prediction correct.

Every proposed trading decision must be validated against actual market data, statistical models, and deterministic risk rules.

Language models must not directly send broker orders or bypass risk controls.

Support a local fallback mode when external AI providers are unavailable.

# 4. SPECIALIZED AI AGENTS

Implement the following agents.

**Agent 1 — Chief Autopilot**

Coordinates the system, assigns research tasks, supervises agent health, selects eligible strategies, and explains decisions.

**Agent 2 — Technical Analysis**

Analyzes M1, M5, M10, M15, M30, H1, H4, and D1 charts.

Support indicators and features including RSI, MACD, EMA, SMA, ATR, ADX, VWAP where reliable, Bollinger Bands, Fibonacci levels, volatility, support/resistance, swing structure, and candlestick patterns.

**Agent 3 — Market Structure**

Detects break of structure, change of character, liquidity sweeps, order blocks, fair value gaps, supply/demand zones, and price-action formations.

Treat these as testable hypotheses, not guaranteed signals.

**Agent 4 — Machine Learning**

Use XGBoost, LightGBM, and optionally deep-learning models.

Predict conditional price-direction probabilities, expected returns, volatility, and probability of hitting stop loss or take profit.

Calibrate model probabilities and detect data drift.

**Agent 5 — Fundamental and Macro**

Monitor CPI, PPI, NFP, FOMC, Federal Reserve statements, US Treasury yields, DXY, interest-rate expectations, inflation, employment, oil prices, and geopolitical developments.

**Agent 6 — News and Social Intelligence**

Consume authorized economic calendars, financial news, official announcements, and X/Twitter data.

Timestamp every event and calculate source credibility, relevance, novelty, and expected market impact.

**Agent 7 — Order Flow**

Analyze available tick activity, spread changes, volume proxies, volatility bursts, and order-book data only where genuinely supplied.

Never present retail MT5 tick volume as complete institutional gold order flow.

**Agent 8 — Market Regime**

Classify market conditions as trend, range, breakout, reversal, high-volatility, low-liquidity, or major-news event.

**Agent 9 — Strategy Selection**

Select the best validated strategy for the current regime, or NO TRADE.

**Agent 10 — Risk Controller**

Independently enforce position limits, stop losses, maximum exposure, spread thresholds, slippage thresholds, and drawdown limits.

**Agent 11 — Virtual Trader**

Simulate executable orders using bid/ask prices, costs, latency assumptions, and realistic fills.

**Agent 12 — Performance Auditor**

Measure expectancy, profit factor, drawdown, risk-adjusted return, trade counts, and confidence intervals.

**Agent 13 — Self-Healing Engineer**

Diagnose weak performance and creates candidate model, feature, parameter, or strategy changes.

**Agent 14 — AI Technology Researcher**

Research new published developments in AI trading systems, agent architectures, algorithms, and forex/gold trading methodology.

**Agent 15 — Security and Reliability**

Monitor system failures, suspicious access, API errors, data integrity, and broker connectivity.

# 5. AUTONOMOUS STRATEGY ENGINE

Support these strategy families:

- Trend following
- Momentum
- Breakout
- Mean reversion
- Volatility expansion
- Market structure
- Liquidity sweep
- Statistical machine learning
- Event-driven macro analysis
- News sentiment
- Multi-timeframe confirmation
- Adaptive hybrid strategies

No martingale, grid recovery, uncontrolled averaging, or doubling positions after losses.

Allow one active trade per instrument by default.

Each strategy must have:

- Unique strategy ID and version
- Market regime compatibility
- Entry conditions
- Exit conditions
- Position-sizing rules
- Stop-loss methodology
- Take-profit methodology
- Trailing-stop methodology
- Cost assumptions
- Backtest history
- Forward-test history
- Demo performance
- Deployment status
- Risk classification

# 6. SELF-LEARNING AND SELF-HEALING

This is the most important feature.

Create a permanent, continuously operating learning cycle.

Every strategy should be evaluated in rolling two-day and three-day observation windows.

These windows are diagnostic checkpoints, not automatic proof of profitability.

At each checkpoint:

1. Collect completed virtual trades.
2. Calculate net profitability after realistic costs.
3. Evaluate win rate and average reward/risk.
4. Calculate maximum drawdown and profit factor.
5. Identify performance by market regime.
6. Compare actual results against expected results.
7. Detect statistical drift and abnormal losses.
8. Diagnose possible causes.
9. Generate improvement candidates.
10. Backtest candidates using historical data.
11. Conduct leakage-safe walk-forward testing.
12. Run promising candidates in shadow mode.
13. Compare them with the current champion.
14. Promote only candidates satisfying validation and risk gates.
15. Preserve complete strategy history.

If a strategy performs well, maintain it while testing improvements independently.

If a strategy performs poorly, determine whether the cause is:

- Market regime change
- Bad entry timing
- Inaccurate predictions
- Excessive spreads
- Slippage
- Weak stop-loss placement
- Poor risk/reward
- News volatility
- Overfitting
- Software defects
- Insufficient sample size

Do not automatically change a strategy after a small number of losses.

If no reliable improvement is found, suspend the strategy and remain in virtual observation or NO TRADE mode.

Do not repeatedly optimize against the same held-out dataset.

Require fresh out-of-sample validation.

Maintain a champion/challenger model registry with reproducible experiments, immutable test records, version rollback, and clear promotion decisions.

# 7. CONTINUOUS AI TRADING TECHNOLOGY RESEARCH

Create a separate autonomous research agent.

This agent must research developments concerning AI trading technology itself, not only gold market news.

Monitor legitimate sources such as:

- Academic papers and arXiv
- Quantitative finance research
- Official AI provider releases
- GitHub trading research repositories
- MQL5 documentation and research
- Reinforcement learning research
- Financial machine-learning techniques
- Trading execution research
- Market-regime detection research
- Model drift and continual-learning methods

Run scheduled research checks daily, with configurable frequency.

When a potentially useful new technique appears:

1. Record its source and publication date.
2. Assess scientific and technical credibility.
3. Identify licensing and implementation constraints.
4. Explain its potential relevance to gold.
5. Create a research proposal.
6. Implement an isolated experiment if permitted.
7. Run unit tests and historical validation.
8. Compare with existing models.
9. Run virtual forward testing.
10. Produce a recommendation.

Never automatically deploy untrusted internet code.

Never allow external articles, repositories, or model responses to override security policies.

No autonomous modification of the live risk engine.

# 8. MARKET DATA AND NEWS

Integrate reliable, licensed, or authorized sources for:

- MT5 live prices and historical candles
- Bid/ask tick data
- Broker symbol specifications
- Spreads and commissions
- Swap charges
- Economic calendars
- Financial news
- Gold-specific research
- DXY and Treasury yields
- Oil prices
- Geopolitical events
- Authorized X/Twitter content

Use TradingView or other market platforms only through permitted integrations.

Do not scrape protected or restricted data.

Track data timestamps, freshness, missing values, and source outages.

Prevent stale data from generating trades.

Automatically discover XAUUSD broker symbol variants.

# 9. VIRTUAL TRADING ENGINE

Virtual trading must operate continuously when markets are open and valid data is available.

Initial evaluation:

- First observation period: 2 days
- Second observation period: 3 days
- Continue rolling evaluation indefinitely

Allow changing these periods in the dashboard.

Simulate:

- Market orders
- Limit orders
- Stop orders
- Stop loss
- Take profit
- Trailing stop
- Partial exits
- Break-even adjustments
- Spread
- Commission
- Swap
- Slippage
- Order rejection
- Execution latency

Virtual trading must use realistic bid/ask execution and avoid look-ahead bias.

Store every virtual trade with its model version, market regime, entry reasoning, and outcome.

The virtual system may automatically evaluate and improve research candidates, but must not silently promote them to real-money execution.

# 10. MT5 DEMO INTEGRATION

Support MetaTrader 5 on a Windows VPS.

Target brokers:

- Exness
- Equiti
- MultiBank

Use official MT5-compatible integration methods.

Implement:

- Broker connection diagnostics
- Account type verification
- Symbol discovery
- Tick ingestion
- Historical data import
- Order placement
- Position monitoring
- Stop-loss and take-profit management
- Trailing stops
- Reconnection
- Duplicate-order prevention
- Trade reconciliation
- Connection-loss handling

Only permit demo-account execution in the initial release.

Verify the account is actually a demo account before submitting any order.

Do not assume all brokers have identical contract sizes, trading hours, symbol names, or minimum stop distances.

# 11. TRADING MODES

Implement four modes:

**Mode A — Research Only**

Analyze markets without placing trades.

**Mode B — Virtual Autopilot**

Generate and simulate trades automatically.

**Mode C — MT5 Demo Autopilot**

Place and manage actual demo-account orders, subject to demo activation and risk gates.

**Mode D — Live Trading**

Disabled and inaccessible for execution in V1.

Future live trading must require an explicitly approved separate release and owner authorization.

Within any future approved live release, provide signal-only and automatic execution as separate modes.

A high AI maturity score must never independently authorize real-money trading.

# 12. DYNAMIC RISK MANAGEMENT

Every trade must have a broker-side protective stop loss wherever supported.

Use dynamic risk/reward selection based on market conditions.

Evaluate 1:1.5, 1:2, 1:3, and 1:4 configurations, plus evidence-based alternatives.

Do not assume a larger reward/risk ratio is automatically better.

Provide configurable:

- Risk per trade
- Maximum daily loss
- Maximum weekly loss
- Maximum drawdown
- Maximum concurrent trades
- Maximum spread
- Maximum slippage
- News blackout periods
- Trading sessions
- Emergency stop

Default to conservative demo risk limits.

Never increase position size simply to recover losses.

Create an independent kill switch that works even if the AI orchestrator fails.

# 13. PERSISTENT LEARNING MEMORY

Create separate permanent data stores for:

**Historical Memory**

Historical data, backtests, research experiments, and strategy performance.

**Virtual Memory**

Virtual trades, simulated costs, regime observations, and forward-test results.

**Demo Memory**

Actual MT5 demo orders, fills, costs, and execution performance.

**Future Live Memory**

A separate disabled schema for a future explicitly authorized live release.

Never mix results from different environments.

Do not expire learning records automatically.

Provide backups, retention controls, and data export.

Maintain model lineage and explain which evidence supported each promotion.

# 14. WEB DASHBOARD

Create a modern responsive dashboard with a professional dark trading-terminal interface.

Pages:

1. Command Center
2. Live Gold Chart
3. AI Agent Status
4. Strategy Laboratory
5. Virtual Trading
6. MT5 Demo Trading
7. Strategy Performance
8. Learning and Self-Healing
9. News and Macro Intelligence
10. AI Technology Research
11. Model Registry
12. Risk Management
13. Trade History
14. Broker Connections
15. Notifications
16. Settings and API Providers
17. System Logs
18. Deployment and GitHub Status

Display each agent's current activity and last successful run.

Show BUY, SELL, and NO TRADE signals with entry, stop loss, TP1, TP2, TP3, confidence calibration, and explanatory evidence.

Include strategy comparison, equity curves, drawdown charts, and profit/loss analytics.

Show the exact reason whenever a strategy is suspended, changed, or promoted.

# 15. ANDROID APPLICATION

Build a genuine Android application, not merely a website shortcut.

Preferred technology: Flutter.

Provide:

- Secure login
- Dashboard
- Gold market overview
- Virtual trades
- Demo trades
- AI agent activity
- Strategy performance
- Self-healing history
- News notifications
- Push notifications
- Risk settings
- Emergency stop
- Broker connection status
- AI provider health

Support real-time updates through authenticated WebSockets or equivalent technology.

Keep all broker credentials and AI API keys on the backend.

Generate an installable debug APK for testing and a properly signed release APK when signing credentials are securely configured.

Provide the exact APK output path and installation instructions.

Never claim an APK exists without completing the build and verifying the artifact.

# 16. WINDOWS VPS DEPLOYMENT

Design for a Windows VPS running MT5.

Run backend services independently of the ChatGPT desktop application's session.

The trading platform must continue functioning when ChatGPT Codex is closed.

Use Windows services or an equivalent supervised process manager for long-running components.

Provide:

- Automated installation scripts
- Environment configuration
- Database setup
- Service startup
- Health checks
- Restart recovery
- Secure remote dashboard access
- TLS/HTTPS
- Backup and restore
- Monitoring and alerts

Prefer PostgreSQL, Python FastAPI, Redis where appropriate, and a React/Next.js web frontend.

Provide a documented deployment architecture for Windows.

# 17. GITHUB AND CODEX WORKFLOW

Use GitHub as the source-code repository.

Create a private repository named:

`omnex-aura-agentic-trading`

Use GitHub CLI and authenticated Git operations.

Create development branches and pull requests for significant changes.

Set up GitHub Actions for:

- Linting
- Unit tests
- Integration tests
- Security scanning
- Dependency scanning
- Backend builds
- Android builds
- Release packaging

Automatically commit and push tested code to development branches when authorized.

Do not automatically merge unreviewed AI-generated trading changes into production.

Require approval for deployment of executable trading changes.

Never commit API keys, MT5 credentials, secrets, or signing keys.

Include `.env.example`, setup documentation, architecture documentation, and operational runbooks.

# 18. AUTOMATED TESTING

Implement at least these 11 test categories:

1. Unit testing
2. Integration testing
3. System testing
4. Functional testing
5. Regression testing
6. Performance testing
7. Load and stress testing
8. Security testing
9. Compatibility testing
10. End-to-end testing
11. User acceptance testing

Additionally implement trading-specific validation:

- Historical backtesting
- Walk-forward testing
- Out-of-sample testing
- Monte Carlo analysis
- Transaction-cost stress testing
- Market-regime stress testing
- News volatility testing
- Model drift testing
- Broker disconnection testing
- VPS restart testing
- Duplicate-order prevention
- Risk-engine failure testing
- Strategy rollback testing

Link test cases to acceptance criteria.

Generate test reports and evidence.

# 19. DEVELOPMENT MILESTONES

**Milestone 1 — Foundation**

Repository, architecture, backend, database, authentication, configuration, and deployment framework.

**Milestone 2 — Market Data**

MT5 demo connection, historical ingestion, live ticks, broker metadata, and data validation.

**Milestone 3 — Trading Research**

Technical analysis, macro data, initial strategies, backtesting, and performance analytics.

**Milestone 4 — Multi-Agent AI**

OpenAI, Claude, Grok adapters, orchestrator, specialized agents, and structured decision records.

**Milestone 5 — Virtual Autopilot**

Realistic virtual order engine, trade history, portfolio accounting, and two-/three-day evaluation.

**Milestone 6 — Self-Healing**

Drift detection, challenger creation, walk-forward validation, model registry, strategy promotion, and rollback.

**Milestone 7 — MT5 Demo Autopilot**

Demo execution, risk controls, order reconciliation, and fault recovery.

**Milestone 8 — Dashboard and Android**

Web administration, Flutter application, push notifications, and installable APK.

**Milestone 9 — Continuous Research**

AI trading technology research, candidate experimentation, and research reporting.

**Milestone 10 — Release and Operations**

Automated tests, GitHub CI/CD, VPS deployment, backups, monitoring, documentation, and final acceptance testing.

# 20. ACCEPTANCE CRITERIA

The project is not complete unless:

- Multiple agents genuinely execute independent functions.
- AI providers are integrated through configurable official APIs.
- MT5 demo connectivity works.
- Virtual trading operates without manual intervention.
- Every trade is recorded with realistic costs.
- Two-/three-day evaluation cycles run automatically.
- Poor performance triggers diagnosis and controlled research.
- Promising challenger strategies are independently validated.
- Champion strategies are retained when challengers are not demonstrably better.
- Historical and forward-test data remain separate.
- Learning memory persists after restart.
- The risk engine blocks prohibited trades.
- No real-money order can be submitted in V1.
- The dashboard displays live system state.
- The Android APK is successfully built and tested.
- GitHub CI tests pass.
- Windows VPS services recover after reboot.
- Every deployment has a version and rollback path.
- The system can explain why it traded, paused, or changed strategy.

# 21. FIRST CODEX EXECUTION INSTRUCTIONS

Start immediately by inspecting the development environment.

1. Detect Windows version and installed development tools.
2. Check Python, Git, Node.js, Flutter, Android SDK, PostgreSQL, and MT5 availability.
3. Identify missing dependencies and install safe development prerequisites with appropriate permissions.
4. Check GitHub authentication.
5. Create the repository structure.
6. Write `ARCHITECTURE.md`, `ROADMAP.md`, `ACCEPTANCE_CRITERIA.md`, and `AGENTS.md`.
7. Implement Milestone 1.
8. Write and execute tests.
9. Commit tested changes.
10. Continue milestone by milestone.

At the end of each milestone, report:

- Features implemented
- Files created or modified
- Tests passed and failed
- Known limitations
- Security concerns
- Required credentials or approvals
- Next implementation tasks

Do not pretend unavailable APIs, broker connections, APK builds, or test results have succeeded.

If a required credential is missing, implement a mock adapter and continue other work, then clearly report the dependency.

**Final objective:** Deliver OMNEX AURA as a genuine multi-agent, adaptive, continuously learning XAUUSD research and trading platform, with automatic virtual experimentation, controlled strategy evolution, MT5 demo execution, Android access, and auditable GitHub-based development.

Begin implementation now.
