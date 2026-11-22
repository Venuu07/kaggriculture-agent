"""Report diagrams in the style of the original (rounded pastel boxes, Times-like font)."""
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).parent / "img"
OUT.mkdir(exist_ok=True)
FONT = "Liberation Serif"
G = f'graph [fontname="{FONT}", fontsize=11, bgcolor="white", pad=0.2, nodesep=0.45, ranksep=0.5];\n' \
    f'node [fontname="{FONT}", fontsize=11, shape=box, style="rounded,filled", color="#333333", penwidth=0.8];\n' \
    f'edge [fontname="{FONT}", fontsize=8, color="#222222", arrowsize=0.7, penwidth=0.8];\n'
GREEN, BLUE, YELLOW, PEACH, PINK, TEAL, LAV, GREY = "#d9f2d9", "#dcdcf7", "#fdf6c3", "#fde3cc", "#f8d7da", "#cfe8e8", "#e8e0f5", "#efefef"


def dot(name: str, body: str, rankdir: str = "TB") -> None:
    src = "digraph G {\n" + G + f"rankdir={rankdir};\n" + body + "\n}"
    subprocess.run(["dot", "-Tpng", "-Gdpi=220", "-o", str(OUT / f"{name}.png")], input=src.encode(), check=True)


dot("arch", f'''
ui [label="Web Dashboard\\n(React + TypeScript)", fillcolor="{LAV}"];
api [label="FastAPI Server\\n(REST API)", fillcolor="{GREEN}"];
logs [label="Run Logs and Results\\n(JSONL, CSV, charts)", fillcolor="{GREY}"];
llm [label="LLM Provider\\n(Gemini / Groq / Offline)", fillcolor="{PINK}"];
agent [label="Agentic AI Core\\n(ReAct loop, multi-agent team)", fillcolor="{PEACH}"];
mem [label="Memory\\n(season log, verified lessons)", fillcolor="{TEAL}"];
tools [label="Tool Box\\n(prices, weather, profit, simulate)", fillcolor="{YELLOW}"];
guard [label="Guardrails\\n(validation, budget, labour)", fillcolor="{PINK}"];
foreman [label="Foreman\\n(24 turns per day)", fillcolor="{YELLOW}"];
engine [label="Official Kaggriculture Engine\\n+ Weather and Events Layer", fillcolor="{BLUE}"];
ui -> api [label="HTTP / JSON", dir=both];
api -> logs [label="write"];
api -> agent [label="observation"];
{{rank=same; llm; agent; mem}}
llm -> agent [label="prompt / decision", dir=both];
agent -> mem [dir=both];
agent -> tools [label="tool call"];
agent -> guard [label="daily plan"];
{{rank=same; tools; guard}}
guard -> foreman [label="validated plan"];
tools -> engine [label="simulate on a copy", style=dashed];
foreman -> engine [label="per-turn commands"];
''')

dot("dfd0", f'''
node [shape=box, style="filled", fillcolor="white"];
user [label="User / Panel"];
sys [label="Kaggriculture\\nAgent System", shape=box, style="rounded,filled", fillcolor="{GREY}", width=1.8, height=0.8];
llm [label="LLM API", fillcolor="white"];
wx [label="Open-Meteo\\n(optional)"];
store [label="Run Logs / Results", fillcolor="{YELLOW}"];
user -> sys [label="agent choice, seed, plans"];
sys -> user [label="farm state, reasoning, results"];
sys -> llm [label="prompts"]; llm -> sys [label="decisions"];
wx -> sys [label="historical weather"];
sys -> store [label="store"]; store -> sys [label="replay"];
''', "LR")

