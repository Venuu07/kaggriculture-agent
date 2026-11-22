# What makes an AI farmer profitable, and what does competition cost?

*An empirical study of a tool-using, look-ahead LLM agent on the official Kaggriculture rules.*

## Abstract

We build an agentic farm manager on the official rules engine of the Kaggle simulation
competition Kaggriculture and ask four questions. **(RQ1)** Which component of the agent
earns the money? **(RQ2)** Can the agent improve itself by reflecting on past seasons?
**(RQ3)** What does a competitor on the same market cost? **(RQ4)** Who wins when agents meet
head-to-head? An ablation over five seeds shows that **look-ahead simulation is the most
valuable component (−29% profit without it)**, followed by land expansion (−26%) and animals
(−19%). A *verified reflection* loop, in which every lesson is tested in simulation before it
is adopted, takes a novice agent from $53.3k to $67.6k (**+27%**) on held-out seasons and
correctly rejects lessons that do not generalise. In a two-player round-robin on a shared
market, a smart agent facing a copy of itself loses **about 45% of its profit**. The team that
earns the most on average does not win the most games: its look-ahead assumes a naive rival.
**(RQ5)** Real Gemini seasons show that a real LLM **under-uses its tools** (it never simulated a
plan on its own), and that a one-rule *test-before-act* policy raises its profit by 18.5%.

> **Scope of the claims.** RQ1–RQ4 use the **offline reasoner**: a
> deterministic, rule-based stand-in that drives the same ReAct loop, tools, memory, guardrails
> and multi-agent code as a real LLM, but is not a language model. The findings are therefore
> about the *agent architecture* (tools, look-ahead, coordination, verified reflection), not
> about any particular model. Real-LLM numbers can be added with
> `python -m kagri.evaluate --provider gemini --seeds 1`. **RQ5 uses real Gemini seasons.**

## 1. Setup

| Item | Value |
|---|---|
| Rules | Official `kaggriculture.py` (kaggle-environments 1.33.3), vendored unchanged |
| Season | 30 days × 24 turns, $3,000 start, 10×10 farm in four quadrants |
| Decision rate | One plan per day; the Foreman executes 24 turns |
| Extension | Seeded weather and events (drought, heavy rain, pests, price shocks); optional real historical weather |
| Opponent (RQ1, RQ2) | Kaggle's built-in "starter" bot on the shared market |
| Metric | Profit = final cash − $3,000 (unsold stock is worth nothing, as in the competition) |
| Determinism | Fixed seeds; identical plans give identical results (tested) |

## 2. RQ1: Which component earns the money? (ablation)

Each variant switches off one component of the full multi-agent system. 5 seeds per variant
(`python -m kagri.ablation`, `results/ablation.csv`, `results/ablation.png`).

| Variant | Mean profit | Change vs full | Seeds worse |
|---|---|---|---|
| **Full system** | **$88,794** | – | – |
| No look-ahead (plans never simulated) | $63,281 | **−$25,513 (−28.7%)** | 5/5 |
| No land expansion | $66,044 | −$22,750 (−25.6%) | 5/5 |
| No animals | $71,805 | −$16,988 (−19.1%) | 5/5 |
| No team (single agent) | $79,344 | −$9,450 (−10.6%) | 5/5 |
| No glut-awareness (one crop everywhere) | $79,436 | −$9,358 (−10.5%) | 5/5 |
| Small workforce (max 4 hands) | $84,549 | −$4,245 (−4.8%) | 4/5 |

**Reading.** Every component pays its way. The biggest single gain comes from *testing a plan
before acting*: without `simulate_action`, the agent cannot weigh an expensive investment today
against its payoff 8–10 days later. Animals matter mostly through fertiliser (one unit per
animal per day, worth about $100), not through eggs or milk.

## 3. RQ2: Can the agent learn from its own seasons? (verified reflection)

Plain reflection (write lessons, put them in the next prompt) produced no measurable gain with
the offline reasoner (`results/reflection.png`, flat). So we turned reflection into an
experiment loop (`python -m kagri.reflection`):

1. The learner starts as a **novice**: crops only, no animals, no land.
2. After each training season, six evidence-driven lesson templates fire when their evidence is
   present (e.g. "never bought an animal", "melons sold at 40% of base price", "up to 9 weeds").
   Each lesson maps to a concrete strategy change.
3. Each candidate is played on **4 validation seasons**; it is adopted only if it raises
   validation profit by at least 1%.
4. Progress is scored on **4 held-out test seasons** never used for training or validation.

