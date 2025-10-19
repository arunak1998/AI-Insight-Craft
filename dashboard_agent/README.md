# CSV Dashboard Agent

An intelligent AI agent that automatically creates beautiful, interactive dashboards from your CSV data. Just ask a question in plain English, and get a complete HTML dashboard with charts and insights.

---

## What Does This Do?

This agent transforms CSV data into interactive dashboards automatically:
- **Analyzes your CSV structure** - Understands columns and data types
- **Generates SQL queries** - Creates optimized queries for insights
- **Chooses best visualizations** - Picks the right charts for your data
- **Renders HTML dashboard** - Creates a complete, interactive dashboard

**Example Questions:**
- "Create a dashboard showing sales trends by region"
- "Build a dashboard for customer analysis with demographics"
- "Show me product performance metrics with comparisons"

**What You Get:**
- 📊 Time series charts for trends
- 📈 Bar charts for comparisons
- 🥧 Pie charts for composition
- 📋 Tables for detailed data
- 🎯 KPI cards with key metrics

---

## Prerequisites

Before you start, make sure you have:

1. **MCP Server** - A running MCP server with CSV tools (same as CSV Agent)
2. **AWS Bedrock Agent Core** - Set up in AWS Console
3. **Groq API Key** - Get it from [Groq Console](https://console.groq.com/)
4. **Python 3.8+** installed on your machine

---

## Installation

### Step 1: Clone the Repository

```bash
git clone <your-repo-url>
cd dashboard-agent
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Set Up Environment Variables

Create a `.env` file in the project root directory:

```env
# AWS Bedrock Agent Core Configuration
AGENT_ARN=arn:aws:bedrock-agentcore:us-east-1:123456789012:agent/your-agent-id
REGION=us-east-1
DISCOVERY_URL=https://your-discovery-url.com/.well-known/oauth-authorization-server
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret

# Groq API Configuration
GROQ_API_KEY=your-groq-api-key-here
MODEL_ID=llama-3.3-70b-versatile
```

**Important:** Replace all placeholder values with your actual credentials.

---

## How to Run

### Step 1: Start Your MCP Server

Make sure your MCP server is running and accessible. The server should provide these tools:
- `get_files_list` - List available CSV files
- `get_schema` - Get column names and types
- `execute_polars_sql` - Run SQL queries on CSV data

### Step 2: Run the Dashboard Agent

```bash
python dashboard_agent.py
```

The agent will start and connect to your MCP server via AWS Bedrock Agent Core.

### Step 3: Ask for a Dashboard

The agent accepts a payload with a `prompt` field:

```python
payload = {
    "prompt": "Create a sales dashboard showing trends and top products"
}
```

The agent will return a complete HTML dashboard ready to display!

---

## Configuration

### Groq Models

You can use different Groq models by changing `MODEL_ID` in `.env`:

- `llama-3.3-70b-versatile` (recommended for complex dashboards)
- `llama-3.1-70b-versatile`
- `mixtral-8x7b-32768`

Get your Groq API key from: https://console.groq.com/

### AWS Bedrock Setup

1. Go to AWS Console → Bedrock Agent Core
2. Create a new agent
3. Set up OAuth2 client credentials
4. Copy the Agent ARN, Client ID, and Client Secret to `.env`

---

## How It Works

The agent follows a 3-stage pipeline:

### Stage 1: Schema Analysis
- Connects to MCP server
- Reads CSV schema (columns and data types)
- Analyzes data structure
- Generates metric specifications with SQL queries

### Stage 2: SQL Execution
- Executes Polars SQL queries on your CSV
- Retrieves aggregated data for each metric
- Handles errors and validates results

### Stage 3: HTML Rendering
- Generates complete HTML dashboard
- Creates interactive Chart.js visualizations
- Applies responsive Tailwind CSS styling
- Returns production-ready HTML

---

## Supported Visualizations

The agent intelligently chooses from these chart types:

| Chart Type | Best For | Example Use |
|------------|----------|-------------|
| **Time Series** | Data over time | Sales trends, user growth |
| **Bar Chart** | Category comparison | Sales by region, products |
| **Pie Chart** | Composition | Market share, budget split |
| **Scatter Plot** | Correlations | Price vs rating, age vs salary |
| **Heatmap** | Patterns | Activity by hour/day |
| **Table** | Detailed records | Individual transactions |
| **Gauge** | KPIs with targets | Goal progress, satisfaction |
| **Funnel** | Process steps | Sales funnel, user journey |

---

## Example Output

When you ask for a dashboard, you get a complete HTML file:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Sales Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <!-- Interactive dashboard with charts -->
    <div class="dashboard-container">
        <!-- KPI Cards -->
        <!-- Charts -->
        <!-- Tables -->
    </div>
</body>
</html>
```

The HTML includes:
- ✅ Responsive design (works on mobile, tablet, desktop)
- ✅ Interactive charts (hover for details)
- ✅ Clean, modern styling
- ✅ All CSS/JS embedded (no external dependencies needed)

---

## Features

- **Smart Analysis** - Automatically understands your data structure
- **Optimized Queries** - Generates efficient Polars SQL queries
- **Intelligent Visualization** - Picks the best chart for each metric
- **Responsive Design** - Works perfectly on all screen sizes
- **Production Ready** - Complete HTML with no setup needed
- **Fast Execution** - 3-stage pipeline completes in seconds

---

## Troubleshooting

### "No file is present and there is nothing to analyze"

**Problem:** The MCP server has no CSV files loaded.

**Solution:**
- Check if your MCP server has CSV files available
- Verify the MCP server is running and accessible
- Check the file path configuration

### "The security token included in the request is invalid"

**Problem:** AWS credentials are incorrect or expired.

**Solution:**
- Double-check your `CLIENT_ID` and `CLIENT_SECRET` in `.env`
- Verify your `AGENT_ARN` is correct
- Ensure your Discovery URL is valid
- Re-generate credentials in AWS Console if needed

### Connection Timeout

**Problem:** Cannot connect to MCP server or AWS.

**Solution:**
- Check your internet connection
- Verify the MCP server URL is accessible
- Increase timeout value in the code (default is 120 seconds)
- Check firewall settings

### "SQL query failed" or "Invalid Polars SQL"

**Problem:** Generated SQL query is incompatible with Polars.

**Solution:**
- Check that your CSV columns match the schema exactly
- Verify column names are case-sensitive
- Ensure no special characters in column names
- Review Polars SQL documentation for syntax

### Empty or broken dashboard

**Problem:** HTML rendering failed or returned empty.

**Solution:**
- Check Groq API key is valid
- Verify MODEL_ID is correct
- Increase max_tokens if dashboard is complex
- Check agent logs for LLM errors

---

## Project Structure

```
dashboard-agent/
├── dashboard_agent.py      # Main agent code
├── .env                    # Environment variables (create this)
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

---

## Required Python Dependencies

Create a `requirements.txt` file with:

```
langchain-groq
langgraph
langchain-mcp-adapters
mcp
boto3
python-dotenv
bedrock-agentcore
requests
```

Install with:

```bash
pip install -r requirements.txt
```

---

## Pipeline Architecture

```
┌─────────────────────┐
│   User Question     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Stage 1: Schema    │
│  - Get CSV schema   │
│  - Analyze with LLM │
│  - Generate metrics │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Stage 2: Execute    │
│  - Run SQL queries  │
│  - Collect results  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Stage 3: Render     │
│  - Generate HTML    │
│  - Add charts       │
│  - Apply styling    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   HTML Dashboard    │
└─────────────────────┘
```

---

## Differences from CSV Agent

| Feature | CSV Agent | Dashboard Agent |
|---------|-----------|-----------------|
| **Output** | Text answer + table | Complete HTML dashboard |
| **Visualizations** | Simple markdown tables | Interactive Chart.js charts |
| **Use Case** | Q&A analysis | Visual reporting |
| **Complexity** | Single query | Multiple metrics + charts |
| **Pipeline** | 2 steps (query → answer) | 3 steps (schema → execute → render) |

---

## Security Notes

- Never commit your `.env` file to Git
- Add `.env` to `.gitignore`
- Keep your AWS credentials secure
- Rotate your Groq API key regularly
- Use environment variables for all sensitive data
- Validate user input before processing

---

## Advanced Usage

### Customizing Dashboard Style

Edit the CSS in `INSTRUCTIONS_RENDER_HTML` to change:
- Color schemes
- Card layouts
- Chart heights
- Responsive breakpoints

### Adding New Visualization Types

Update `VISUALIZATION_TYPES` in `DashboardConfig` to add:
- Radar charts
- Box plots
- Sankey diagrams
- Custom visualizations

### Optimizing Performance

- Cache schema and file paths (already implemented)
- Limit SQL query complexity
- Use sampling for large datasets
- Increase timeout for complex dashboards

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test the complete pipeline
5. Submit a pull request



---

## Support

For issues or questions:
- Open an issue on GitHub
- Check the troubleshooting section above
- Review AWS Bedrock documentation
- Check Groq API documentation

---

## Acknowledgments

Built with:
- [LangChain](https://www.langchain.com/) - LLM framework
- [LangGraph](https://langchain-ai.github.io/langgraph/) - Agent workflow
- [Groq](https://groq.com/) - Fast LLM inference
- [AWS Bedrock](https://aws.amazon.com/bedrock/) - Agent infrastructure
- [Chart.js](https://www.chartjs.org/) - Interactive charts
- [Tailwind CSS](https://tailwindcss.com/) - Responsive styling
- [MCP](https://modelcontextprotocol.io/) - Model Context Protocol

---

## Examples

### Sales Dashboard
```python
payload = {
    "prompt": "Create a sales dashboard showing monthly trends and top 10 products"
}
```

### Customer Analytics
```python
payload = {
    "prompt": "Build a customer dashboard with demographics and purchase patterns"
}
```

### Product Performance
```python
payload = {
    "prompt": "Show product metrics with revenue, units sold, and ratings"
}
```

---

**Made with ❤️ for data visualization**
