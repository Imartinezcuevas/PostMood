import React from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const SentimentChart = ({ data }) => {
  const chartData = [
    { name: "Muy Negativo", value: data.veryNegative.percentage },
    { name: "Negativo", value: data.negative.percentage },
    { name: "Positivo", value: data.positive.percentage },
    { name: "Muy Positivo", value: data.veryPositive.percentage },
  ];

  return (
    <div style={{ width: "100%", height: 150, marginBottom: 20 }}>
      <ResponsiveContainer>
        <BarChart data={chartData}>
          <XAxis dataKey="name" />
          <YAxis unit="%" />
          <Tooltip />
          <Bar dataKey="value" fill="#4da6ff" radius={[5, 5, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default SentimentChart;
