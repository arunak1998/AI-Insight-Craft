# MCP Polars SQL Analyst Server  

> High-performance Model Context Protocol (MCP) server for CSV analysis and SQL execution using Polars  

---

## 🚀 Overview  

The **MCP Polars SQL Analyst Server** enables AI agents and developers to interact with CSV datasets through natural language or SQL queries.  
It leverages the **Polars DataFrame engine (Rust-powered, multi-threaded, lazy evaluation)** for lightning-fast analytics on large files.  

With this server, you can:  
- ✅ Discover CSV files available in a directory  
- ✅ Inspect schemas, datatypes, and stats  
- ✅ Run **SQL queries** directly on your CSVs using Polars SQL  
- ✅ Easily integrate with AI agents and dashboards for **interactive CSV insights**  

---

## ✨ Features  

- **High-Performance Data Processing**  
  - Rust-based Polars engine (faster than pandas)  
  - Multi-threaded execution across CPUs  
  - Lazy evaluation for optimized queries  
  - Memory-efficient for large datasets  

- **MCP Tools Available**  
  1. **get_files_list**  
     - 📂 Retrieve all available CSV files in the configured directory  
     - *Returns:* List of file names and paths  

  2. **get_schema**  
     - 🔎 Extract schema: column names, datatypes, and basic stats  
     - *Params:* file_path (CSV file path)  
     - *Returns:* JSON with field info  

  3. **execute_polars_sql**  
     - 📝 Run SQL queries on CSV data via Polars SQL engine  
     - *Params:* sql_query, file_path  
     - *Returns:* Structured query results  

---

## 🛠️ Technology Stack  

- **MCP Framework:** FastMCP – rapid protocol server creation  
- **Data Engine:** Polars – fast, Rust-native DataFrame library  
- **Query Language:** SQL (via Polars SQL context)  
- **File Support:** CSV datasets  

📦 Installation
bash
# Clone repository
git clone https://github.com/yourusername/mcp-polars-analyst.git
cd mcp-polars-analyst

# Install dependencies
pip install -e .
▶️ Usage
Start the MCP server and point to your CSV directory:

bash
FILE_LOCATION="/mnt/c/workspaces/mcpserver/temp/*.csv" \
python server/analyst.py
The server will:

Scan the specified location for CSVs

Initialize Polars SQL context

Expose MCP tools (get_files_list, get_schema, execute_polars_sql)

Start SSE (Server-Sent Events) for agent communication
