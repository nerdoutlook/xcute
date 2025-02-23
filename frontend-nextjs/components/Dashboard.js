import { useEffect, useState, useContext } from 'react';
import { SocketContext } from './SocketProvider';
import TransactionLog from './TransactionLog';
import Charts from './Charts';
import { toast } from 'react-toastify';
import axios from 'axios';

export default function Dashboard() {
  const { socketData } = useContext(SocketContext);
  const [contracts, setContracts] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [metrics, setMetrics] = useState({
    totalContracts: 0,
    successfulBuys: 0,
    successfulSells: 0,
    profit: 0,
    activeContracts: 0,
  });

  useEffect(() => {
    const fetchData = async () => {
      const [contractsRes, transactionsRes] = await Promise.all([
        axios.get('http://localhost:8000/api/contracts'),
        axios.get('http://localhost:8000/api/transactions'),
      ]);
      setContracts(contractsRes.data);
      setTransactions(transactionsRes.data);
      updateMetrics(contractsRes.data, transactionsRes.data);
    };
    fetchData();

    setContracts(socketData.contracts);
    setTransactions(socketData.transactions);

    socketData.contracts.forEach(data => toast.info(`New contract: ${data.contract}`));
    socketData.transactions.forEach(data => {
      if (data.token_bought) {
        toast.success(`Buy executed: ${data.token_bought} for $${data.dollar_value}`);
      } else if (data.token_sold) {
        toast.success(`Sell executed: ${data.token_sold} for $${data.dollar_value}`);
      }
    });
  }, [socketData]);

  const updateMetrics = (contractsData, transactionsData) => {
    const totalContracts = contractsData.length;
    const successfulBuys = transactionsData.filter(t => t.transaction_type === 'buy').length;
    const successfulSells = transactionsData.filter(t => t.transaction_type === 'sell').length;
    const profit = transactionsData.reduce((acc, t) => {
      return t.transaction_type === 'sell' ? acc + t.amount_in_dollars : acc;
    }, 0) - transactionsData.reduce((acc, t) => {
      return t.transaction_type === 'buy' ? acc + t.amount_in_dollars : acc;
    }, 0);
    const activeContracts = new Set(transactionsData.filter(t => t.transaction_type === 'buy').map(t => t.token_address)).size;

    setMetrics({ totalContracts, successfulBuys, successfulSells, profit, activeContracts });
  };

  return (
    <div className="p-4 max-w-7xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Xcute Trading Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white p-4 rounded shadow">
          <h2 className="text-lg font-semibold">Total Contracts</h2>
          <p className="text-2xl">{metrics.totalContracts}</p>
        </div>
        <div className="bg-white p-4 rounded shadow">
          <h2 className="text-lg font-semibold">Successful Trades</h2>
          <p className="text-2xl">{metrics.successfulBuys + metrics.successfulSells}</p>
        </div>
        <div className="bg-white p-4 rounded shadow">
          <h2 className="text-lg font-semibold">Profit/Loss</h2>
          <p className={`text-2xl ${metrics.profit >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            ${metrics.profit.toFixed(2)}
          </p>
        </div>
      </div>
      <Charts transactions={transactions} />
      <TransactionLog transactions={transactions} />
    </div>
  );
}
