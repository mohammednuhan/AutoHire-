"use client";

import { Bar, BarChart, Cell, ResponsiveContainer, XAxis, YAxis } from "recharts";
import type { ScoreBreakdown } from "../../types/api";

export function ScoreBreakdownChart({ score }: { score?: ScoreBreakdown | null }) {
  const data = [
    { name: "Technical", value: score?.technical_match ?? 0 },
    { name: "Experience", value: score?.experience_match ?? 0 },
    { name: "Domain", value: score?.domain_match ?? 0 },
    { name: "Location", value: score?.location_match ?? 0 },
    { name: "Growth", value: score?.growth_potential ?? 0 },
  ];

  return (
    <div className="h-44 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
          <XAxis type="number" domain={[0, 100]} hide />
          <YAxis dataKey="name" type="category" width={82} tick={{ fontSize: 12 }} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={14}>
            {data.map((entry) => (
              <Cell
                key={entry.name}
                fill={entry.value >= 80 ? "#059669" : entry.value >= 60 ? "#d97706" : "#64748b"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
