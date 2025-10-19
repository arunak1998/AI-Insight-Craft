# CSV Analysis Agent

A smart AI agent that analyzes CSV files using natural language queries. Built with AWS Bedrock Agent Core and MCP (Model Context Protocol).

---

## What Does This Do?

Ask questions about your CSV data in plain English, and the agent will:
- Read your CSV files
- Understand the data structure
- Run SQL queries automatically
- Give you insights and answers

**Example Questions:**
- "What are the top 5 customers by revenue?"
- "Show me average sales by month"
- "Which products have the highest profit margin?"

---

## Prerequisites

Before you start, make sure you have:

1. **MCP Server** - A running MCP server with CSV tools
2. **AWS Bedrock Agent Core** - Set up in AWS Console
3. **Groq API Key** - Get it from [Groq Console](https://console.groq.com/)
4. **Python 3.8+** installed on your machine

---

## Installation

### Step 1: Clone the Repository

```bash
git clone <your-repo-url>
cd csv-analysis-agent
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
- `read_file` - Read CSV content
- `get_schema` - Get column names and types
- `execute_polars_sql` - Run SQL queries on CSV data

### Step 2: Run the Agent

```bash
python your_script_name.py
```

The agent will start and connect to your MCP server via AWS Bedrock Agent Core.

### Step 3: Ask Questions

The agent accepts a payload with a `prompt` field:

```python
payload = {
    "prompt": "What are the top 3 teams by average score?"
}
```

---

## Configuration

### Groq Models

You can use different Groq models by changing `MODEL_ID` in `.env`:

- `llama-3.3-70b-versatile` (recommended)
- `llama-3.1-70b-versatile`
- `mixtral-8x7b-32768`
- `gemma2-9b-it`

Get your Groq API key from: https://console.groq.com/

### AWS Bedrock Setup

1. Go to AWS Console → Bedrock Agent Core
2. Create a new agent
3. Set up OAuth2 client credentials
4. Copy the Agent ARN, Client ID, and Client Secret to `.env`

---

## Features

- **Smart Caching** - Remembers file paths and schemas to avoid repeated calls
- **SQL Query Optimization** - Automatically generates efficient Polars SQL queries
- **Error Handling** - Clear error messages when files are missing or queries fail
- **Formatted Output** - Results presented as clean tables with insights
- **Natural Language** - No need to write SQL, just ask questions

---

## Example Output

When you ask a question, you get formatted results:

```
📊 Answer Summary
Top 3 teams by average score.

📋 Key Insights
• MI leads with 180 average runs.
• CSK follows closely with 175.
• RCB trails with 165.

📈 Table Output
| Team | Avg Runs |
|------|----------|
| MI   | 180      |
| CSK  | 175      |
| RCB  | 165      |

🚀 Next Step Suggestion
Would you like a year-over-year trend chart for these averages?
```

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

### "Tool not found" errors

**Problem:** MCP server doesn't have required tools.

**Solution:**
- Ensure your MCP server implements all required tools
- Check MCP server logs for errors
- Verify tool names match exactly

---

## Project Structure

```
csv-analysis-agent/
├── your_script.py          # Main agent code
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

## How It Works

1. **Connection** - Agent connects to MCP server using AWS Bedrock Agent Core
2. **Authentication** - Uses OAuth2 to authenticate with bearer token
3. **Caching** - Loads and caches file paths and CSV schemas
4. **Query Processing** - Converts natural language to SQL queries
5. **Execution** - Runs queries on CSV data using Polars
6. **Results** - Formats and presents insights in clean tables

---

## Security Notes

- Never commit your `.env` file to Git
- Add `.env` to `.gitignore`
- Keep your AWS credentials secure
- Rotate your Groq API key regularly
- Use environment variables for all sensitive data

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---


---

## Support

For issues or questions:
- Open an issue on GitHub
- Check the troubleshooting section above
- Review AWS Bedrock documentation

---

## Acknowledgments

Built with:
- [LangChain](https://www.langchain.com/) - LLM framework
- [Groq](https://groq.com/) - Fast LLM inference
- [AWS Bedrock](https://aws.amazon.com/bedrock/) - Agent infrastructure
- [MCP](https://modelcontextprotocol.io/) - Model Context Protocol

---

**Made with ❤️ for data analysts**