dot("dfd1", f'''
node [shape=box, style="rounded,filled", fillcolor="{GREEN}"];
user [label="User", shape=box, style="filled", fillcolor="white"];
p1 [label="P1: Observe\\nfarm state"]; p2 [label="P2: Reason\\n(ReAct + tools)"]; p3 [label="P3: Validate\\n(guardrails)"];
p4 [label="P4: Execute\\n(Foreman)"]; p5 [label="P5: Log and\\nEvaluate"];
llm [label="LLM API", shape=box, style="filled", fillcolor="white"];
d1 [label="D1: Run logs", shape=box, style="filled", fillcolor="{YELLOW}"];
d2 [label="D2: Lessons memory", shape=box, style="filled", fillcolor="{YELLOW}"];
d3 [label="D3: Config", shape=box, style="filled", fillcolor="{YELLOW}"];
user -> p1 [label="start season"]; p1 -> p2 [label="observation"]; p2 -> llm [label="prompt"]; llm -> p2 [label="action"];
d2 -> p2 [label="lessons"]; d3 -> p1 [label="rules"]; p2 -> p3 [label="plan"]; p3 -> p4 [label="clean plan"];
p4 -> p1 [label="next day", style=dashed]; p4 -> p5 [label="rewards"]; p5 -> d1; p5 -> d2 [label="reflection"]; d1 -> user [label="replay, charts"];
''', "TB")

dot("usecase", f'''
node [shape=ellipse, style="filled", fillcolor="{BLUE}", fontsize=10];
u [label="User / Student", shape=plaintext, style="", fontsize=11];
r [label="Researcher", shape=plaintext, style="", fontsize=11];
subgraph cluster_s {{ label="Kaggriculture Agent System"; style="rounded"; color="#555555"; fontname="{FONT}";
  a1 [label="Replay recorded season"]; a2 [label="Run live season"]; a3 [label="Inspect agent reasoning"];
  a4 [label="Play vs the AI"]; a5 [label="Run crisis scenario"]; a6 [label="Run shop world"];
  a7 [label="Evaluate agents"]; a8 [label="Run research studies"]; a9 [label="Record real-LLM run"]; }}
u -> a1; u -> a2; u -> a3; u -> a4; u -> a5; u -> a6; r -> a7; r -> a8; r -> a9; r -> a3;
''', "LR")

dot("classes", f'''
node [shape=record, style="filled", fillcolor="{YELLOW}", fontsize=9];
edge [arrowhead=empty];
farm [label="{{FarmEnv|seed, me, events, scenario\\l|reset(seed)\\lstep(plan, rival)\\lsimulate(plan, days)\\lobserve()\\lview(player)\\l}}"];
fore [label="{{Foreman|plan, day\\l|act(obs)\\l_tasks(obs)\\l}}"];
agent [label="{{Agent|name, label\\l|begin_episode()\\ldecide(obs, env)\\lafter_step()\\lend_episode()\\l}}", fillcolor="{GREEN}"];
rnd [label="{{RandomAgent||decide()\\l}}", fillcolor="{GREEN}"]; gr [label="{{GreedyAgent||decide()\\l}}", fillcolor="{GREEN}"];
llm [label="{{LLMAgent|provider, multi, reflection\\l|decide()\\l_react()\\l_team()\\lend_episode()\\l}}", fillcolor="{GREEN}"];
prov [label="{{Provider|model, temperature\\l|respond(system, msgs)\\lcost(reply)\\l}}", fillcolor="{PINK}"];
gem [label="{{GeminiProvider}}", fillcolor="{PINK}"]; oai [label="{{OpenAICompat\\n(OpenAI, Groq)}}", fillcolor="{PINK}"]; off [label="{{OfflineReasoner}}", fillcolor="{PINK}"];
tb [label="{{ToolBox|env, obs\\l|call(name, args)\\ldescribe()\\l}}", fillcolor="{BLUE}"];
mem [label="{{LongTermMemory|entries\\l|lessons()\\ladd()\\l}}", fillcolor="{TEAL}"];
rnd -> agent; gr -> agent; llm -> agent; gem -> prov; oai -> prov; off -> prov;
edge [arrowhead=vee, style=dashed];
llm -> prov [label="uses"]; llm -> tb [label="uses"]; llm -> mem [label="uses"]; tb -> farm [label="simulates"]; farm -> fore [label="runs"];
''')

