"""Builds the major-project report PDF (HTML + WeasyPrint) in the layout of the department template."""
from __future__ import annotations

import html
from pathlib import Path

import weasyprint

HERE = Path(__file__).parent
TITLE = "Intelligent Decision-Making Agent for Dynamic Resource Management in Kaggriculture"
SHORT = "INTELLIGENT DECISION-MAKING AGENT FOR KAGGRICULTURE"
STUDENTS = [("Chintakunta Venu", "B210834"), ("Raghu Ram Reddy Katkuri", "B211518"), ("Manoj Kumar Deekonda", "B210947")]
GUIDE, GUIDE_ROLE = "Mrs. K Govardhini", "Assistant Professor"
HOD, HOD_ROLE = "Dr. B Venkat Raman", "Assistant Professor"
MONTH, DATE = "NOVEMBER 2026", "23-11-2026"

toc: list[tuple[int, str, str, str]] = []  # (level, number, title, anchor)
figs: list[tuple[str, str, str]] = []
tabs: list[tuple[str, str, str]] = []
body: list[str] = []
state = {"ch": 0, "sec": 0, "sub": 0, "fig": 0, "tab": 0, "first": True}


def esc(s: str) -> str:
    return s  # content is trusted, may contain inline HTML


def chapter(title: str) -> None:
    state["ch"] += 1
    state.update(sec=0, sub=0, fig=0, tab=0)
    n = state["ch"]
    cls = "chapter first" if state["first"] else "chapter"
    state["first"] = False
    a = f"ch{n}"
    toc.append((0, str(n), title, a))
    body.append(f'<div class="{cls}" id="{a}"><div class="chapnum">Chapter {n}</div><h1>{title}</h1></div>')


def sec(title: str) -> None:
    state["sec"] += 1
    state["sub"] = 0
    num = f'{state["ch"]}.{state["sec"]}'
    a = "s" + num.replace(".", "_")
    toc.append((1, num, title, a))
    body.append(f'<h2 id="{a}"><span class="n">{num}</span>{title}</h2>')


def sub(title: str) -> None:
    state["sub"] += 1
    num = f'{state["ch"]}.{state["sec"]}.{state["sub"]}'
    a = "s" + num.replace(".", "_")
    toc.append((2, num, title, a))
    body.append(f'<h3 id="{a}"><span class="n">{num}</span>{title}</h3>')


def p(*paras: str) -> None:
    for t in paras:
        body.append(f"<p>{esc(t)}</p>")


def ul(items: list[str], ordered: bool = False) -> None:
    tag = "ol" if ordered else "ul"
    body.append(f"<{tag}>" + "".join(f"<li>{esc(i)}</li>" for i in items) + f"</{tag}>")


def table(caption: str, headers: list[str], rows: list[list[str]], widths: list[str] | None = None, small: bool = False) -> None:
    state["tab"] += 1
    num = f'{state["ch"]}.{state["tab"]}'
    a = f"t{num.replace('.', '_')}"
    tabs.append((num, caption, a))
    cols = "".join(f'<col style="width:{w}">' for w in widths) if widths else ""
    head = "".join(f"<th>{h}</th>" for h in headers)
    rws = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    body.append(f'<div class="tbl{" small" if small else ""}" id="{a}"><div class="cap">Table {num}: {caption}</div>'
                f"<table><colgroup>{cols}</colgroup><thead><tr>{head}</tr></thead><tbody>{rws}</tbody></table></div>")


def fig(img: str, caption: str, width: str = "85%") -> None:
    state["fig"] += 1
    num = f'{state["ch"]}.{state["fig"]}'
    a = f"f{num.replace('.', '_')}"
    figs.append((num, caption, a))
    body.append(f'<div class="fig" id="{a}"><img src="img/{img}" style="width:{width}"><div class="cap">Figure {num}: {caption}</div></div>')


def code(text: str) -> None:
    body.append(f"<pre>{html.escape(text)}</pre>")


def pagebreak() -> None:
    body.append('<div class="pb"></div>')


# =============================================================== CHAPTER 1
chapter("Introduction")
sec("Overview")
p("Agriculture is, at its heart, a chain of economic decisions taken under uncertainty: what to plant, how much "
  "labour to hire, when to invest in land or livestock, and when to sell. Each decision has a delayed effect, a crop "
  "may take ten days to mature, and the market reacts to what everyone else is selling. Good decisions therefore need "
  "planning, not only prediction.",
  "This project builds an <b>agentic AI farm manager</b> for <b>Kaggriculture</b>, a Kaggle simulation competition in "
  "which an autonomous agent runs a farm for a 30-day season (720 turns) and is judged on the cash it holds at the end. "
  "The agent does not simply map an input to an output as a conventional machine-learning model does. Every day it "
  "observes the farm, reasons about it, calls tools (price-impact calculators, profit estimators and a look-ahead "
  "simulator), checks its own plan against safety rules, and then commits a decision. Over many seasons it learns "
  "lessons that it verifies before adopting.",
  "The system runs on the <b>official competition rules engine</b>, is evaluated against classic baselines and a real "
  "large language model (Google Gemini), and is presented through an interactive web dashboard in which a user can "
  "watch the agent think, play against it, or throw crises at it. The same agent core is also shown running a second, "
  "completely different business, a neighbourhood grocery (kirana) store, to demonstrate that the approach "
  "generalises beyond farming.")
sec("Problem Background")
p("Kaggriculture models the difficulties of real farm management in a compact, measurable game. Two players start "
  "with $3,000 and a 5x5 field, and can grow five crops (wheat, carrot, tomato, strawberry, melon), raise three kinds "
  "of animals (goose, cow, sheep), hire farm hands, buy more land and trade on a shared market.",
  "Three properties make the problem hard. First, <b>delayed rewards</b>: money spent today on melon seeds or a cow "
  "returns only after many days. Second, a <b>reactive market</b>: every unit sold lowers the price, and premium "
  "goods such as melons fall to $1 after a modest glut, so the most obvious strategy, planting the most valuable crop "
  "everywhere, destroys its own profit. Third, <b>operational risk</b>: plants that are not watered for two days die, "
  "animals that are not fed escape, and a competitor shares the same market.",
  "A simple rule-based player therefore performs poorly, while reinforcement learning needs very many episodes and "
  "produces policies that are difficult to explain. Large language models (LLMs) can reason in natural language and "
  "call external tools, which makes them a promising basis for an agent that can plan, explain and stay safe.")
sec("Project Motivation")
p("The motivation was to build a decision-making agent that is <b>profitable, explainable and safe</b>, and to study "
  "it scientifically rather than only demonstrate it. We wanted to answer concrete questions: Which part of an agentic "
  "system actually creates value? Can an agent improve by reflecting on its own mistakes? What happens when two smart "
  "agents compete for one market? How does a real LLM behave compared with a carefully engineered reasoner?",
  "A second motivation was practicality. Free LLM tiers are rate-limited and internet access during a demonstration "
  "is not guaranteed, so the system had to work fully offline, replay recorded runs, and never crash in front of an "
  "audience.")
sec("Objectives of the Project")
ul(["Wrap the official Kaggriculture rules as a deterministic, gym-style environment in which one step is one day.",
    "Implement baseline agents (Random and a Greedy heuristic) as reference points.",
    "Build a ReAct-style agent that reasons, calls tools, simulates plans before acting and keeps short-term and long-term memory.",
    "Add a multi-agent mode (Planner, Market Analyst, Agronomist, coordinated by a Manager) and guardrails that make every plan safe.",
    "Support several LLM providers (Gemini, Groq, OpenAI, Claude) and a fully offline reasoner behind one interface.",
    "Evaluate all agents over multiple seeds and answer five research questions with reproducible experiments.",
    "Deliver an interactive dashboard: live farm, reasoning trace, Play vs AI, Scenario Lab, Arena, Research and a second (shop) world."])
