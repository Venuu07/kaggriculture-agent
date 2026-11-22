import { useMemo } from "react";
import { CODE_TO_NAME, CROP_EMOJI, HARVEST_AGE, titleCase } from "../constants";
import type { FarmState, Plot } from "../types";

interface Props { state: FarmState; opponentLabel?: string }

/** The 10x10 farm. Plants grow from a sprout to full size, ripe tiles glow, the weather plays over the field. */
export function FarmGrid({ state }: Props) {
  const plots = useMemo(() => {
    const m = new Map<string, Plot>();
    (state.plots || []).forEach((p) => m.set(`${p.x},${p.y}`, p));
    return m;
  }, [state.plots]);
  const weather = state.weather?.weather ?? "";
  const events = state.weather?.events ?? [];
  const pests = events.some((e) => e.toLowerCase().includes("pest"));

  return (
    <div className={`farm-wrap weather-${weather}`}>
      <div className="farm">
        {state.grid.map((row, y) =>
          row.map((code, x) => <Tile key={`${x},${y}`} code={code} plot={plots.get(`${x},${y}`)} />),
        )}
        <div className="shed" title="Shed: harvests are stored here and sold to the market">⌂</div>
      </div>
      {weather === "heavy_rain" && <div className="rain" aria-hidden>{Array.from({ length: 40 }, (_, i) => <i key={i} style={{ left: `${(i * 2.5) % 100}%`, animationDelay: `${(i % 10) * 0.09}s` }} />)}</div>}
      {weather === "drought" && <div className="heat" aria-hidden />}
      {pests && <div className="pests" aria-hidden>{["🐛", "🦗", "🐛", "🐜", "🦗"].map((b, i) => <span key={i} style={{ left: `${15 + i * 17}%`, animationDelay: `${i * 0.4}s` }}>{b}</span>)}</div>}
      <div className="farm-legend">
        <span><i className="sw sw-land" />Free plot</span>
        <span><i className="sw sw-locked" />Unbought land</span>
        <span><i className="sw sw-ready" />Ready to harvest</span>
        <span>Bar = growth</span>
      </div>
    </div>
  );
}

function Tile({ code, plot }: { code: string; plot?: Plot }) {
  if (code === "#") return <div className="tile locked" />;
  if (code === ".") return <div className="tile land" />;
  if (code === "x") return <div className="tile land weed"><span className="em pop">🌿</span></div>;
  if (code === "C" || code === "P") {
    return <div className="tile struct" title={code === "C" ? "Empty coop" : "Empty pasture"}><span className="struct-l">{code === "C" ? "coop" : "pasture"}</span></div>;
  }
  const name = CODE_TO_NAME[code];
  if (!name) return <div className="tile land" />;
  if (["GOOSE", "COW", "SHEEP"].includes(name)) {
    return (
      <div className={`tile animal a-${name.toLowerCase()}`} title={titleCase(name)}>
        <span className="em bob">{CROP_EMOJI[name]}</span>
      </div>
    );
  }
  const target = HARVEST_AGE[name] ?? 5;
  const age = plot?.age ?? 0;
  const progress = Math.max(0, Math.min(1, (age + 1) / (target + 1)));
  const ready = plot ? plot.ready_in === 0 && plot.yield > 0 : false;
  const sprout = progress < 0.34;
  const scale = 0.5 + 0.5 * progress;
  const tip = plot
    ? `${titleCase(name)} · age ${plot.age}d · ${ready ? "ready to harvest" : `ready in ${plot.ready_in}d`} · ${plot.yield} units${plot.fertilised ? " · fertilised" : ""}`
    : titleCase(name);
  return (
    <div className={`tile crop c-${name.toLowerCase()} ${ready ? "ready" : ""}`} title={tip}>
      <span className="em" style={{ transform: `scale(${sprout ? 0.8 : scale})` }}>{sprout ? "🌱" : CROP_EMOJI[name]}</span>
      <span className="grow" style={{ width: `${progress * 100}%` }} />
      {plot?.fertilised && <span className="fert" title="Fertilised">✦</span>}
    </div>
  );
}
