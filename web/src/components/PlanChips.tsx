import { titleCase } from "../constants";
import type { Plan } from "../types";

/** A daily plan as readable chips. */
export function PlanChips({ plan }: { plan?: Plan & { order?: Record<string, number>; price?: Record<string, number> } }) {
  if (!plan) return null;
  if (plan.order || plan.price) {
    const shop = [
      ...Object.entries(plan.order ?? {}).filter(([, n]) => n > 0).map(([p, n]) => ({ k: `o${p}`, verb: "Order", n, what: titleCase(p), tone: "green" })),
      ...Object.entries(plan.price ?? {}).map(([p, v]) => ({ k: `p${p}`, verb: `${titleCase(p)} at`, n: `₹${v}`, what: "", tone: "orange" })),
    ];
    return <div className="chips">{shop.map((c) => <span key={c.k} className={`chip ${c.tone}`}><span>{c.verb}</span><b>{c.n}</b>{c.what && <span>{c.what}</span>}</span>)}</div>;
  }
  const chips: { k: string; verb: string; n?: number | string; what?: string; tone: string }[] = [];
  Object.entries(plan.plant ?? {}).forEach(([c, n]) => chips.push({ k: `p${c}`, verb: "Plant", n, what: titleCase(c), tone: "green" }));
  Object.entries(plan.sell ?? {}).forEach(([c, n]) => chips.push({ k: `s${c}`, verb: "Sell", n, what: titleCase(c), tone: "orange" }));
  Object.entries(plan.buy_animals ?? {}).forEach(([a, n]) => chips.push({ k: `a${a}`, verb: "Buy", n, what: titleCase(a), tone: "violet" }));
  (plan.fertilise ?? []).forEach((c) => chips.push({ k: `f${c}`, verb: "Fertilise", what: titleCase(c), tone: "teal" }));
  if (plan.buy_land) chips.push({ k: "land", verb: "Buy next quadrant", tone: "blue" });
  if (plan.hands) chips.push({ k: "hands", verb: "Hire", n: plan.hands, what: "hands", tone: "gray" });
  if (!chips.length) return <div className="chips"><span className="chip gray">Maintenance only</span></div>;
  return (
    <div className="chips">
      {chips.map((c) => (
        <span key={c.k} className={`chip ${c.tone}`}><span>{c.verb}</span>{c.n !== undefined && <b>{c.n}</b>}{c.what && <span>{c.what}</span>}</span>
      ))}
    </div>
  );
}