sec("Scope of the Project")
p("The project covers the complete pipeline from simulation to presentation:")
ul(["A faithful simulator built on the vendored official engine, with an optional weather and events layer and a real-weather mode for Indian districts.",
    "A Foreman executor that turns one daily plan into 24 turns of low-level commands for the farmer and hired hands.",
    "An agentic core with eight tools, memory, reflection, a multi-agent team and safety guardrails.",
    "An evaluation suite: baseline comparison, ablation study, verified reflection, two-player tournament, crisis scenarios and real-LLM case studies.",
    "A React dashboard served by a FastAPI backend, usable with or without internet and API keys.",
    "A second environment (a kirana store) driven by the same agent core, demonstrating generality."])
p("Out of scope are submitting to the (closed) Kaggle ladder, per-turn LLM control of all 720 turns, and training a "
  "reinforcement-learning policy, which is discussed as future work.")
sec("Significance of the Project")
p("The project shows that an agent which <b>tests its plans in a simulator before acting</b> earns about three times "
  "the profit of a classic heuristic, and it quantifies why: removing look-ahead alone costs 29% of profit. It shows "
  "that safety guardrails are essential when a real LLM is in control, that a real LLM tends to under-use its tools, "
  "and that a one-rule policy (test before you act) recovers part of that gap.",
  "Beyond farming, the same pattern, observe, reason with tools, simulate, act within guardrails and learn from "
  "verified lessons, applies wherever decisions repeat under uncertainty and a simulator of the world can be built: "
  "inventory and retail pricing, supply chains, perishable goods, energy scheduling and farm advisory with real weather.")

# =============================================================== CHAPTER 2
chapter("Literature Survey")
sec("Review of Related Work")
sub("ReAct: Reasoning and Acting in Language Models")
p("<b>Authors:</b> Yao, Zhao, Yu, Du, Shafran, Narasimhan and Cao (2022). <b>Publication:</b> ICLR 2023.",
  "<b>Summary:</b> ReAct interleaves natural-language reasoning traces with actions such as tool calls. The model "
  "writes a thought, chooses an action, reads the observation that the action returns and repeats until it can answer. "
  "Interleaving makes the reasoning grounded in real observations and the actions explainable.",
  "<b>Relevance:</b> our daily decision loop (thought, tool, observation, ..., take_action) follows ReAct directly. "
  "The reasoning trace of every day is logged and displayed in the dashboard's Agent's Mind view.")
sub("Reflexion: Language Agents with Verbal Reinforcement Learning")
p("<b>Authors:</b> Shinn, Cassano, Gopinath, Narasimhan and Yao (2023). <b>Publication:</b> NeurIPS 2023.",
  "<b>Summary:</b> instead of updating model weights, a Reflexion agent writes verbal feedback about a failed episode "
  "and stores it in memory; later episodes read these reflections and avoid repeating the mistake.",
  "<b>Relevance:</b> our long-term memory stores lessons after every season. We extend the idea with <b>verified "
  "reflection</b>: each lesson is tested in simulation on unseen seasons and adopted only if it helps.")
sub("Toolformer: Language Models Can Teach Themselves to Use Tools")
p("<b>Authors:</b> Schick et al. (2023). <b>Publication:</b> NeurIPS 2023.",
  "<b>Summary:</b> shows that language models can learn when to call external APIs such as calculators and search "
  "engines, improving accuracy on tasks the model cannot solve alone.",
  "<b>Relevance:</b> our agent relies on tools for everything numerical: price impact, crop profit, sale proceeds and "
  "plan simulation. We use prompted tool calling with a fixed, documented tool list rather than training.")
sub("Multi-Agent LLM Frameworks (AutoGen, CAMEL)")
p("<b>Authors:</b> Wu et al. (2023); Li et al. (2023). <b>Publication:</b> arXiv 2308.08155; NeurIPS 2023.",
  "<b>Summary:</b> several LLM agents with different roles converse to solve a task, which can improve coverage and "
  "self-checking compared with a single agent.",
  "<b>Relevance:</b> our team mode uses fixed roles with restricted tools (Planner, Market Analyst, Agronomist) and a "
  "Manager that merges their proposals and resolves conflicts. This is cheaper and easier to audit than free conversation.")
sub("Reinforcement Learning for Crop Management (CropGym)")
p("<b>Authors:</b> Overweg, Berghuijs and Athanasiadis (2021). <b>Publication:</b> arXiv 2104.04326.",
  "<b>Summary:</b> provides a gym environment for fertiliser and crop decisions and trains reinforcement-learning "
  "agents on it.",
  "<b>Relevance:</b> we follow the gym interface (reset and step) but use an LLM-style agent that needs no training "
  "and explains each decision. An RL comparison is listed as future work.")
sec("Existing Systems")
sub("Rule-Based Heuristics")
p("Fixed rules, for example 'plant the crop with the highest margin on every free plot and sell when the price is above "
  "average', are simple and fast. They ignore their own market impact and have no notion of risk or investment timing. "
  "Our Greedy baseline represents this family.")
sub("Reinforcement-Learning Agents")
p("Trained policies can be strong but need thousands of simulated seasons, careful reward design and retraining "
  "whenever the rules change. Their decisions are hard to explain to a farmer or an examiner.")
sub("Kaggle Built-in Bots")
p("The competition ships 'pass', 'random' and 'starter' bots. The starter bot runs a simple carrot loop and ends a "
  "season close to its starting money; it is used as the default opponent on our shared market.")
sub("General LLM Chat Assistants")
p("A chat assistant can give farming advice in text but does not act, cannot test a plan against a simulator, has no "
  "memory of past seasons and offers no safety checks on what it suggests.")
sec("Proposed System")
p("We propose an agentic decision system in which an LLM (or an offline reasoner speaking the same protocol) acts as "
  "the farm's manager. Once per day it observes a compact state, reasons step by step, calls tools, and tests "
  "candidate plans on a copy of the farm before committing. A guardrail layer validates every plan (budget, labour, "
  "timing), and a deterministic Foreman executes the validated plan over 24 turns. After each season the agent "
  "reflects, and in verified-reflection mode every lesson is tested before it is kept. The key features are listed in "
  "Table 2.1.")
table("Key Features of the Proposed System", ["S.No", "Feature", "Description"], [
    ["1", "Official rules engine", "Vendored Kaggriculture engine wrapped as a deterministic gym environment"],
    ["2", "ReAct reasoning", "Think, call a tool, observe, repeat, then commit one daily plan"],
    ["3", "Look-ahead simulation", "simulate_action plays a candidate plan on a copy of the farm"],
    ["4", "Memory and reflection", "Season log in the prompt; lessons verified on unseen seasons"],
    ["5", "Multi-agent team", "Planner, Market Analyst and Agronomist proposals merged by a Manager"],
    ["6", "Guardrails", "Plan validation, budget and labour checks, safe fallback plan"],
    ["7", "Provider choice", "Gemini, Groq, OpenAI, Claude or a fully offline reasoner"],
    ["8", "Interactive dashboard", "Live farm, reasoning trace, Play vs AI, Scenario Lab, Arena, Research"],
    ["9", "Second world", "The same agent core runs a kirana store"],
], ["8%", "28%", "64%"])
sec("Comparative Analysis of Existing Systems")
Y, N = "&#10003;", "&#10007;"
table("Comparative Analysis of Existing Systems", ["Feature", "Heuristic", "RL Agent", "Kaggle Bot", "Chat LLM", "Proposed"], [
    ["Plans ahead (look-ahead)", N, "Partial", N, N, Y],
    ["Accounts for own market impact", N, "Partial", N, N, Y],
    ["Explains each decision", "Partial", N, N, Y, Y],
    ["Uses tools / simulator", N, N, N, N, Y],
    ["Learns across seasons", N, Y, N, N, Y],
    ["Safety guardrails", N, N, N, N, Y],
    ["Works offline", Y, Y, Y, N, Y],
    ["No training required", Y, N, Y, Y, Y],
    ["Generalises to new domains", N, N, N, "Partial", Y],
], ["31%", "13%", "13%", "13%", "13%", "17%"])

# =============================================================== CHAPTER 3
chapter("System Analysis")
sec("Problem Definition")
p("Given the official Kaggriculture rules, a starting budget of $3,000 and a 30-day season, design an autonomous agent "
  "that chooses each day which crops to plant, which animals and land to buy, how many hands to hire, which goods to "
  "fertilise and how much stock to sell, so as to maximise cash at the end of the season, while explaining every "
  "decision and never taking an unsafe or invalid action.",
  "Formally, the environment is a sequential decision process with state <i>s<sub>t</sub></i> (farm tiles, cash, shed "
  "stock, prices, weather), daily action <i>a<sub>t</sub></i> (a plan) and reward equal to the change in cash. The "
  "objective is to maximise the profit, final cash minus $3,000.")
