
# ChronosMatch — Zero-Copy High-Frequency Trading Engine

**Order Matching | Trading Terminal | Market Depth | Trade Analytics | Simulation**

ChronosMatch is a Python-based High-Frequency Trading (HFT) simulation project designed to demonstrate order matching, order-book management, trade execution, and low-latency trading concepts.

The project implements a price-time priority matching engine and provides an interactive Streamlit trading terminal for submitting orders, monitoring market depth, viewing trade history, and analyzing trading performance.

**Project Status:** Development and Testing  
**Trading Mode:** Local Simulation Only

> **Note:** ChronosMatch is an educational trading simulation. It does not execute real stock-market transactions or place live broker orders.

---

## Table of Contents

1. Project Overview
2. Project Objectives
3. Features
4. Technology Stack
5. Project Architecture
6. Project Structure
7. How the Matching Engine Works
8. Order Matching Example
9. Trading Terminal Modules
10. Database Management
11. Installation and Setup
12. Running the Application
13. Running the Tests
14. Performance and Design Goals
15. Advantages
16. Limitations
17. Future Enhancements
18. Applications
19. Author
20. Disclaimer

---

## 1. Project Overview

ChronosMatch demonstrates the fundamental working principles of electronic trading systems and high-frequency trading engines.

In financial markets, buyers and sellers submit orders at different prices and quantities. An order matching engine processes these orders and identifies compatible buy and sell requests according to predefined matching rules.

ChronosMatch implements this concept using Python. It maintains buy and sell orders, processes incoming orders, executes compatible trades, and manages remaining quantities for partially filled orders.

The project also provides a Streamlit-based trading terminal that allows users to interact with the matching engine through a graphical interface.

The system combines backend order processing, database management, trading simulation, and data visualization into a modular application.

---

## 2. Project Objectives

The primary objectives of ChronosMatch are:

- To develop a Python-based order matching engine.
- To implement price-time priority matching.
- To process buy and sell orders efficiently.
- To support partial order execution.
- To maintain an organized order book.
- To store order and trade information using SQLite.
- To develop an interactive trading terminal using Streamlit.
- To visualize market depth, trade history, and execution information.
- To demonstrate paper trading and local broker-style simulation.
- To understand the architecture and design principles of high-frequency trading systems.

---

## 3. Features

### 3.1 Order Matching Engine

- Processes incoming buy and sell orders.
- Implements price-time priority matching.
- Matches compatible orders automatically.
- Supports partial order execution.
- Maintains remaining order quantities.
- Records completed trade information.

### 3.2 Order Book Management

- Maintains pending buy orders.
- Maintains pending sell orders.
- Tracks order prices and quantities.
- Updates order status after execution.
- Provides information about available simulated liquidity.

### 3.3 Interactive Trading Terminal

- Streamlit-based dashboard.
- Buy and sell order submission.
- Trading statistics and execution information.
- Organized navigation between application modules.
- Interactive data visualization.

### 3.4 Market Depth

- Displays pending buy orders.
- Displays pending sell orders.
- Shows available prices and quantities.
- Helps understand simulated market liquidity.

### 3.5 Trade History

- Displays completed trade records.
- Shows execution prices and quantities.
- Provides historical execution information.
- Supports trade filtering and analysis.

### 3.6 Trade Graphs

- Candlestick-style execution visualization.
- Execution price movement charts.
- Trading volume visualization.
- Graphical analysis of completed simulated trades.

*Note: Candlestick-style visualizations are constructed from available trade records. They do not represent live exchange market data.*

### 3.7 Performance Lab

- Displays trading performance statistics.
- Provides execution analysis.
- Helps evaluate matching-engine behavior.
- Supports analysis of simulated trading activity.

### 3.8 Risk Monitor

- Provides basic order and trading risk information.
- Helps monitor submitted quantities and prices.
- Supports validation and monitoring of simulated orders.

### 3.9 Backtesting

- Provides a module for experimenting with simulated trading data.
- Helps explore trading strategies.
- Supports analysis of hypothetical trading results.

### 3.10 Paper Trading

- Supports virtual trading operations.
- Tracks simulated balances and positions.
- Allows users to experiment without real money.
- Demonstrates a simulated trading workflow.

### 3.11 Local Upstox Simulator

