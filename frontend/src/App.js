import React, { useEffect, useState } from "react";
import { Line } from "react-chartjs-2";
import io from "socket.io-client";

const socket = io("http://localhost:8000");

const App = () => {
  const [contracts, setContracts] = useState([]);
  const [transactions, setTransactions] = useState([]);

  useEffect(() => {
    // Fetch initial data
    fetch("/api/contracts").then((res) => res.json()).then(setContracts);
    fetch("/api/transactions").then((res) => res.json()).then(setTransactions);

    // Listen for real-time updates
    socket.on("contract", (data) => {
      setContracts((prev) => [data, ...prev]);
    });

    socket.on("buy", (data) => {
      setTransactions((prev) => [data, ...prev]);
    });
  }, []);

  return (
    <div className="container mt-4">
      <h1>Contract Monitoring Dashboard</h1>
      <div className="row">
        <div className="col-md-6">
          <h2>Contracts Detected</h2>
          <ul className="list-group">
            {contracts.map((contract, index) => (
              <li key={index} className="list-group-item">
                <strong>{contract.group}</strong>: {contract.address}
                <br />
                <small>{contract.timestamp}</small>
              </li>
            ))}
          </ul>
        </div>
        <div className="col-md-6">
          <h2>Transaction History</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Token</th>
                <th>Amount</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((tx, index) => (
                <tr key={index}>
                  <td>{tx.token_bought}</td>
                  <td>${tx.amount_bought.toFixed(2)}</td>
                  <td>{tx.timestamp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default App;