sec("System Requirements")
sub("Functional Requirements")
ul(["<b>Simulation:</b> reset and step a season deterministically from a seed, on the official rules.",
    "<b>Planning:</b> accept a daily plan (plant, sell, buy animals, fertilise, hands, buy land) and execute it over 24 turns.",
    "<b>Validation:</b> reject or trim invalid plan parts with a reason and never crash.",
    "<b>Reasoning:</b> provide tools for state, weather, prices, profit estimates, sale estimates and look-ahead simulation.",
    "<b>Memory:</b> keep a rolling season log and store lessons after each season.",
    "<b>Coordination:</b> run single-agent and multi-agent modes with a selectable LLM provider.",
    "<b>Evaluation:</b> evaluate agents over N seeds and output tables and charts; run ablation, reflection, arena and scenario studies.",
    "<b>Logging and replay:</b> log every day (thought, tool calls, results, plan, reward) to JSONL for offline replay.",
    "<b>Interaction:</b> a dashboard with live farm, reasoning trace, Play vs AI, Scenario Lab, Arena, Research, Results and the shop world."])
sub("Non-Functional Requirements")
ul(["<b>Reliability:</b> the demonstration must work without internet or API keys (replay mode and offline reasoner).",
    "<b>Safety:</b> guardrails on budget, labour and plan validity; bounded tool calls; automatic fallback plan.",
    "<b>Performance:</b> a full 720-turn game runs in about 0.03 s; an offline decision takes 0.1 to 0.2 s.",
    "<b>Reproducibility:</b> fixed seeds; every experiment reproducible with one command.",
    "<b>Portability:</b> runs on Windows, Linux and macOS with Python 3.11 or newer.",
    "<b>Security:</b> API keys kept only in a local .env file that is excluded from version control.",
    "<b>Maintainability:</b> typed Python, documented modules, 24 automated tests, configuration in one YAML file."])
sub("Software Requirements")
table("Software Requirements", ["Component", "Requirement"], [
    ["Operating system", "Windows 10/11, Ubuntu 22.04+ or macOS"],
    ["Language runtime", "Python 3.11 or newer"],
    ["Python packages", "fastapi, uvicorn, pandas, matplotlib, pyyaml, requests, python-dotenv, pytest"],
    ["Frontend (only to rebuild)", "Node.js 18+, React 18, TypeScript, Vite, Recharts"],
    ["Browser", "Any modern browser (Chrome, Edge, Firefox)"],
    ["Optional services", "Google Gemini or Groq API key; Open-Meteo archive (no key)"],
], ["35%", "65%"])
sub("Hardware Requirements")
ul(["Processor: any dual-core x86-64 or ARM CPU; no GPU required.",
    "Memory: 4 GB RAM or more.",
    "Storage: about 200 MB for the project, recorded runs and results.",
    "Network: optional, only for real-LLM runs and fetching historical weather."])
sec("Feasibility Study")
p("<b>Technical feasibility:</b> the official engine is open source (Apache-2.0) and pure Python, so it can be vendored "
  "and driven directly. Deciding once per day keeps LLM usage within free-tier limits.",
  "<b>Economic feasibility:</b> all software is free and open source. A full real-LLM season costs 3 to 8 US cents at "
  "list prices and nothing on the free tier.",
  "<b>Operational feasibility:</b> the dashboard needs a single command (python -m kagri.serve) and works offline, so "
  "it can be demonstrated reliably on a student laptop.")
sec("System Objectives and Constraints")
sub("System Objectives")
ul(["Maximise end-of-season profit on the official rules.", "Make every decision explainable through a logged reasoning trace.",
    "Guarantee that no plan can overspend, starve the farm of labour or crash the system.", "Measure the contribution of each component scientifically."])
sub("System Constraints")
ul(["<b>Rate limits:</b> the Gemini free tier allows about 5 requests per minute per model; the system rotates between models.",
    "<b>Decision granularity:</b> the agent decides once per day; the Foreman handles the 24 turns, so per-turn micro-strategy is fixed.",
    "<b>Opponent:</b> evaluation uses Kaggle's starter bot on a shared market instead of the (closed) Kaggle ladder.",
    "<b>Extension:</b> the weather and events layer is our addition; it can be switched off for competition-pure runs."])

# =============================================================== CHAPTER 4
chapter("System Design")
p("System design translates the requirements into a structured architecture: the components, how data flows between "
  "them, and how a single daily decision is made, validated and executed.")
sec("System Architecture")
sub("Overview")
p("The system is layered. The <b>simulation layer</b> holds the official engine, the weather and events extension and "
  "the gym-style FarmEnv. The <b>execution layer</b> contains the guardrails, which validate a plan, and the Foreman, "
  "which turns it into per-turn commands. The <b>agent layer</b> contains the domain-neutral ReAct core, the tools, "
  "memory, the multi-agent roles and the LLM providers. The <b>presentation layer</b> is a FastAPI server and a React "
  "dashboard. Recorded runs and results are stored as JSONL, CSV and PNG files.",
  "One day flows through the layers as follows: the environment produces an observation; the agent reasons and calls "
  "tools (the simulate tool plays candidate plans on a deep copy of the environment); the chosen plan passes the "
  "guardrails; the Foreman executes it for 24 turns while the opponent plays on the same market; the reward and next "
  "observation return to the agent.")
sub("System Architecture Diagram")
fig("arch.png", "System Architecture Diagram", "92%")
sec("Data Flow Diagrams")
sub("DFD Level 0 - Context Diagram")
fig("dfd0.png", "DFD Level 0 - Context Diagram", "90%")
sub("DFD Level 1")
fig("dfd1.png", "DFD Level 1", "62%")
sec("UML Diagrams")
sub("Use Case Diagram")
fig("usecase.png", "Use Case Diagram", "78%")
sub("Class Diagram")
fig("classes.png", "Class Diagram", "100%")
sub("Sequence Diagram - One Daily Decision")
fig("sequence.png", "Sequence Diagram - One Daily Decision", "100%")
sub("Activity Diagram - Season Loop")
fig("activity.png", "Activity Diagram - Season Loop", "52%")
sub("Component Diagram")
fig("components.png", "Component Diagram", "82%")
sub("Deployment Diagram")
fig("deploy.png", "Deployment Diagram", "100%")
sec("Data Design")
sub("Overview")
p("The system has no database server; it stores structured files. Configuration lives in config.yaml; each recorded "
  "season is a JSONL file (one header line, one line per day and a summary line); evaluation results are CSV and JSON; "
  "lessons are JSON. This keeps the project portable and lets every run be replayed offline.")
table("Daily Plan Schema (agent action)", ["Field", "Type", "Meaning"], [
    ["plant", "{crop: plots}", "New plots to sow today (WHEAT, CARROT, TOMATO, STRAWBERRY, MELON)"],
    ["sell", "{product: qty | 'all'}", "Units to sell from the shed"],
    ["buy_animals", "{animal: n}", "Geese, cows or sheep; a coop or pasture is built for each"],
    ["fertilise", "[crop, ...]", "Crops to fertilise today"],
    ["hands", "0-10", "Farm hands hired for the day (Fibonacci wage)"],
    ["buy_land", "boolean", "Unlock the next 5x5 quadrant ($1,000 / $2,000 / $4,000)"],
], ["18%", "26%", "56%"])
sub("Run Log Data Model")
fig("datamodel.png", "Run Log Data Model", "60%")

# =============================================================== CHAPTER 5
chapter("System Implementation")
sec("Introduction")
p("The system is implemented in Python (agents, simulation, evaluation and API) and TypeScript (dashboard). The source "
  "is organised as a package, kagri, with sub-packages for the engine, agents, LLM providers and the shop world, plus a "
  "web folder for the React application. Configuration is centralised in kagri/config.yaml.")
