import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

// Initialize Socket.io
const socket = window.io("http://localhost:8000");

// Update contract count
let contractCount = 0;
socket.on("contract", (data) => {
    contractCount++;
    document.getElementById("contract-count").textContent = contractCount;

    // Add contract to the table
    const contractTable = document.getElementById("contract-table");
    const row = document.createElement("tr");
    row.innerHTML = `
        <td>${data.contract}</td>
        <td>${data.group}</td>
        <td>${data.timestamp}</td>
    `;
    contractTable.prepend(row);
});

// Update transaction count
let transactionCount = 0;
socket.on("buy", (data) => {
    transactionCount++;
    document.getElementById("transaction-count").textContent = transactionCount;

    // Add transaction to the table
    const transactionTable = document.getElementById("transaction-table");
    const row = document.createElement("tr");
    row.innerHTML = `
        <td>${data.token_bought}</td>
        <td>$${data.amount_bought.toFixed(2)}</td>
        <td>${data.timestamp}</td>
    `;
    transactionTable.prepend(row);
});

// Initialize charts
const contractChart = new window.Chart(document.getElementById("contract-chart"), {
    type: "line",
    data: {
        labels: [],
        datasets: [{
            label: "Contracts Detected",
            data: [],
            borderColor: "#007bff",
            fill: false
        }]
    },
    options: {
        responsive: true,
        scales: {
            x: {
                display: true,
                title: {
                    display: true,
                    text: "Time"
                }
            },
            y: {
                display: true,
                title: {
                    display: true,
                    text: "Contracts"
                }
            }
        }
    }
});

const transactionChart = new window.Chart(document.getElementById("transaction-chart"), {
    type: "bar",
    data: {
        labels: [],
        datasets: [{
            label: "Transactions Executed",
            data: [],
            backgroundColor: "#28a745"
        }]
    },
    options: {
        responsive: true,
        scales: {
            x: {
                display: true,
                title: {
                    display: true,
                    text: "Time"
                }
            },
            y: {
                display: true,
                title: {
                    display: true,
                    text: "Transactions"
                }
            }
        }
    }
});

// Update charts with real-time data
socket.on("contract", (data) => {
    const labels = contractChart.data.labels;
    const dataset = contractChart.data.datasets[0].data;

    labels.push(data.timestamp);
    dataset.push(contractCount);

    if (labels.length > 10) {
        labels.shift();
        dataset.shift();
    }

    contractChart.update();
});

socket.on("buy", (data) => {
    const labels = transactionChart.data.labels;
    const dataset = transactionChart.data.datasets[0].data;

    labels.push(data.timestamp);
    dataset.push(transactionCount);

    if (labels.length > 10) {
        labels.shift();
        dataset.shift();
    }

    transactionChart.update();
});

// Create a root element and render the app
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
    <React.StrictMode>
        <App />
    </React.StrictMode>
);