dot("activity", f'''
node [style="rounded,filled", fillcolor="{BLUE}", fontsize=10];
s [label="", shape=circle, width=0.22, fillcolor="black", style="filled"];
reset [label="Reset season (seed)"]; obs [label="Observe farm, market, weather"];
think [label="LLM thinks"]; tool [label="Call a tool"]; dec [label="Tool budget left\\nand not decided?", shape=diamond, fillcolor="{YELLOW}", style="filled"];
plan [label="take_action(plan)"]; val [label="Guardrails validate plan"]; ok [label="Usable?", shape=diamond, fillcolor="{YELLOW}", style="filled"];
fb [label="Safe fallback plan", fillcolor="{PINK}"]; run [label="Foreman runs 24 turns"]; more [label="Day < 30?", shape=diamond, fillcolor="{YELLOW}", style="filled"];
refl [label="Reflect and store lessons"]; e [label="", shape=doublecircle, width=0.18, fillcolor="black", style="filled"];
s -> reset -> obs -> think -> dec; dec -> tool [label="yes"]; tool -> think; dec -> plan [label="no"];
plan -> val -> ok; ok -> run [label="yes"]; ok -> fb [label="no"]; fb -> run; run -> more; more -> obs [label="yes"]; more -> refl [label="no"]; refl -> e;
''')

dot("components", f'''
compound=true;
node [style="rounded,filled", fontsize=10];
subgraph cluster_fe {{ label="Frontend (web/)"; style="rounded"; color="#777777"; fontname="{FONT}";
  f1 [label="Live Farm", fillcolor="{LAV}"]; f2 [label="Agent's Mind", fillcolor="{LAV}"]; f3 [label="Play vs AI", fillcolor="{LAV}"];
  f4 [label="Scenario Lab", fillcolor="{LAV}"]; f5 [label="Shop World", fillcolor="{LAV}"]; f6 [label="Arena / Research", fillcolor="{LAV}"]; }}
subgraph cluster_api {{ label="Backend API (kagri/)"; style="rounded"; color="#777777"; fontname="{FONT}";
  b1 [label="server.py", fillcolor="{GREEN}"]; b2 [label="play.py", fillcolor="{GREEN}"]; b3 [label="scenarios.py", fillcolor="{GREEN}"]; b4 [label="shop/agent.py", fillcolor="{GREEN}"]; }}
subgraph cluster_core {{ label="Agent Layer"; style="rounded"; color="#777777"; fontname="{FONT}";
  c1 [label="agents/core.py\\n(react_loop)", fillcolor="{PEACH}"]; c2 [label="llm_agent.py", fillcolor="{PEACH}"]; c3 [label="tools.py / memory.py", fillcolor="{PEACH}"]; c4 [label="llm/providers.py", fillcolor="{PINK}"]; }}
subgraph cluster_env {{ label="Simulation Layer"; style="rounded"; color="#777777"; fontname="{FONT}";
  e1 [label="env.py (FarmEnv)", fillcolor="{BLUE}"]; e2 [label="foreman.py / plan.py", fillcolor="{BLUE}"]; e3 [label="engine/kaggriculture.py", fillcolor="{BLUE}"]; e4 [label="shop/env.py", fillcolor="{BLUE}"]; }}
f3 -> b2 [lhead=cluster_api, ltail=cluster_fe, label="REST"]; b1 -> c2 [lhead=cluster_core, ltail=cluster_api];
c2 -> c1; c1 -> c4; c3 -> e1 [lhead=cluster_env, ltail=cluster_core]; e1 -> e2 -> e3; b4 -> e4;
''')