sec("Technology Stack")
sub("Backend and Agent Technologies")
table("Backend and Agent Technologies", ["Technology", "Description", "Role in System"], [
    ["Python 3.11", "General-purpose language", "Agents, simulator, evaluation, API"],
    ["Kaggriculture engine", "Official rules (kaggle-environments 1.33.3)", "Game physics and market"],
    ["FastAPI + Uvicorn", "Asynchronous web framework and server", "REST API for runs, play, scenarios, shop"],
    ["pandas, matplotlib", "Data analysis and plotting", "Result tables and report charts"],
    ["pytest", "Testing framework", "24 automated tests"],
], ["24%", "38%", "38%"])
sub("Frontend Technologies")
table("Frontend Technologies", ["Technology", "Description", "Role in System"], [
    ["React 18 + TypeScript", "Component-based UI library", "All dashboard views"],
    ["Vite", "Build tool", "Bundles the UI into static files served by FastAPI"],
    ["Recharts", "React charting library", "Profit races, ablation and research charts"],
    ["Fraunces, IBM Plex (bundled)", "Typefaces packaged with the app", "Works offline, no CDN"],
], ["26%", "37%", "37%"])
sub("AI Services")
table("AI Services", ["Service", "Purpose", "Integration Method"], [
    ["Google Gemini (3.6 / 3.5 Flash)", "Primary real LLM", "REST generateContent, JSON mode, model fallback list"],
    ["Groq (Llama 3.3 70B)", "Fast free-tier alternative", "OpenAI-compatible chat completions"],
    ["OpenAI, Anthropic Claude", "Optional providers", "REST, same Provider interface"],
    ["Offline reasoner", "No-key, no-internet mode", "Rule-based, speaks the same JSON protocol"],
    ["Open-Meteo archive", "Historical weather", "REST, cached locally once"],
], ["30%", "28%", "42%"])
sub("Data Storage")
p("Runs are stored in runs/*.jsonl, results in results/ (CSV, JSON, PNG), lessons in memory/*.json and real weather in "
  "data/weather/*.json. API keys are read from a local .env file through python-dotenv.")
sec("Module Description")
sub("Environment and Engine Module")
p("<b>Purpose:</b> provide a faithful, deterministic simulator. The official kaggriculture.py is vendored unchanged "
  "except for removing the framework import and HTML renderer. A 60-line GameDriver runs both players turn by turn, "
  "and FarmEnv (kagri/env.py) wraps it as a gym environment where step(plan) plays one day.",
  "FarmEnv also adds the weather and events layer (sunny, cloudy, heavy rain, drought, pests, price shocks), a noisy "
  "three-day forecast, scripted scenarios for the Scenario Lab, and a real-weather mode. Its simulate(plan, days) "
  "method deep-copies the environment and plays a plan ahead, which is what the agent's look-ahead tool uses. "
  "view(player) lets the same game be driven from either seat for two-agent matches.")
sub("Guardrails and Foreman Module")
p("<b>Purpose:</b> make every plan safe and executable. validate_plan (kagri/plan.py) checks keys, numbers, free plots, "
  "budget (keeping a three-day feed reserve per animal) and timing (no crop that cannot ripen before day 29), and "
  "returns a clean plan plus the reasons for every change. For real LLMs two extra guardrails apply: a labour check "
  "that tops up hands when a plan is clearly under-staffed, and a working-capital check that keeps at least $300 or a "
  "week of wages after spending.",
  "The Foreman (kagri/foreman.py) converts the plan into 24 turns. It builds the day's market orders, lists the tasks "
  "on every tile (water, harvest, plant, feed, fertilise, dig weeds, build and place animals) and assigns the farmer "
  "and each hand to the nearest task by priority, with the farmer fetching feed and animals from the shed. On the last "
  "day it harvests everything sellable and sells it.")
sub("Agentic Core Module")
p("<b>Purpose:</b> the reasoning loop shared by every world. react_loop (kagri/agents/core.py) sends the system prompt "
  "and the day's message to the provider, parses a JSON reply {thought, action, args}, runs the requested tool, appends "
  "the result to the conversation and repeats until the model calls take_action. Guardrails inside the loop enforce a "
  "maximum of four tool calls, restrict each role to its tools, retry invalid JSON twice and, if enabled, require a "
  "simulation before committing (test-before-act).")
code('''{"thought": "Melons crash if I plant too many; test two mixes.",
 "action": "simulate_action",
 "args": {"plan": {"plant": {"MELON": 12, "STRAWBERRY": 8}, "hands": 4}, "days": 8}}''')
p("The eight tools are: get_farm_state, get_weather_forecast, get_market_prices, estimate_crop_profit, "
  "estimate_animal_profit, estimate_sale, plan_crop_mix and simulate_action. Profit estimates walk the official price "
  "curve unit by unit, so the agent sees the price drop its own harvest will cause.")
sub("Memory and Reflection Module")
p("Short-term memory renders the last five days (plan, cash change, weather, rejections) into each prompt. Long-term "
  "memory stores lessons after every season. In <b>verified reflection</b> (kagri/reflection.py) evidence-driven lesson "
  "templates propose concrete strategy changes; each is played on four validation seasons and adopted only if it "
  "raises profit by at least 1%, with progress measured on four held-out seasons.")
sub("Multi-Agent Coordination Module")
p("In team mode the Planner decides land use (plant, land, animals) with look-ahead, the Market Analyst decides sales "
  "with price-impact estimates, and the Agronomist decides fertiliser and labour from the forecast. The Manager merges "
  "their proposals, fixes conflicts such as too few hands for newly planted land, checks the merged plan with "
  "simulate_action and commits.")
sub("LLM Provider Module")
p("All providers implement one interface, respond(system, messages), over plain HTTPS: Gemini, OpenAI-compatible "
  "(OpenAI and Groq) and Claude. The base class adds rate limiting, retries with capped back-off, and token and cost "
  "accounting. The Gemini provider accepts a list of models and skips a model that is busy (503), rate-limited (429) "
  "or retired (404). The offline reasoner implements the same interface with rules, so the whole pipeline runs "
  "without a key.")
sub("Evaluation and Research Module")
p("kagri/evaluate.py runs all agents over N seeds in parallel and writes tables and charts. kagri/ablation.py switches "
  "off one component at a time. kagri/arena.py runs a round-robin two-player tournament on one market and fits "
  "Bradley-Terry ratings. kagri/scenarios.py runs scripted crises against a calm control. kagri/record.py records a "
  "real-LLM season for replay.")
sub("Dashboard and API Module")
p("kagri/server.py exposes recorded runs, results, research data, memory and live seasons; kagri/play.py lets a human "
  "take one seat of the shared market; kagri/scenarios.py and kagri/shop/agent.py serve the Scenario Lab and the shop "
  "world. The React app (web/) offers eight views: Live farm, Agent's mind, Play vs AI, Scenario Lab, New world: Shop, "
  "Arena, Research, Results and How it works. The built app is served by FastAPI, so the demonstration needs only "
  "python -m kagri.serve.")
sub("Shop World Module")
p("To show generality, kagri/shop implements a 30-day kirana store with five products (milk, bread, rice, ice cream, "
  "sweets), spoilage, price-sensitive demand, heatwaves, festivals, rival promotions and supplier delays. A ShopAgent "
  "calls the <b>same react_loop</b> with shop tools (store state, demand forecast, demand at a price, suggested plan, "
  "simulate_plan). Only the tools, prompt and simulator are new.")

# =============================================================== CHAPTER 6
chapter("System Testing")
sec("Testing Strategy")
p("Testing combined automated unit and integration tests, end-to-end checks of the user interface and API, and "
  "real-LLM case studies:")
ul(["<b>Unit testing:</b> environment rules, plan validation, JSON parsing, tool calls, reflection hypotheses and the shop simulator.",
    "<b>Integration testing:</b> full seasons for every agent, two-agent matches on a shared market, and a scripted fake LLM that exercises the ReAct loop, retries and fallback.",
    "<b>System testing:</b> a fresh clone, install, evaluation and server start; every API endpoint checked; the dashboard driven with Playwright (no browser errors).",
    "<b>Real-LLM testing:</b> three full seasons with Google Gemini, which exposed rate limits and LLM-specific failure modes fixed by new guardrails.",
    "<b>Regression testing:</b> after each change the main evaluation was re-run to confirm unchanged results (for example, after refactoring the ReAct loop into a shared core)."])
