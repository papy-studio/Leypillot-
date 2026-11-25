import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>
      {payload.map((item) => (
        <span key={item.dataKey}><i style={{ backgroundColor: item.color }} />{item.name}: {item.value}</span>
      ))}
    </div>
  );
}

function RegulatoryTrendChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
        <defs>
          <linearGradient id="confirmedFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#173d61" stopOpacity={0.14} />
            <stop offset="95%" stopColor="#173d61" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="anticipatedFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f2653b" stopOpacity={0.16} />
            <stop offset="95%" stopColor="#f2653b" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#edf0f3" strokeDasharray="3 5" vertical={false} />
        <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: "#919aa5", fontSize: 11 }} dy={9} />
        <YAxis axisLine={false} tickLine={false} tick={{ fill: "#a4abb4", fontSize: 10 }} />
        <Tooltip content={<ChartTooltip />} />
        <Area type="monotone" dataKey="confirmed" name="Confirmés" stroke="#173d61" strokeWidth={2.5} fill="url(#confirmedFill)" activeDot={{ r: 4, strokeWidth: 0 }} />
        <Area type="monotone" dataKey="anticipated" name="Anticipés" stroke="#f2653b" strokeWidth={2.5} strokeDasharray="5 4" fill="url(#anticipatedFill)" activeDot={{ r: 4, strokeWidth: 0 }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export default RegulatoryTrendChart;
