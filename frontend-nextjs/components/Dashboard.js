
import { useEffect, useState, useContext } from 'react';
import { SocketContext } from './SocketProvider';
import TransactionLog from './TransactionLog';
import Charts from './Charts';
import { toast } from 'react-toastify';
import axios from 'axios';
import { io } from 'socket.io-client';

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
  const [balance, setBalance] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [contractsRes, transactionsRes, balanceRes] = await Promise.all([
          axios.get('https://xcute.onrender.com/api/contracts'),
          axios.get('https://xcute.onrender.com/api/transactions'),
          axios.get('https://xcute.onrender.com/api/wallet_balance'),
        ]);
        setContracts(contractsRes.data);
        setTransactions(transactionsRes.data);
        setBalance(balanceRes.data.balance);
        updateMetrics(contractsRes.data, transactionsRes.data);
      } catch (error) {
        console.error('Error fetching data:', error);
      }
    };
    fetchData();

    // Connect to Render backend WebSocket
    const socket = io('https://xcute.onrender.com', { transports: ['websocket', 'polling'] });
    socket.on('connect', () => console.log('WebSocket connected'));
    socket.on('connect_error', (err) => console.error('WebSocket connection error:', err.message));
    socket.on('contract', (data) => {
      console.log('New contract:', data);
      setContracts(prev => [...prev, data]);
      toast.info(`New contract: ${data.contract}`);
      fetchData();
    });
    socket.on('buy', (data) => {
      console.log('Buy succeeded:', data);
      setTransactions(prev => [...prev, { ...data, transaction_type: 'buy', status: 'success' }]);
      toast.success(`Buy executed: ${data.token_bought} for $${data.dollar_value}`);
      fetchData();
    });
    socket.on('buy_failed', (data) => {
      console.log('Buy failed:', data);
      setTransactions(prev => [...prev, {
        token_address: data.token,
        transaction_type: 'buy',
        amount_in_dollars: 1.0,
        amount_in_sol: 0,
        status: 'failed',
        error: data.error,
        timestamp: data.timestamp
      }]);
      toast.error(`Buy failed: ${data.token} - ${data.error}`);
      fetchData();
    });

    return () => {
      socket.disconnect();
      console.log('WebSocket disconnected');
    };
  }, []);

  const updateMetrics = (contractsData, transactionsData) => {
    const totalContracts = contractsData.length;
    const successfulBuys = transactionsData.filter(t => t.transaction_type === 'buy' && t.status === 'success').length;
    const successfulSells = transactionsData.filter(t => t.transaction_type === 'sell' && t.status === 'success').length;
    const profit = transactionsData.reduce((acc, t) => {
      return t.transaction_type === 'sell' && t.status === 'success' ? acc + t.amount_in_dollars : acc;
    }, 0) - transactionsData.reduce((acc, t) => {
      return t.transaction_type === 'buy' && t.status === 'success' ? acc + t.amount_in_dollars : acc;
    }, 0);
    const activeContracts = new Set(transactionsData.filter(t => t.transaction_type === 'buy' && t.status === 'success').map(t => t.token_address)).size;
    setMetrics({ totalContracts, successfulBuys, successfulSells, profit, activeContracts });
  };

  return (
    <div className="p-2 sm:p-4 max-w-full sm:max-w-7xl mx-auto">
      <h1 className="text-xl sm:text-3xl font-bold mb-4 sm:mb-6">Xcute Trading Dashboard</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-4 mb-4 sm:mb-6">
        <div className="bg-white p-2 sm:p-4 rounded shadow">
          <h2 className="text-sm sm:text-lg font-semibold">Total Contracts</h2>
          <p className="text-lg sm:text-2xl">{metrics.totalContracts}</p>
        </div>
        <div className="bg-white p-2 sm:p-4 rounded shadow">
          <h2 className="text-sm sm:text-lg font-semibold">Successful Trades</h2>
          <p className="text-lg sm:text-2xl">{metrics.successfulBuys + metrics.successfulSells}</p>
        </div>
        <div className="bg-white p-2 sm:p-4 rounded shadow">
          <h2 className="text-sm sm:text-lg font-semibold">Profit/Loss</h2>
          <p className={`text-lg sm:text-2xl ${metrics.profit >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            ${metrics.profit.toFixed(2)}
          </p>
        </div>
        <div className="bg-white p-2 sm:p-4 rounded shadow">
          <h2 className="text-sm sm:text-lg font-semibold">Wallet Balance</h2>
          <p className="text-lg sm:text-2xl">{balance.toFixed(6)} SOL</p>
        </div>
      </div>
      <Charts transactions={transactions} />
      <TransactionLog transactions={transactions} />
    </div>
  );
}