sec("Unit and Integration Tests")
p("The suite contains 24 automated tests, all passing (python -m pytest).")
table("Automated Tests", ["Test file", "Tests", "What is verified"], [
    ["test_env.py", "8", "Initial state, 30-day season, determinism, profitable plan, invalid actions rejected, budget trim, late planting rejected, simulate does not change the real environment"],
    ["test_agents.py", "2", "Baselines play full seasons and logs round-trip; Greedy beats Random"],
    ["test_llm_agent.py", "5", "JSON extraction, ReAct loop with tools and a bad-JSON retry, safe fallback, multi-agent + reflection, test-before-act policy"],
    ["test_arena.py", "3", "Two agents share one market, seat views, Bradley-Terry ordering"],
    ["test_reflection.py", "1", "Evidence-based lesson hypotheses"],
    ["test_realweather.py", "2", "Weather mapping thresholds, environment follows a weather file"],
    ["test_shop.py", "3", "Shop determinism and validation, same ReAct core, agent beats fixed rule"],
], ["22%", "9%", "69%"])
sec("Test Cases and Results")
table("Test Cases and Results", ["ID", "Test case", "Expected result", "Status"], [
    ["TC1", "Reset season with seed 0", "Day 0, $3,000, 25 free plots", "Pass"],
    ["TC2", "Same seed and plans twice", "Identical final cash", "Pass"],
    ["TC3", "Plan with unknown crop and negative hands", "Parts rejected with reasons, no crash", "Pass"],
    ["TC4", "Plan spending more than cash", "Plan trimmed to budget", "Pass"],
    ["TC5", "Melon planted on day 26", "Rejected: cannot ripen", "Pass"],
    ["TC6", "LLM returns invalid JSON", "Retried, then safe fallback plan", "Pass"],
    ["TC7", "Missing API key in live mode", "Notice shown, offline reasoner used", "Pass"],
    ["TC8", "Gemini model busy (503) or retired (404)", "Next model in the list used", "Pass"],
    ["TC9", "Plan with 25 plots and 0 hands", "Labour guardrail raises hands", "Pass"],
    ["TC10", "Plan leaving $68 after day 0", "Budget guardrail cancels land purchase", "Pass"],
    ["TC11", "Human plays a day in Play vs AI", "Both farms update, AI reasoning shown", "Pass"],
    ["TC12", "Dashboard without internet", "Replay, Play vs AI, Scenario Lab, Shop work", "Pass"],
], ["8%", "34%", "45%", "13%"], small=True)
sec("Bug Report and Fix Summary")
table("Bug Report and Fix Summary", ["ID", "Module", "Description", "Severity", "Fix summary"], [
    ["B1", "Foreman", "Animals stayed in the shed; farmer always chose watering", "High", "Farmer-only item tasks get top priority; act on current tile first"],
    ["B2", "Plan validation", "Plans spent all cash, animals starved", "High", "Three-day feed reserve per animal"],
    ["B3", "Strategy", "Weeds piled up; labour was the hidden bottleneck", "Medium", "Hand cap raised from 6 to 10 (profit $71k to $79k)"],
    ["B4", "Team mode", "Agronomist hired too few hands for new land", "Medium", "Manager checks labour against the merged plan"],
    ["B5", "Gemini provider", "gemini-2.5-flash retired for new keys (404)", "High", "Model fallback list"],
    ["B6", "Gemini provider", "Free tier 5 requests/min/model (429)", "High", "Rotate models on 429; capped retries"],
    ["B7", "LLM agent", "Gemini planned 25 plots with 0 hands", "High", "Labour guardrail"],
    ["B8", "LLM agent", "Gemini left $68 after day 0", "High", "Working-capital guardrail"],
    ["B9", "Shop agent", "Prompt braces broke string formatting", "Low", "Escaped braces in the template"],
    ["B10", "Strategy", "Full shed sells everything even at $1 (melon crash)", "Medium", "Documented; fix planned (free only needed space)"],
], ["6%", "15%", "36%", "11%", "32%"], small=True)

# =============================================================== CHAPTER 7
chapter("Results and Discussion")
sec("System Output Screenshots")
fig("ui_farm.png", "Live Farm View (replay of the multi-agent season)", "100%")
fig("ui_mind.png", "Agent's Mind - Reasoning Trace of One Day", "100%")
fig("ui_play.png", "Play vs AI - Human and Agent on One Shared Market", "100%")
fig("ui_scenarios.png", "Scenario Lab - Melon Market Crash", "100%")
fig("ui_shop.png", "Same Brain, New World - the Kirana Store", "100%")
fig("ui_arena.png", "Arena - Two Agents Racing on One Market", "92%")
sec("Agent Comparison")
p("All agents played the same five seeds with weather and events on, against Kaggle's starter bot on the shared "
  "market (Table 7.1, Figure 7.7). The LLM-agent rows use the offline reasoner, which drives the same ReAct loop, "
  "tools and guardrails as a real LLM.")
table("Mean Profit per Agent (5 seeds)", ["Agent", "Mean profit", "Std. dev.", "Min", "Max"], [
    ["Random", "$11,060", "$4,061", "$6,667", "$15,866"],
    ["Greedy heuristic", "$30,021", "$980", "$28,484", "$30,866"],
    ["LLM single-agent (offline reasoner)", "$79,344", "$16,126", "$61,166", "$104,187"],
    ["<b>LLM multi-agent (offline reasoner)</b>", "<b>$88,794</b>", "$11,840", "$78,757", "$104,737"],
], ["40%", "16%", "14%", "15%", "15%"])
fig("profit_by_agent.png", "Mean Profit per Agent", "78%")
fig("profit_over_time.png", "Profit over the Season", "78%")
p("The multi-agent system earns about <b>three times</b> the Greedy heuristic. Greedy plants melons on every plot, "
  "floods the market and watches the price collapse; the agents spread their crops by marginal profit, buy animals "
  "whose daily fertiliser sells for about $100, and expand land when simulation shows it pays back.")
sec("Ablation Study (RQ1)")
table("Ablation: Profit Lost when a Component is Removed", ["Variant", "Mean profit", "Change", "Seeds worse"], [
    ["Full system", "$88,794", "-", "-"],
    ["No look-ahead (plans never simulated)", "$63,281", "-28.7%", "5 / 5"],
    ["No land expansion", "$66,044", "-25.6%", "5 / 5"],
    ["No animals", "$71,805", "-19.1%", "5 / 5"],
    ["No team (single agent)", "$79,344", "-10.6%", "5 / 5"],
    ["No glut-awareness", "$79,436", "-10.5%", "5 / 5"],
    ["Small workforce (max 4 hands)", "$84,549", "-4.8%", "4 / 5"],
], ["46%", "18%", "16%", "20%"])
fig("ablation.png", "Ablation Study", "74%")
p("Every component pays its way. Testing a plan in simulation before acting is the most valuable skill: without it "
  "the agent cannot weigh an investment today against its payoff eight to ten days later.")
sec("Verified Reflection (RQ2)")
p("Plain reflection (lessons written into the next prompt) produced no measurable gain with the offline reasoner. "
  "Verified reflection starts the agent as a novice (crops only) and adopts a lesson only if it wins on four "
  "validation seasons. In the first season it learned to buy land, lifting profit on four held-out seasons from "
  "<b>$53,273 to $67,626 (+27%)</b>, and it then rejected lessons that did not transfer (animals +0.4%, labour +0.9%, "
  "look-ahead -0.8%, fewer melons -1.9%).")
