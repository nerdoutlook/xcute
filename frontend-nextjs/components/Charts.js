import React from 'react';
import { Line, Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend } from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend);

export default function Charts({ transactions }) {
  const profitData = {
    labels: transactions.map(t => new Date(t.timestamp).toLocaleTimeString()),
    datasets: [{
      label: 'Profit Over Time',
      data: transactions.map(t => t.transaction_type === 'sell' ? t.amount_in_dollars : -t.amount_in_dollars),
      borderColor: 'rgba(75, 192, 192, 1)',
      fill: false,
    }],
  };

  const successData = {
    labels: ['Buys', 'Sells'],
    datasets: [{
      label: 'Success Rates',
      data: [
        transactions.filter(t => t.transaction_type === 'buy').length,
        transactions.filter(t => t.transaction_type === 'sell').length,
      ],
      backgroundColor: ['rgba(54, 162, 235, 0.6)', 'rgba(255, 99, 132, 0.6)'],
    }],
  };

  return (
    <div className="mb-6">
      <div className="bg-white p-4 rounded shadow mb-4">
        <h2 className="text-lg font-semibold mb-2">Profit Trends</h2>
        <Line data={profitData} options={{ responsive: true }} />
      </div>
      <div className="bg-white p-4 rounded shadow">
        <h2 className="text-lg font-semibold mb-2">Buy/Sell Success</h2>
        <Bar data={successData} options={{ responsive: true }} />
      </div>
    </div>
  );
}
