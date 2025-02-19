// Connect to WebSocket
const socket = io("http://localhost:8000");

// DOM Elements
const contractsList = document.getElementById("contracts-list");
const buyTransactions = document.getElementById("buy-transactions");
const logsList = document.getElementById("logs-list");

// Handle WebSocket connection
socket.on("connect", () => {
    console.log("WebSocket connection established.");
    addLog("WebSocket connection established.");
});

socket.on("disconnect", () => {
    console.log("WebSocket connection closed.");
    addLog("WebSocket connection closed. Please refresh the page.");
});

// Handle contract data
socket.on("contract", (data) => {
    console.log("Contract data received:", data);
    addContract(data);
});

// Handle buy transaction data
socket.on("buy", (data) => {
    console.log("Buy transaction received:", data);
    addBuyTransaction(data);
});

// Handle log messages
socket.on("log", (data) => {
    console.log("Log received:", data.message);
    addLog(data.message);
});

// Add detected contract to the list
function addContract(contract) {
    const li = document.createElement("li");
    li.textContent = `[${contract.timestamp}] Detected in ${contract.group}: ${contract.contract}`;
    contractsList.prepend(li);  // Add to the top of the list
}

// Add buy transaction to the list
function addBuyTransaction(transaction) {
    const li = document.createElement("li");
    li.textContent = `[${transaction.timestamp}] Bought ${transaction.amount_bought} of ${transaction.token_bought} (Slippage: ${transaction.slippage_paid}%)`;
    buyTransactions.prepend(li);  // Add to the top of the list
}

// Add log entry to the list
function addLog(log) {
    const li = document.createElement("li");
    li.textContent = log;
    logsList.prepend(li);  // Add to the top of the list
}