| After season | Held-out profit | Adopted |
|---|---|---|
| 0 (novice) | $53,273 | – |
| 1 | **$67,626 (+27%)** | "Buy land" (+30% on validation) |
| 2–4 | $67,626 | nothing passed: animals +0.4%, labour +0.9%, look-ahead −0.8%, glut −1.9% |

**Reading.** The loop finds the lesson that matters in one season and then, importantly,
**refuses** lessons that look sensible but do not transfer. One example is "plant fewer
melons", which costs 1.9% on unseen seasons. Animals help the full team (RQ1) but add little to a
single agent that already has land. Lessons are context-dependent, which is exactly why they
should be verified rather than trusted.

## 4. RQ3: What does a rival on the same market cost?

Each agent plays (a) Kaggle's weak starter bot and (b) a copy of itself, on 3 seeds and both
seat orders (`python -m kagri.arena`, `results/arena_ratings.csv`, `results/arena.png`).

| Agent | Profit vs starter bot | Profit vs itself | Price of competition |
|---|---|---|---|
| LLM single-agent | $72,474 | $39,881 | **−45.0%** |
| LLM multi-agent | $84,355 | $47,404 | **−43.8%** |
| Greedy heuristic | $30,498 | $23,416 | −23.2% |
| Random | $12,906 | $10,683 | −17.2% |

**Reading.** The smarter the agent, the more a twin hurts: two optimisers find the same
profitable niches (melons, strawberries, milk) and crash those prices together. The game's
price curves for premium goods fall to $1 after a modest glut, so the market cannot absorb two
competent farmers growing the same thing.

## 5. RQ4: Who wins head-to-head?

Round-robin tournament between our four agents and Kaggle's starter bot, rated with
**Bradley-Terry** (the method Kaggriculture used for its final leaderboard). Only wins count.

| # | Agent | Rating | Win rate | Mean profit |
|---|---|---|---|---|
| 1 | LLM single-agent | 2434 | 96% | $55,393 |
| 2 | LLM multi-agent | 2124 | 75% | $61,390 |
| 3 | Greedy heuristic | 1815 | 54% | $30,549 |
| 4 | Random | 979 | 25% | $10,259 |
| 5 | Kaggle starter bot | 147 | 0% | $580 |

**Reading.** The multi-agent team earns the most on average, yet the single agent beats it in
**all 6** direct games. The cause is in the look-ahead: `simulate_action` models the rival as
the starter bot. The team trusts its simulations more (8-day horizon, three candidates), so it
invests harder in the same crops as a smart rival and suffers a deeper glut. **Planning with a
wrong opponent model is worse than planning less.** This motivates opponent-aware look-ahead
(future work).

## 6. RQ5: How does a real LLM behave?

We recorded three full seasons with **Google Gemini** (free tier, `gemini-3.6-flash` with
`3.5-flash` / `3.1-flash-lite` as rate-limit fallbacks) on seed 0, the same farm and weather as
the other agents' seed-0 runs (`runs/recorded_*.jsonl`, replayable in the dashboard).

| Agent (seed 0, same farm and weather) | Profit | LLM calls | Days using tools | Simulations | Guardrail fixes | Cost (list price) |
|---|---|---|---|---|---|---|
| LLM multi-agent, offline reasoner | $98,156 | – | 30 / 30 | 76 | 0 | $0 |
| LLM single-agent, offline reasoner | $81,188 | – | 30 / 30 | 48 | 0 | $0 |
| **Gemini single-agent + test-before-act** | **$48,617** | 90 | 29 / 30 | 30 | 40 | $0.067 |
| **Gemini single-agent** | **$41,018** | 34 | 2 / 30 | **0** | 0 | $0.027 |
| **Gemini multi-agent team** | **$31,197** | 123 | 3 / 30 | 1 | 16 | $0.079 |
| Greedy heuristic | $29,709 | – | – | – | – | $0 |
| Random | $6,667 | – | – | – | – | $0 |

**Findings.**
1. **Real LLMs under-use their tools.** Left alone, Gemini used a tool on 2 of 30 days and
   **never simulated a plan**. It behaved like the "no look-ahead" ablation of RQ1, and its profit
   ($41k) sits far below the tool-heavy offline reasoner ($81k), though above Greedy (+38%).
2. **A one-rule policy helps.** *Test-before-act* (if the model tries to commit without
   simulating, the loop asks it to simulate first) made Gemini simulate on 29 of 30 days and
   raised profit **+18.5%** ($41.0k → $48.6k) for 4 extra cents.