- Demonstrates broker-style order management locally.
- Supports simulated order placement.
- Supports order modification.
- Supports order cancellation.
- Does not connect to the live Upstox trading platform.

---

## 4. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Main programming language |
| Streamlit | Interactive trading dashboard |
| SQLite | Database management |
| Pandas | Data processing and analysis |
| Plotly | Interactive charts and graphs |
| Custom Python Engine | Order matching |
| Python Unittest | Unit testing |
| Git | Version control |
| GitHub | Source code hosting |
| Visual Studio Code | Development environment |

---

## 5. Project Architecture

ChronosMatch follows a modular architecture consisting of the following components.

### 5.1 User Interface Layer

The Streamlit dashboard provides the interface through which users interact with the trading system.

### 5.2 Order Management Layer

This layer receives submitted buy and sell orders and passes them to the matching engine.

### 5.3 Matching Engine Layer

The matching engine checks the order book and identifies compatible orders using price-time priority.

### 5.4 Database Layer

The SQLite database stores order records, trade executions, and other relevant trading information.

### 5.5 Analytics Layer

The analytics module processes available trading records to calculate execution statistics and performance information.

### 5.6 Visualization Layer

Plotly generates charts and graphical representations of execution prices, trading volume, and market activity.

### 5.7 Simulation Layer

Paper trading and the local Upstox simulator demonstrate broker-style order operations without connecting to a live exchange.

---

## 6. Project Structure

The main project files include:

```text
chronosmatch-hft-engine/
│
├── app.py
├── chronosmatch.py
├── database.py
├── requirements.txt
├── test_chronosmatch.py
│
├── upstox_adapter.py
├── upstox_local_simulator.py
│
├── README.md
│
└── chronosmatch_aapl.db
```

Additional backup, configuration, and testing files may also be present in the repository.

### Main Files

| File | Description |
|---|---|
| app.py | Main Streamlit trading dashboard |
| chronosmatch.py | Core order matching engine |
| database.py | SQLite database operations |
| requirements.txt | Python dependencies |
| test_chronosmatch.py | Matching-engine unit tests |
| upstox_adapter.py | Supporting simulator integration |
| upstox_local_simulator.py | Local broker-style simulation |
| README.md | Project documentation |

---

## 7. How the Matching Engine Works

ChronosMatch uses the price-time priority concept.

### 7.1 Order Submission

A buy or sell order is submitted with relevant order information, including price and quantity.

### 7.2 Order-Book Processing

The engine evaluates the incoming order against compatible orders already present on the opposite side of the order book.

### 7.3 Price-Time Priority

The engine follows these principles:

- Higher-priced buy orders receive priority.
- Lower-priced sell orders receive priority.
- Earlier orders receive priority when multiple orders have the same price.

### 7.4 Order Matching

A trade can occur when:

**Best Buy Price >= Best Sell Price**

The matching engine identifies compatible orders and calculates the executable quantity.

### 7.5 Partial Execution

If only part of an order can be matched, the executed quantity is updated and the remaining quantity is retained according to the order-management rules.

### 7.6 Trade Completion

The engine records the execution and updates the remaining order quantities and order-book state.

---

## 8. Order Matching Example

Consider the following simulated orders:

| Order | Side | Price | Quantity |
|---|---|---:|---:|
| Order 1 | SELL | 100 | 10 |
| Order 2 | BUY | 99 | 5 |
| Order 3 | BUY | 101 | 6 |

The BUY order at 99 cannot match the SELL order at 100 because the buy price is lower than the sell price.

The BUY order at 101 is compatible with the SELL order at 100.

### Example Execution Result

- Execution price: 100
- Executed quantity: 6
- Remaining SELL quantity: 4

This example demonstrates partial order execution and price-time priority matching.

---

## 9. Trading Terminal Modules

The ChronosMatch dashboard contains multiple modules.

| Module | Description |
|---|---|
| Terminal Overview | Displays overall trading information |
| Order Entry | Submits simulated buy and sell orders |
| Market Depth | Displays pending buy and sell orders |
| Trade Graphs | Visualizes execution prices and volumes |
| Trade History | Displays completed trade records |
| Performance Lab | Analyzes trading performance |
| Risk Monitor | Displays basic risk-related information |
| Backtesting | Supports simulated strategy experiments |
| Paper Trading | Provides virtual trading functionality |
| Upstox Simulator | Demonstrates local broker-style order operations |