fig("reflection_verified.png", "Verified Reflection - Profit on Held-Out Seasons", "74%")
sec("Competition on a Shared Market (RQ3, RQ4)")
table("Arena Results (3 seeds, both seat orders)", ["Agent", "BT rating", "Win rate", "vs starter bot", "vs itself", "Cost"], [
    ["LLM single-agent", "2434", "96%", "$72,474", "$39,881", "-45%"],
    ["LLM multi-agent", "2124", "75%", "$84,355", "$47,404", "-44%"],
    ["Greedy heuristic", "1815", "54%", "$30,498", "$23,416", "-23%"],
    ["Random", "979", "25%", "$12,906", "$10,683", "-17%"],
    ["Kaggle starter bot", "147", "0%", "-", "-", "-"],
], ["30%", "13%", "13%", "16%", "15%", "13%"])
fig("arena.png", "Arena Ratings and the Price of Competition", "100%")
p("A smart agent facing a copy of itself loses about 45% of its profit, because both chase the same premium crops and "
  "crash the same prices. Surprisingly, the single agent beats the higher-earning team in all six direct games: the "
  "look-ahead tool models the rival as the weak starter bot, so the team over-invests against a smart rival. Planning "
  "with the wrong opponent model is worse than planning less.")
sec("Real LLM Case Study (RQ5)")
table("Real Gemini Seasons on Seed 0", ["Agent", "Profit", "LLM calls", "Days using tools", "Simulations", "Guardrail fixes", "Cost"], [
    ["Offline multi-agent", "$98,156", "-", "30 / 30", "76", "0", "$0"],
    ["Offline single-agent", "$81,188", "-", "30 / 30", "48", "0", "$0"],
    ["Gemini + test-before-act", "$48,617", "90", "29 / 30", "30", "40", "$0.067"],
    ["Gemini single-agent", "$41,018", "34", "2 / 30", "0", "0", "$0.027"],
    ["Gemini multi-agent", "$31,197", "123", "3 / 30", "1", "16", "$0.079"],
    ["Greedy heuristic", "$29,709", "-", "-", "-", "-", "$0"],
], ["28%", "12%", "11%", "14%", "12%", "12%", "11%"], small=True)
p("Left alone, Gemini used a tool on only 2 of 30 days and never simulated a plan, behaving like the no-look-ahead "
  "ablation. The <b>test-before-act</b> policy made it simulate on 29 days and raised profit by <b>18.5%</b>. The real "
  "multi-agent team made 3.6 times more calls but simulated once and earned the least: agents that skip their tools "
  "add cost, not thinking. No season needed a fallback plan, because the guardrails repaired 16 to 40 risky plans per "
  "season. A season costs 3 to 8 US cents at list price.")
sec("Robustness and Generalisation")
table("Scenario Lab - Scripted Crises (seed 0)", ["Scenario", "AI team", "% of calm", "Greedy"], [
    ["Calm season (control)", "$85,525", "100%", "$34,439"],
    ["Melon market crash", "$34,930", "41%", "-$755"],
    ["Drought week", "$77,855", "91%", "$34,439"],
    ["Pest wave", "$64,485", "75%", "$31,131"],
    ["Monsoon with fungus", "$77,732", "91%", "$34,813"],
    ["Festival demand boom", "$78,245", "92%", "$34,439"],
], ["40%", "20%", "18%", "22%"])
table("Shop World - Same Agent Core (5 seeds)", ["Agent", "Mean profit", "Customers turned away", "Units wasted"], [
    ["AI shopkeeper (same ReAct core)", "Rs 61,815", "237", "5"],
    ["Fixed restock rule", "Rs 35,653", "1,671", "3"],
], ["40%", "20%", "24%", "16%"])
p("The AI stays far ahead in every crisis; in the melon crash Greedy ends the season with a loss while the agent's "
  "diversified farm still earns $34,930. In the kirana store the same agent core earns 73% more than a fixed restock "
  "rule by stocking up before heatwaves and festivals it sees in the forecast.")
sec("Limitations")
ul(["LLM-agent comparisons over five seeds use the offline reasoner; real-LLM results are single-season case studies.",
    "Few seeds per configuration; effects smaller than about 2% are within noise.",
    "The look-ahead assumes a weak opponent, which hurts against a smart rival.",
    "When the shed is nearly full, a sell-everything rule can sell at very low prices (seen in the melon crash).",
    "The weather and events layer is our extension and not part of the official competition."])
sec("Summary")
p("The agentic system meets its objectives: it is about three times more profitable than a classic heuristic, every "
  "decision is explained, guardrails prevent unsafe actions, and five research questions are answered with "
  "reproducible experiments. The results consistently point to one lesson: the value of an agent comes from testing "
  "its plans before acting, and from using its tools rather than only reasoning in words.")

# =============================================================== CHAPTER 8
chapter("Conclusion and Future Scope")
sec("Conclusion")
p("This project built a complete agentic decision-making system on the official rules of the Kaggle Kaggriculture "
  "competition: a deterministic environment, a Foreman executor, guardrails, a ReAct core with eight tools, memory, "
  "verified reflection, a multi-agent team, support for several LLM providers and an offline reasoner, an evaluation "
  "and research suite, and an interactive dashboard.",
  "The multi-agent system earned a mean profit of $88,794 against $30,021 for a greedy heuristic. The ablation study "
  "showed that look-ahead simulation alone is worth 29% of profit; verified reflection lifted a novice agent by 27% on "
  "unseen seasons; the Arena revealed that competition on a shared market costs a smart agent about 45% of its profit; "
  "and real Gemini runs showed that LLMs under-use their tools, a gap that a simple test-before-act policy partly "
  "closes. Finally, the same agent core ran a kirana store and earned 73% more than a fixed rule, demonstrating that "
  "the approach transfers to other decision problems.")
sec("Future Scope")
ul(["<b>Opponent-aware look-ahead:</b> simulate the rival as a copy of the agent, or infer its strategy from its visible farm.",
    "<b>Larger real-LLM study:</b> many seeds across Gemini, Groq, Claude and OpenAI, comparing profit, cost and latency.",
    "<b>Verified reflection for LLMs:</b> let the model propose free-form lessons and verify them with the same simulation gate.",
    "<b>Real market data:</b> drive prices with mandi price series (Agmarknet) alongside the real-weather mode.",
    "<b>Reinforcement-learning comparison:</b> train a PPO policy on FarmEnv and compare sample efficiency and explainability.",
    "<b>Better shed management:</b> free only the space needed, cheapest items first, instead of selling everything.",
    "<b>Deployment:</b> host the dashboard as a farm advisory service with real weather and price feeds."])

# =============================================================== CHAPTER 9
chapter("References")
refs = [
    "B. Doerschuk-Tiberi, D. Weir and M. Cruz, \"Kaggriculture,\" Kaggle Simulation Competition, 2026. https://www.kaggle.com/competitions/kaggriculture",
    "Kaggle, \"kaggle-environments,\" version 1.33.3, Apache License 2.0. https://github.com/Kaggle/kaggle-environments",
    "S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran, K. Narasimhan and Y. Cao, \"ReAct: Synergizing Reasoning and Acting in Language Models,\" ICLR, 2023.",
    "N. Shinn, F. Cassano, A. Gopinath, K. Narasimhan and S. Yao, \"Reflexion: Language Agents with Verbal Reinforcement Learning,\" NeurIPS, 2023.",
    "T. Schick et al., \"Toolformer: Language Models Can Teach Themselves to Use Tools,\" NeurIPS, 2023.",
    "J. S. Park et al., \"Generative Agents: Interactive Simulacra of Human Behavior,\" UIST, 2023.",
    "Q. Wu et al., \"AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation,\" arXiv:2308.08155, 2023.",
    "G. Li et al., \"CAMEL: Communicative Agents for Mind Exploration of Large Language Model Society,\" NeurIPS, 2023.",
    "H. Overweg, H. N. C. Berghuijs and I. N. Athanasiadis, \"CropGym: a Reinforcement Learning Environment for Crop Management,\" arXiv:2104.04326, 2021.",
    "G. Brockman et al., \"OpenAI Gym,\" arXiv:1606.01540, 2016.",
    "R. A. Bradley and M. E. Terry, \"Rank Analysis of Incomplete Block Designs: I. The Method of Paired Comparisons,\" Biometrika, 39(3/4), 1952.",
    "Google, \"Gemini API Documentation.\" https://ai.google.dev",
    "Open-Meteo, \"Historical Weather API.\" https://open-meteo.com",
    "FastAPI Documentation. https://fastapi.tiangolo.com",
    "React Documentation. https://react.dev",
]
body.append('<ol class="refs">' + "".join(f"<li>{html.escape(r)}</li>" for r in refs) + "</ol>")