dot("deploy", f'''
node [style="filled", fontsize=10, shape=box3d, fillcolor="{GREY}"];
subgraph cluster_l {{ label="Laptop (Windows / Linux / macOS)"; style="rounded"; color="#555555"; fontname="{FONT}";
  br [label="Web Browser\\nlocalhost:8000", shape=box, style="rounded,filled", fillcolor="{LAV}"];
  py [label="Python 3.11 process\\nuvicorn + FastAPI + agents + simulator", shape=box, style="rounded,filled", fillcolor="{GREEN}"];
  fs [label="Local files\\nruns/, results/, memory/, .env", shape=folder, fillcolor="{YELLOW}"]; }}
gem [label="Google Gemini API"]; groq [label="Groq API"]; om [label="Open-Meteo Archive"];
br -> py [label="HTTP"]; py -> fs [dir=both]; py -> gem [label="HTTPS (optional)", style=dashed]; py -> groq [label="HTTPS (optional)", style=dashed]; py -> om [label="fetch once (optional)", style=dashed];
''', "LR")

dot("datamodel", f'''
node [shape=record, style="filled", fillcolor="{YELLOW}", fontsize=9];
edge [arrowhead=crow, arrowtail=tee, dir=both];
h [label="{{Run Header|agent, label, seed\\lprovider, events\\lweather_source\\l}}"];
d [label="{{Day Record|day, reward, cash\\lplan, rejected\\lsales, events\\ltokens, latency, fallback\\l}}"];
t [label="{{Trace Step|type (thought/tool/action)\\lagent role, text\\ltool name, args, result\\l}}", fillcolor="{GREEN}"];
o [label="{{Observation Snapshot|cash, profit, grid\\lprices, shed, weather\\lforecast, plots\\l}}", fillcolor="{BLUE}"];
s [label="{{Season Summary|profit, final cash\\lllm_calls, tokens, cost\\lfinal snapshot\\l}}", fillcolor="{PEACH}"];
l [label="{{Lesson Entry|episode, seed, profit\\llessons[], params\\l}}", fillcolor="{TEAL}"];
h -> d [label="1 : 30"]; d -> t [label="1 : N"]; d -> o [label="1 : 1", arrowhead=tee]; h -> s [label="1 : 1", arrowhead=tee]; s -> l [label="reflection", style=dashed, arrowhead=vee, dir=forward];
''', "TB")


def sequence() -> None:
    parts = ["Runner", "LLMAgent", "LLM", "ToolBox", "FarmEnv\n(copy)", "Guardrails", "Foreman"]
    msgs = [(0, 1, "decide(obs)"), (1, 2, "system + day prompt"), (2, 1, "thought + tool call"), (1, 3, "call(simulate_action)"),
            (3, 4, "play plan 8 days"), (4, 3, "net-worth change"), (3, 1, "result"), (1, 2, "tool result"),
            (2, 1, "take_action(plan)"), (1, 5, "labour / budget check"), (5, 1, "safe plan"), (1, 0, "Decision(plan, trace)"),
            (0, 6, "execute 24 turns"), (6, 0, "reward, next observation")]
    fig, ax = plt.subplots(figsize=(8.2, 5.4))
    xs = [i * 1.25 for i in range(len(parts))]
    top, bottom = 0.0, -(len(msgs) + 1) * 0.42
    for x, p in zip(xs, parts):
        ax.add_patch(plt.Rectangle((x - 0.5, top), 1.0, 0.45, facecolor="#dcdcf7", edgecolor="#333333", lw=0.8))
        ax.text(x, top + 0.22, p, ha="center", va="center", fontsize=8, family=FONT)
        ax.plot([x, x], [top, bottom], ls="--", color="#888888", lw=0.7)
    for i, (a, b, t) in enumerate(msgs):
        y = -(i + 1) * 0.42
        ax.annotate("", xy=(xs[b], y), xytext=(xs[a], y), arrowprops=dict(arrowstyle="->", lw=0.8, color="#222222",
                    ls="--" if b < a else "-"))
        ax.text((xs[a] + xs[b]) / 2, y + 0.06, f"{i + 1}. {t}", ha="center", va="bottom", fontsize=7, family=FONT)
    ax.set_xlim(-0.7, xs[-1] + 0.7)
    ax.set_ylim(bottom - 0.1, top + 0.6)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "sequence.png", dpi=220)
    plt.close(fig)


sequence()
print("diagrams done:", sorted(p.name for p in OUT.glob("*.png")))
