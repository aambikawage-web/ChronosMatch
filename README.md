# ChronosMatch
A high-performance, zero-copy matching engine designed for high-frequency trading, focusing on low-latency order processing and efficient order matching.
# ChronosMatch – High-Frequency Trading Engine

## Project Overview
ChronosMatch is a Python-based simulated trading engine designed to demonstrate order matching, trade execution, and order book management.

## Features
- Buy and sell order processing
- Order matching and trade execution
- Partial order matching
- SQLite database integration
- Streamlit trading dashboard
- Unit tests for core matching functionality

## Technology Stack
- Python
- Streamlit
- SQLite
- Pandas
- Plotly
- Unittest

## Project Structure
- `chronosmatch.py` – Core order matching engine
- `database.py` – Database operations and persistence
- `app.py` – Interactive trading dashboard
- `test_chronosmatch.py` – Unit tests
- `requirements.txt` – Python dependencies

## How to Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the dashboard:

```bash
streamlit run app.py
```

Run the tests:

```bash
python -m unittest -v test_chronosmatch.py
```

## Disclaimer
This project is an educational trading simulation. It is not intended for live trading or financial advice.