# =============================================================== FRONT MATTER
LOGO = '<img class="logo" src="img/logo-000.png">'
names_lines = "".join(f"<div class='nm'>{n} - {i}</div>" for n, i in STUDENTS)
DEPT = ("<div class='dept'>DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING<br>RAJIV GANDHI UNIVERSITY OF KNOWLEDGE TECHNOLOGIES,"
        "<br>BASAR</div>")

cover = f"""<div class="cover">
<div class="t1">{TITLE}</div><div class="t2">A MAJOR PROJECT REPORT</div><div class="it">by</div>{names_lines}
<div class="b">Of</div><div class="bb">Bachelor of Technology</div><div class="it">Under the guidance of</div>
<div class="bb">{GUIDE}</div><div class="bb">{GUIDE_ROLE}</div><div class="logo-wrap">{LOGO}</div>
<div class="dept2">DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING<br>RAJIV GANDHI UNIVERSITY OF KNOWLEDGE TECHNOLOGIES<br>BASAR, NIRMAL (DIST.),<br>TELANGANA – 504107</div></div>"""

titlepage = f"""<div class="cover pb">
<div class="t1 caps">{SHORT}</div><div class="it">Project Report submitted to</div><div class="it">Rajiv Gandhi University of Knowledge Technologies, Basar</div>
<div class="it">for the partial fulfillment of the requirements</div><div class="it">for the award of the degree of</div>
<div class="bb">Bachelor of Technology</div><div class="bb">in</div><div class="bb">Computer Science &amp; Engineering</div><div class="it">by</div>{names_lines}
<div class="it">Under the Guidance of</div><div class="bb">{GUIDE}</div><div class="bb">{GUIDE_ROLE}</div><div class="logo-wrap small">{LOGO}</div>
<div class="dept2">DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING<br>RAJIV GANDHI UNIVERSITY OF KNOWLEDGE TECHNOLOGIES<br>BASAR, NIRMAL (DIST)<br>{MONTH}</div></div>"""

s1, s2, s3 = STUDENTS
certificate = f"""<div class="first formal nonum"><div class="logo-wrap">{LOGO}</div>{DEPT}<div class="ft">CERTIFICATE</div>
<p>This is to certify that the Project Report entitled <b>{SHORT}</b> submitted by <b>{s1[0]} ({s1[1]})</b>, <b>{s3[0]} ({s3[1]})</b> and
<b>{s2[0]} ({s2[1]})</b>, is a bonafide record of the work and investigations carried out by them under my supervision and guidance.
The report has been submitted in partial fulfillment of the requirements for the degree of <b>Bachelor of Technology</b> in
<b>Computer Science and Engineering</b> at <b>Rajiv Gandhi University of Knowledge Technologies, Basar</b>.</p>
<table class="sig"><tr><td><b>PROJECT SUPERVISOR</b><br><br>{GUIDE.upper().replace("MRS.", "Mrs.")}<br>{GUIDE_ROLE}</td>
<td><b>HEAD OF DEPARTMENT</b><br><br>{HOD.upper().replace("DR.", "Dr.")}<br>{HOD_ROLE}</td></tr></table>
<div class="ext"><b>EXTERNAL EXAMINER</b></div></div>"""

declaration = f"""<div class="formal pb nonum"><div class="logo-wrap">{LOGO}</div>{DEPT}<div class="ft">DECLARATION</div>
<p>We hereby declare that the work which is being presented in this project entitled, <b>{SHORT}</b> submitted to RAJIV GANDHI UNIVERSITY OF
KNOWLEDGE TECHNOLOGIES, BASAR in the partial fulfillment of the requirements for the award of the degree of <b>BACHELOR OF TECHNOLOGY</b>
in <b>COMPUTER SCIENCE AND ENGINEERING</b>, is an authentic record of our own work carried out under the supervision of {GUIDE}, {GUIDE_ROLE}
in Department of Computer Science and Engineering, RGUKT-Basar.</p>
<p>The matter embodied in this project report has not been submitted by us for the award of any other degree.</p>
<table class="sig decl"><tr><td><br><br>Place: <b>Basar</b><br>Date: <b>{DATE}</b></td><td><b>Name of the Students – ID No</b><br>
{"<br>".join(f"{n} - {i}" for n, i in STUDENTS)}</td></tr></table></div>"""

ack = f"""<div class="pb plainfront"><div class="fh">ACKNOWLEDGEMENT</div>
<p>We express our sincere gratitude to Rajiv Gandhi University of Knowledge Technologies, Basar for providing the opportunity and resources to
carry out this project. We are deeply thankful to our project supervisor, <b>{GUIDE.upper().replace("MRS.", "Mrs.")}</b>, for her valuable guidance,
constructive feedback and continuous support throughout this project, and to our Head of the Department, <b>{HOD.upper().replace("DR.", "Dr.")}</b>,
for his encouragement and support.</p>
<p>Finally, we would like to thank our family and friends for their unwavering support and motivation during this endeavor.</p>
<div class="acknames">{"<br>".join(f"{n} - {i}" for n, i in STUDENTS)}</div></div>"""

abstract = """<div class="pb plainfront"><div class="fh">ABSTRACT</div>
<p>Farm management is a sequence of economic decisions under uncertainty: what to plant, how much labour to hire, when to invest and when to sell,
while prices react to supply and weather adds risk. This project, <b>Intelligent Decision-Making Agent for Dynamic Resource Management in
Kaggriculture</b>, studies the problem on the official rules of Kaggriculture, a Kaggle simulation competition in which an agent runs a farm for a
30-day, 720-turn season and is scored on its final cash.</p>
<p>We wrap the official engine as a deterministic gym-style environment in which one step is one day, and a Foreman executor turns each daily plan
into per-turn commands. On top we build an agentic AI manager: a ReAct agent that reasons, calls eight tools including a look-ahead simulator,
keeps short-term memory and verified long-term lessons, and can work as a team of Planner, Market Analyst and Agronomist coordinated by a Manager.
Guardrails validate every plan. The agent supports Google Gemini, Groq, OpenAI and Claude, and an offline reasoner keeps it usable without internet.</p>
<p>Over five seeds the multi-agent system earned a mean profit of $88,794 against $30,021 for a greedy heuristic, about three times more. An
ablation study shows that look-ahead simulation alone is worth 29% of profit; verified reflection improves a novice agent by 27% on unseen seasons;
a two-player tournament shows that competition on a shared market costs a smart agent about 45% of its profit; and real Gemini seasons show that an
LLM under-uses its tools, a gap that a test-before-act policy reduces by 18.5%. The same agent core also runs a kirana store, earning 73% more than a
fixed restock rule. An interactive dashboard lets users watch the agent think, play against it and stress-test it with crises.</p>
<p><b>Keywords:</b> Agentic AI, Large Language Models, ReAct, Tool Use, Multi-Agent Systems, Reflection, Simulation, Farm Management.</p></div>"""


def toc_html() -> str:
    rows = ['<div class="tocl lv0f"><a class="r" href="#cert">Certificate</a></div>',
            '<div class="tocl lv0f"><a class="r" href="#decl">Declaration</a></div>',
            '<div class="tocl lv0f"><a class="r" href="#ack">Acknowledgement</a></div>',
            '<div class="tocl lv0f"><a class="r" href="#abs">Abstract</a></div>',
            '<div class="tocl lv0f"><a class="r" href="#lof">List of Figures</a></div>',
            '<div class="tocl lv0f"><a class="r" href="#lot">List of Tables</a></div>',
            '<div class="tocl lv0f"><a class="r" href="#abbr">List of Abbreviations</a></div>']
    for lv, num, t, a in toc:
        rows.append(f'<div class="tocl lv{lv}"><a href="#{a}"><span class="tn">{num}</span>{t}</a></div>')
    return '<div class="pb plainfront toc"><div class="ch">Contents</div>' + "".join(rows) + "</div>"


def lof_html() -> str:
    rows = "".join(f'<div class="tocl lv1"><a href="#{a}"><span class="tn">{n}</span>{c}</a></div>' for n, c, a in figs)
    return f'<div class="pb plainfront toc" id="lof"><div class="ch">List of Figures</div>{rows}</div>'


