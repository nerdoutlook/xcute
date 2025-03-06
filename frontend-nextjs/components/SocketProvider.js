import React, { createContext, useEffect, useState } from 'react';
import io from 'socket.io-client';

export const SocketContext = createContext();

const socket = io('https://xcute.onrender.com', { transports: ['websocket'] });

const SocketProvider = ({ children }) => {
  const [socketData, setSocketData] = useState({ contracts: [], transactions: [] });

  useEffect(() => {
    socket.on('connect', () => console.log('Connected to WebSocket'));
    socket.on('contract', (data) => {
      setSocketData((prev) => ({
        ...prev,
        contracts: [data, ...prev.contracts.slice(0, 9)], // Limit to 10
      }));
    });
    socket.on('buy', (data) => {
      setSocketData((prev) => ({
        ...prev,
        transactions: [data, ...prev.transactions],
      }));
    });
    socket.on('sell', (data) => {
      setSocketData((prev) => ({
        ...prev,
        transactions: [data, ...prev.transactions],
      }));
    });

    return () => {
      socket.off('connect');
      socket.off('contract');
      socket.off('buy');
      socket.off('sell');
    };
  }, []);

  return (
    <SocketContext.Provider value={{ socket, socketData }}>
      {children}
    </SocketContext.Provider>
  );
};

export default SocketProvider;