---

## 10. Database Management

ChronosMatch uses SQLite for persistent storage of trading information.

The database is managed through the project's Python database module.

The database supports information related to:

- Submitted orders.
- Buy and sell order details.
- Order prices and quantities.
- Remaining order quantities.
- Order execution status.
- Completed trade records.

SQLite provides a lightweight database solution suitable for this local development and simulation project.

---

## 11. Installation and Setup

### Prerequisites

- Python 3.10 or later.
- Visual Studio Code.
- Git.
- Basic knowledge of Python.

### Step 1: Clone the Repository

```bash
git clone https://github.com/aambikawage-web/ChronosMatch.git
```

### Step 2: Navigate to the Project Folder

```bash
cd ChronosMatch
```

### Step 3: Create a Virtual Environment (Optional)

**Windows PowerShell:**

```powershell
python -m venv .venv
```

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Step 4: Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

### Step 5: Verify Python Installation

```powershell
python --version
```

---

## 12. Running the Application

Run the following command from the project directory:

```powershell
python -m streamlit run app.py
```

After starting the application, open the following address in your browser:

```text
http://localhost:8501
```

The ChronosMatch trading dashboard will open locally.

Keep the terminal running while using the application.

---

## 13. Running the Tests

The matching engine can be tested using Python's unittest framework.

Run the following command:

```powershell
python -m unittest test_chronosmatch.py
```

The tests help validate:

- Buy and sell order processing.
- Price-time priority matching.
- Trade execution.
- Partial order matching.
- Remaining order quantities.
- Order-book operations.

Testing helps identify errors and verify the expected behavior of the matching engine.

---

## 14. Performance and Design Goals

ChronosMatch explores important design considerations used in low-latency trading systems.

These include:

- Efficient order processing.
- Predictable matching behavior.
- Reduced unnecessary processing overhead.
- Clear separation of order-book and matching logic.
- Correct handling of order quantities and partial fills.
- Modular and maintainable components.
- Testing of matching-engine functionality.

The project title references zero-copy HFT concepts as a design direction. Actual zero-copy implementation and performance improvements should be evaluated against the source code and measured benchmarks.

Performance depends on the implementation, hardware, Python runtime, and workload. Benchmark results should only be reported when they have been measured.

---

## 15. Advantages

- Demonstrates fundamental high-frequency trading concepts.
- Implements automated order matching.
- Supports price-time priority.
- Handles partial order execution.
- Provides an interactive trading terminal.
- Stores trading records using SQLite.
- Displays trade information through interactive graphs.
- Supports simulated paper trading.
- Provides a modular and extensible architecture.
- Does not require real trading capital.

---

## 16. Limitations

- The current application operates as a local simulation.
- It does not execute real stock-market transactions.
- It does not connect to a live stock exchange.
- The local Upstox simulator is not a live broker integration.
- Market information is based on locally available simulated or submitted data.
- Performance measurements depend on the local computer and execution environment.
- Current charts do not represent live exchange market data.

---

## 17. Future Enhancements

Potential improvements include:

1. Optimize the matching engine for improved processing performance.
2. Explore advanced data structures for efficient order management.
3. Introduce time-based market data and candlestick generation.
4. Improve market depth visualization.
5. Support additional order types.
6. Improve risk management and monitoring.
7. Add advanced execution latency analysis.
8. Expand unit testing and performance benchmarking.
9. Investigate zero-copy data processing techniques.
10. Explore official broker sandbox integration.

---

## 18. Applications

The concepts demonstrated in ChronosMatch can be useful for:

- Understanding electronic trading systems.
- Learning order matching algorithms.
- Studying financial market microstructure.
- Demonstrating price-time priority.
- Learning trading data visualization.
- Exploring simulated trading systems.
- Academic projects and software engineering demonstrations.

---

## 19. Author

**Ambika Wage**

Information Science and Engineering  
SJC Institute of Technology  
Chikkaballapura, Karnataka, India

**GitHub Repository:**

https://github.com/aambikawage-web/ChronosMatch

---

## 20. Disclaimer

ChronosMatch is an educational and software development project created to demonstrate order matching, trading workflows, and market simulation concepts.

It is not a financial advisory system or a live trading platform. All order placement and execution functionality is intended for local simulation only.

No real-money transactions or live stock-market orders are executed.
