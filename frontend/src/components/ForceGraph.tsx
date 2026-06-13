import { useEffect, useRef, useState } from "react";

interface Node {
  id: number;
  label: string;
  center_id: number | null;
}
interface Edge {
  source: number;
  target: number;
  weight: number;
  same_center: boolean;
}
interface P {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

const COLORS = ["#C8281A", "#1A7A4A", "#7B3FBE", "#2D6FA3", "#B07D2A"];

/** Tiny hand-rolled force-directed layout (no D3 dependency) rendered as SVG. */
export default function ForceGraph({ nodes, edges }: { nodes: Node[]; edges: Edge[] }) {
  const W = 760;
  const H = 440;
  const [pos, setPos] = useState<Record<number, P>>({});
  const raf = useRef<number>(0);

  useEffect(() => {
    const p: Record<number, P> = {};
    nodes.forEach((n, i) => {
      const a = (i / Math.max(1, nodes.length)) * Math.PI * 2;
      p[n.id] = { x: W / 2 + Math.cos(a) * 140, y: H / 2 + Math.sin(a) * 140, vx: 0, vy: 0 };
    });

    let ticks = 0;
    const step = () => {
      ticks++;
      const ids = nodes.map((n) => n.id);
      // repulsion
      for (let i = 0; i < ids.length; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          const a = p[ids[i]];
          const b = p[ids[j]];
          let dx = a.x - b.x;
          let dy = a.y - b.y;
          let d2 = dx * dx + dy * dy || 0.01;
          const f = 1800 / d2;
          const d = Math.sqrt(d2);
          const ux = dx / d;
          const uy = dy / d;
          a.vx += ux * f;
          a.vy += uy * f;
          b.vx -= ux * f;
          b.vy -= uy * f;
        }
      }
      // spring attraction along edges
      edges.forEach((e) => {
        const a = p[e.source];
        const b = p[e.target];
        if (!a || !b) return;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
        const target = 70;
        const f = (d - target) * 0.02 * (0.5 + e.weight);
        const ux = dx / d;
        const uy = dy / d;
        a.vx += ux * f;
        a.vy += uy * f;
        b.vx -= ux * f;
        b.vy -= uy * f;
      });
      // integrate + center gravity + damping
      ids.forEach((id) => {
        const n = p[id];
        n.vx += (W / 2 - n.x) * 0.002;
        n.vy += (H / 2 - n.y) * 0.002;
        n.vx *= 0.85;
        n.vy *= 0.85;
        n.x = Math.max(20, Math.min(W - 20, n.x + n.vx));
        n.y = Math.max(20, Math.min(H - 20, n.y + n.vy));
      });
      setPos({ ...p });
      if (ticks < 240) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [nodes, edges]);

  if (!nodes.length)
    return <div className="empty">No collusion network detected for this exam.</div>;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ background: "#FAFAFA", borderRadius: 8 }}>
      {edges.map((e, i) => {
        const a = pos[e.source];
        const b = pos[e.target];
        if (!a || !b) return null;
        return (
          <line
            key={i}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke={e.same_center ? "#C8281A" : "#BBB"}
            strokeWidth={0.6 + e.weight * 4}
            strokeOpacity={0.5}
          />
        );
      })}
      {nodes.map((n) => {
        const a = pos[n.id];
        if (!a) return null;
        const c = COLORS[(n.center_id || 0) % COLORS.length];
        return (
          <g key={n.id}>
            <circle cx={a.x} cy={a.y} r={9} fill={c} />
            <text x={a.x} y={a.y - 13} textAnchor="middle" fontSize={8} fill="#555">
              {n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
