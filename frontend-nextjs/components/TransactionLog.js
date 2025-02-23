import React from 'react';

export default function TransactionLog({ transactions }) {
  return (
    <div className="bg-white p-4 rounded shadow">
      <h2 className="text-lg font-semibold mb-2">Transaction History</h2>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Token</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Amount ($)</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {transactions.map((tx, index) => (
              <tr key={index}>
                <td className="px-6 py-4 whitespace-nowrap">{tx.token_address || tx.token_sold}</td>
                <td className="px-6 py-4 whitespace-nowrap">{tx.transaction_type || (tx.token_bought ? 'buy' : 'sell')}</td>
                <td className="px-6 py-4 whitespace-nowrap">${tx.amount_in_dollars.toFixed(2)}</td>
                <td className="px-6 py-4 whitespace-nowrap">{new Date(tx.timestamp).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
