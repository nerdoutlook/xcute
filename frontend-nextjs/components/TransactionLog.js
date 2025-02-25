import React from 'react';

export default function TransactionLog({ transactions }) {
  return (
    <div className="bg-white p-4 rounded shadow">
      <h3 className="text-lg font-semibold mb-2">Transaction Log</h3>
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead>
            <tr>
              <th className="border-b p-2 text-left">Contract Address</th>
              <th className="border-b p-2 text-left">Action</th>
              <th className="border-b p-2 text-left">Amount ($)</th>
              <th className="border-b p-2 text-left">Timestamp</th>
              <th className="border-b p-2 text-left">Status</th> {/* Added */}
              <th className="border-b p-2 text-left">Error</th>  {/* Added */}
            </tr>
          </thead>
          <tbody>
            {transactions.map(tx => (
              <tr key={tx.id}>
                <td className="border-b p-2">{tx.token_address}</td>
                <td className="border-b p-2">{tx.transaction_type}</td>
                <td className="border-b p-2">{tx.amount_in_dollars}</td>
                <td className="border-b p-2">{tx.timestamp}</td>
                <td className="border-b p-2">{tx.status}</td> {/* Added */}
                <td className="border-b p-2">{tx.error || '-'}</td> {/* Added */}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