def lot_html() -> str:
    rows = "".join(f'<div class="tocl lv1"><a href="#{a}"><span class="tn">{n}</span>{c}</a></div>' for n, c, a in tabs)
    return f'<div class="pb plainfront toc" id="lot"><div class="ch">List of Tables</div>{rows}</div>'


ABBR = [("AI", "Artificial Intelligence"), ("LLM", "Large Language Model"), ("ReAct", "Reasoning and Acting"),
        ("API", "Application Programming Interface"), ("REST", "Representational State Transfer"), ("JSON", "JavaScript Object Notation"),
        ("JSONL", "JSON Lines"), ("CSV", "Comma-Separated Values"), ("UI", "User Interface"), ("HTTP", "Hypertext Transfer Protocol"),
        ("RL", "Reinforcement Learning"), ("PPO", "Proximal Policy Optimization"), ("BT", "Bradley-Terry (rating model)"),
        ("RQ", "Research Question"), ("TBA", "Test-Before-Act (policy)"), ("DFD", "Data Flow Diagram"), ("UML", "Unified Modeling Language"),
        ("ER", "Entity Relationship"), ("CPU", "Central Processing Unit"), ("RAM", "Random Access Memory"), ("RPM", "Requests Per Minute"),
        ("Rs", "Indian Rupees")]
abbr = ('<div class="pb plainfront" id="abbr"><div class="fh">LIST OF ABBREVIATIONS</div><table class="abbr"><tr><th>Abbreviation</th><th>Full Form</th></tr>'
        + "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in ABBR) + "</table></div>")

CSS = """
@page { size: A4; margin: 2.3cm 2.25cm 2.7cm 2.25cm; @bottom-center { content: none; } }
@page front { @bottom-center { content: counter(page, lower-roman); font: 11pt 'Liberation Serif'; vertical-align: top; padding-top: 0.35cm; } }
@page frontstart { counter-reset: page 1; }
@page frontnonum { @bottom-center { content: none; } }
#decl { page: frontnonum; }
@page main { @bottom-center { content: counter(page); font: 11pt 'Liberation Serif'; vertical-align: top; padding-top: 0.35cm; } }
@page mainstart { counter-reset: page 1; @bottom-center { content: counter(page); font: 11pt 'Liberation Serif'; vertical-align: top; padding-top: 0.35cm; } }
html { font-family: 'Liberation Serif', 'Times New Roman', serif; font-size: 12pt; line-height: 1.75; color: #000; }
.border { position: fixed; top: -1.55cm; left: -1.35cm; right: -1.35cm; bottom: -1.95cm; border: 1.1pt solid #000; }
.pb { break-before: page; }
.frontwrap { page: front; } .frontwrap > .first { page: frontstart; }
.mainwrap { page: main; } .mainwrap > .chapter.first { page: mainstart; }
p { text-align: justify; margin: 0 0 0.55em; hyphens: auto; }
ul, ol { margin: 0.2em 0 0.7em 1.4em; padding-left: 0.6em; } li { text-align: justify; margin-bottom: 0.15em; }
.cover { text-align: center; line-height: 1.5; }
.cover .t1 { font-size: 19pt; font-weight: bold; margin: 0.6cm 0 0.25cm; line-height: 1.3; }
.cover .t1.caps { font-size: 17pt; }
.cover .t2 { font-size: 12.5pt; margin-bottom: 0.55cm; }
.cover .it { font-style: italic; font-size: 11.5pt; margin: 0.18cm 0; }
.cover .nm, .cover .bb { font-weight: bold; font-size: 13pt; margin: 0.1cm 0; }
.cover .b { font-weight: bold; font-size: 11pt; margin: 0.35cm 0; }
.logo-wrap { text-align: center; margin: 0.8cm 0 0.7cm; } .logo { width: 6.2cm; } .logo-wrap.small .logo { width: 5cm; }
.dept2 { font-weight: bold; font-size: 13pt; line-height: 1.75; margin-top: 0.4cm; }
.formal { text-align: center; } .formal .logo-wrap { margin-top: 0.6cm; } .formal p { text-align: justify; line-height: 1.85; }
.dept { font-weight: bold; font-size: 13pt; line-height: 1.8; margin-bottom: 0.4cm; }
.ft { font-size: 19pt; font-weight: bold; margin: 0.3cm 0 0.6cm; }
table.sig { width: 100%; margin-top: 1.6cm; border: none; } table.sig td { border: none; vertical-align: top; text-align: left; width: 50%; line-height: 1.9; padding-left: 0.2cm; }
table.sig.decl { margin-top: 1.3cm; }
.ext { margin-top: 2.6cm; text-align: center; }
.fh { text-align: center; font-weight: bold; font-size: 16pt; margin: 1.5cm 0 0.9cm; }
.acknames { margin-top: 1.2cm; line-height: 1.8; }
.toc .ch { font-size: 22pt; font-weight: bold; margin: 0.6cm 0 0.7cm; }
.tocl { line-height: 1.65; } .tocl a { color: #000; text-decoration: none; }
.tocl a::after { content: leader('. ') target-counter(attr(href), page); }
.tocl a.r::after { content: leader('. ') target-counter(attr(href), page, lower-roman); }
.tocl.lv0 { font-weight: bold; margin-top: 0.35em; } .tocl.lv1 { padding-left: 1.2em; } .tocl.lv2 { padding-left: 3.1em; }
.tn { display: inline-block; min-width: 1.6em; padding-right: 0.5em; } .lv1 .tn { min-width: 2.2em; } .lv2 .tn { min-width: 3.2em; }
table.abbr { width: 85%; margin: 0 auto; border-collapse: collapse; } table.abbr th, table.abbr td { text-align: left; padding: 0.12cm 0.3cm; border: none; }
table.abbr th { border-bottom: 1pt solid #000; }
.chapter { break-before: page; text-align: center; padding-top: 1.4cm; margin-bottom: 0.8cm; }
.chapnum { font-size: 18pt; font-weight: bold; margin-bottom: 0.6cm; }
h1 { font-size: 18pt; font-weight: bold; margin: 0 0 0.2cm; }
h2 { font-size: 14pt; font-weight: bold; margin: 0.75cm 0 0.3cm; break-after: avoid; }
h3 { font-size: 12pt; font-weight: bold; margin: 0.5cm 0 0.2cm; break-after: avoid; }
.n { display: inline-block; min-width: 1.4cm; }
h3 .n { min-width: 1.6cm; }
.tbl { margin: 0.4cm 0 0.6cm; break-inside: avoid; }
.cap { text-align: center; font-size: 11.5pt; margin: 0.2cm 0 0.25cm; }
table { width: 100%; border-collapse: collapse; font-size: 10.5pt; line-height: 1.35; }
th, td { border: 0.8pt solid #000; padding: 0.11cm 0.16cm; text-align: left; vertical-align: top; } th { font-weight: bold; }
.tbl.small table { font-size: 9.5pt; }
.fig { text-align: center; margin: 0.45cm 0 0.55cm; break-inside: avoid; } .fig img { max-height: 19cm; }
pre { font-family: 'Liberation Mono', monospace; font-size: 9pt; line-height: 1.35; background: #f4f4f4; border: 0.6pt solid #bbb; padding: 0.25cm; white-space: pre-wrap; }
ol.refs { line-height: 1.5; } ol.refs li { margin-bottom: 0.25em; text-align: left; }
"""

front = (f'<div class="frontwrap pb"><div id="cert" class="first">{certificate}</div><div id="decl">{declaration}</div>'
         f'<div id="ack">{ack}</div><div id="abs">{abstract}</div>{toc_html()}{lof_html()}{lot_html()}{abbr}</div>')
doc = (f'<html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="border"></div>{cover}{titlepage}{front}'
       f'<div class="mainwrap pb">{"".join(body)}</div></body></html>')
(HERE / "report.html").write_text(doc, encoding="utf-8")
weasyprint.HTML(string=doc, base_url=str(HERE)).write_pdf(HERE / "Kaggriculture_Major_Project_Report.pdf")
print("pdf written")