3. **More agents is not automatically better.** The real multi-agent team made 3.6× the calls of
   the single agent but simulated once all season and earned the least ($31.2k). Specialists that
   each skip the tools add coordination cost without adding thinking. With the offline reasoner,
   where every role does use the tools, the team was the best agent, so *how* agents use tools
   matters more than *how many* agents there are.
4. **Guardrails are load-bearing with real models.** Gemini planned 25 plots with 0 workers, and
   spent all but $68 on day 0 (land + 24 melons). The labour and budget guardrails fixed these
   (16–40 times per season), and no season needed a single fallback plan.
5. **Cost is negligible; rate limits are not.** A season costs 3–8 cents at list price ($0 on the
   free tier). The real constraint is the free tier's 5 requests per minute per model: a
   single-agent season takes about 20–40 minutes and the team over an hour.

**Caveat.** One seed per configuration: these are case studies, not significance tests. They
are consistent with RQ1, where removing look-ahead cost 29%.

## 7. Robustness: the Scenario Lab

Six scripted crises (random events off, so each is a controlled experiment), seed 0, AI team vs
Greedy; each agent's calm-season profit on the same farm is the control
(`python -m kagri.scenarios`, `results/scenarios.json`).

| Scenario | AI team | Greedy |
|---|---|---|
| Calm (control) | $85,525 | $34,439 |
| **Melon market crash** (days 11, 18) | **$34,930** (41% of calm) | **−$755** |
| Drought week (days 6–13) | $77,855 (91%) | $34,439 (100%) |
| Pest wave (days 8, 14, 20) | $64,485 (75%) | $31,131 (90%) |
| Monsoon with fungus | $77,732 (91%) | $34,813 (101%) |
| Festival demand boom | $78,245 (92%) | $34,439 (100%) |

The AI stays far ahead in every crisis. Diversification acts as insurance: the melon crash wipes
out Greedy's all-melon season. In *relative* terms Greedy is often hit less, because it does less
(fewer plants and animals at risk). **Known weakness:** when the shed is nearly full, a
"sell everything" rule fires even after a price crash (in the melon scenario it sold 95 melons at
$1). Freeing only the space needed, cheapest items first, is the obvious fix.

## 8. Generalisation: the same agent core in a second world

`kagri/agents/core.py` holds the ReAct loop, with no farm code in it. The farm agent and a
**kirana-store agent** (`kagri/shop/`) both call it; only the tools, prompt and simulator differ.
The store has perishables (milk spoils in 2 days), price-sensitive demand, heatwaves, festivals,
rival promotions and supplier delays.

| 5 seeds, 30 days, start ₹10,000 | Mean profit | Customers turned away | Units wasted |
|---|---|---|---|
| **AI shopkeeper** (same core, simulate_plan) | **₹61,815** | 237 | 5 |
| Fixed restock rule | ₹35,653 | 1,671 | 3 |

The same pattern (forecast, simulate candidate plans, commit the best within guardrails) earns
**+73%** in a domain it was never designed for. That is the evidence behind "where is this useful".

## 9. Threats to validity

- **Offline reasoner.** Its strength reflects our domain rules; a real LLM may choose
  differently. The architecture claims (look-ahead, verification, coordination) still hold,
  because the ablations switch those parts off in the same system.
- **Few seeds.** 3–5 seeds per cell. The ablation directions are consistent (5/5 seeds worse
  for every component except labour), but small effects (< 2%) are within noise.
- **Weak default opponent.** Hence the Arena experiments with self-play.
- **Our weather layer** is an extension. `--no-events` gives competition-pure runs, and
  real-weather mode replaces the random weather with historical data.

## 10. Future work

1. **Opponent-aware look-ahead:** simulate the rival as a copy of ourselves, or infer its
   strategy from its visible farm (the observation shows the rival's tiles).
2. **Real-LLM evaluation** across Gemini, Groq, Claude and OpenAI: profit against cost against latency.
3. **Verified reflection for LLMs:** let the model propose free-form lessons and verify them with
   the same simulation gate.
4. **Real markets:** drive prices with mandi price series (Agmarknet) alongside the real-weather mode.
5. **Learning baselines:** a PPO policy on `FarmEnv` for an LLM-vs-RL comparison.

## 11. Reproduce everything

```bash
python -m kagri.evaluate      # main comparison (~1 min)
```
```bash
python -m kagri.ablation      # RQ1 (~1 min)
```
```bash
python -m kagri.reflection    # RQ2 (~2 min)
```
```bash
python -m kagri.arena         # RQ3 + RQ4 (~1 min)
```
```bash
python -m kagri.scenarios     # robustness (~10 s)
```
```bash
python -m kagri.shop          # second world (~1 s)
```
```bash
python -m pytest              # 24 tests
```
