import React from 'react';

export default function TransactionLog({ transactions }) {
  return (
    <div className="bg-white p-2 sm:p-4 rounded shadow">
      <h3 className="text-base sm:text-lg font-semibold mb-1 sm:mb-2">Transaction Log</h3>
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-xs sm:text-sm">
          <thead>
            <tr>
              <th className="border-b p-1 sm:p-2 text-left">Contract Address</th>
              <th className="border-b p-1 sm:p-2 text-left">Action</th>
              <th className="border-b p-1 sm:p-2 text-left">Amount ($)</th>
              <th className="border-b p-1 sm:p-2 text-left">Timestamp</th>
              <th className="border-b p-1 sm:p-2 text-left">Status</th>
              <th className="border-b p-1 sm:p-2 text-left">Error</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map(tx => (
              <tr key={tx.id}>
                <td className="border-b p-1 sm:p-2 truncate max-w-[100px] sm:max-w-[200px]">{tx.token_address}</td> {/* Truncate long addresses */}
                <td className="border-b p-1 sm:p-2">{tx.transaction_type}</td>
                <td className="border-b p-1 sm:p-2">{tx.amount_in_dollars}</td>
                <td className="border-b p-1 sm:p-2 whitespace-nowrap">{tx.timestamp}</td>
                <td className="border-b p-1 sm:p-2">{tx.status}</td>
                <td className="border-b p-1 sm:p-2 truncate max-w-[100px] sm:max-w-[200px]">{tx.error || '-'}</td> {/* Truncate long errors */}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
