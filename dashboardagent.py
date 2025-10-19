import asyncio
import os
import time
import json
import logging
from textwrap import dedent
from typing import Dict, Any, List, TypedDict, Annotated
from dataclasses import dataclass
from mcp.client.streamable_http import streamablehttp_client
import requests
from dotenv import load_dotenv
from mcp.client.sse import sse_client
from mcp import ClientSession
from langchain_groq import ChatGroq
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
import asyncio

app = BedrockAgentCoreApp()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class PipelineState(TypedDict):
    """State container for dashboard pipeline"""
    messages: Annotated[List[BaseMessage], "add_messages"]
    csv_file_path: str
    tool: BaseTool


class DashboardConfig:
    """Configuration for Dashboard Agent"""

    VISUALIZATION_TYPES = {
        "time_series": "Data that changes over time (sales trends, user growth)",
        "bar_chart": "Comparing categories or groups (sales by region, products by category)",
        "pie_chart": "Showing composition or proportion (market share, budget allocation)",
        "scatter_plot": "Relationship between two variables (price vs. rating, age vs. salary)",
        "heatmap": "Showing patterns or intensity across multiple dimensions (activity by hour/day)",
        "table": "Detailed individual records or aggregates requiring precise values",
        "gauge": "KPIs with target values (sales goals, customer satisfaction)",
        "funnel": "Sequential process steps with drop-offs (sales funnel, user journey)",
    }

    INSTRUCTIONS_CSV_ANALYSIS = dedent(
        """You are an expert data analyst. Analyze the provided CSV schema and return a JSON report.

INPUT:
- "schema": JSON array with columns "name" and "dtype"
- "question": user's analysis request

OBJECTIVE:
- Generate a JSON report with key metrics and a valid Polars SQL query for each metric
- SQL must be fully compatible with Polars: no joins, no subqueries, proper GROUP BY usage, valid window functions

CRITICAL RULES:
1. Do NOT call any tools.
2. Return ONLY the JSON report and STOP.
3. All SQL queries must be compatible with Polars SQL.
4. No hallucinations: only use columns present in the schema exactly (case-sensitive).

POLARS SQL CONSTRAINTS:
- Use FROM self as the table source.
- Quote identifiers with double quotes if they contain spaces or special characters.
- Use single quotes only for string literals.
- Do not use backticks.
- Do not use subqueries anywhere (SELECT, WHERE, HAVING, FROM)
- Use explicit GROUP BY for aggregations, explicit ORDER BY for sorting.

A. Absolute Prohibitions
- ❌ NO subqueries anywhere (SELECT, WHERE, HAVING, FROM)
- ❌ NO JOINs (implicit or explicit)
- ❌ NO SELECT * with GROUP BY
- ❌ NO aggregates without GROUP BY when grouping is required
- ❌ NO window functions in WHERE, HAVING, or JOIN clauses

B. Mandatory Rules
- Table name is always `self`.
- Quote identifiers with double quotes if they contain spaces or special characters.
- Use single quotes only for string literals.
- Do not use backticks.
- Use `AS alias_name` for all derived tables (CTEs).
- For UNION ALL, ensure identical column names using `AS` aliases.

PRE-GENERATION CHECKS
1. Validate all columns exist exactly as in schema.
2. Decide if the question requires overall aggregates or per-group metrics.
3. Pick a valid grouping column if needed (user-specified or default).
4. Ensure all GROUP BY clauses have at least one column.
5. Avoid subqueries or implicit joins entirely.
6. Apply all aliases correctly.

JSON FORMAT
{
  "domain": "Identified domain",
  "key_metrics": [
    {
      "metric": "Metric Name",
      "description": "Brief description",
      "visualization_type": "chart_type",
      "visualization_rationale": "Why this chart",
      "sql": "Valid Polars SQL query"
    }
  ],
  "dashboard_components": ["filters","charts","tables"]
}

Visualization types: """ + json.dumps(VISUALIZATION_TYPES)
    )

    INSTRUCTIONS_RENDER_HTML = dedent(
        """You are a senior dashboard UI engineer.

Input:
- A JSON object with array `metrics`.
- Each metric has: metric, description, visualization_type, data

Task:
Generate a complete HTML document for a responsive dashboard that renders perfectly in Streamlit with ZERO extra whitespace.

CRITICAL LAYOUT RULES:
1. Body MUST have: margin:0; padding:0; overflow-x:hidden;
2. Root container MUST have: width:100%; padding:0; margin:0;
3. NO max-w-* classes on outer containers
4. Cards MUST use: margin:16px 0; (vertical only, NO horizontal margins)
5. All content MUST be contained within viewport width
6. NO default body margins or padding

HTML STRUCTURE:
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0 !important;
            padding: 0 !important;
            overflow-x: hidden !important;
            background-color: #f3f4f6;
        }
        .dashboard-container {
            width: 100%;
            padding: 16px;
            margin: 0;
        }
        .metric-card {
            background: white;
            border-radius: 0.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            padding: 1.5rem;
            margin: 16px 0;
        }
        .chart-container {
            width: 100%;
            height: 400px;
            position: relative;
        }
    </style>
</head>
<body>
    <div class="dashboard-container">
        <!-- Cards go here -->
    </div>
</body>
</html>

Output:
Return ONLY the complete HTML document with NO markdown formatting, NO code fences, just raw HTML.
"""
    )

    def __init__(self):
        self.model_id = os.getenv("MODEL_ID", "openai/gpt-oss-120b")
        self.api_key = os.getenv("GROQ_API_KEY")
        self.agent_arn = os.getenv('AGENT_ARN')
        self.region = os.getenv('REGION')
        self.discovery_url = os.getenv('DISCOVERY_URL')
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')

        self._validate_config()
        self.mcp_url = self._construct_mcp_url()
        self.csv_path=None
        self.schema=None

        print(f"Agent ARN: {self.agent_arn}")

    def _validate_config(self):
        """Validate required configuration"""
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set.")
    def _construct_mcp_url(self) -> str:
        """Construct MCP URL from agent ARN"""
        encoded_arn = self.agent_arn.replace(':', '%3A').replace('/', '%2F')
        return f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

class AuthenticationManager:
    """Handles OAuth2 authentication"""

    def __init__(self, config: DashboardConfig):
        self.config = config

    def get_bearer_token(self) -> str:
        """Gets a fresh access token using the Client Credentials Flow"""
        print("🔑 Getting fresh Bearer Token...")

        response = requests.get(self.config.discovery_url, timeout=10)
        response.raise_for_status()
        token_endpoint = response.json().get('token_endpoint')

        data = {
            'grant_type': 'client_credentials',
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
        }

        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        response = requests.post(token_endpoint, data=data, headers=headers, timeout=10)
        response.raise_for_status()
        token_data = response.json()
        print("Token retrieved successfully.")
        return token_data.get('access_token')

class FileCache:
    """Manages file path and schema caching"""

    def __init__(self, dashboard_config:DashboardConfig):
        self.dashboard_config = dashboard_config  # using DashboardConfig instead of optimizer

    async def cache_file_path(self, tools: List):
        """Cache file path from get_files_list tool"""
        if not getattr(self.dashboard_config, "csv_path", None):
            get_files_tool = next(t for t in tools if t.name == "get_files_list")
            raw_path = await get_files_tool.ainvoke({})
            self.dashboard_config.csv_path = raw_path.strip()
            print(f"📁 File path cached in DashboardConfig: {self.dashboard_config.csv_path}")
        else:
            print(f"✅ Using cached file path: {self.dashboard_config.csv_path}")

    async def cache_schema(self, tools: List):
        """Cache schema from get_schema tool"""
        if not getattr(self.dashboard_config, "schema", None):
            get_schema_tool = next(t for t in tools if t.name == "get_schema")
            raw_schema = await get_schema_tool.ainvoke({
                "file_location": self.dashboard_config.csv_path
            })

            # Handle both str and list/dict return types
            if isinstance(raw_schema, str):
                items = json.loads(raw_schema)
            else:
                items = raw_schema

            # Build schema dict
            schema_dict = {}
            for obj in items:
                if isinstance(obj, str):
                    obj_data = json.loads(obj)
                else:
                    obj_data = obj
                schema_dict[obj_data["name"]] = obj_data["dtype"]

            self.dashboard_config.schema = schema_dict
            print(f"🧠 Schema cached in DashboardConfig: {list(self.dashboard_config.schema.keys())}")
        else:
            print(f"✅ Using cached schema: {list(self.dashboard_config.schema.keys())}")

class SchemaAnalyzer:
    """Handles schema analysis and metric generation"""

    def __init__(self, config: DashboardConfig):
        self.config = config
        self.llm = ChatGroq(
            model=config.model_id,
            api_key=config.api_key,
            max_tokens='15000'
        )


    async def analyze_schema(self, schema_data: List[Dict], question: str) -> Dict:
        """Analyze schema and generate metrics specification"""
        llm_payload = {
            "schema": schema_data,
            "question": question
        }

        response = await self.llm.ainvoke([
            {"role": "system", "content": DashboardConfig.INSTRUCTIONS_CSV_ANALYSIS},
            {"role": "user", "content": json.dumps(llm_payload, ensure_ascii=False)}
        ])

        if not hasattr(response, "content") or not response.content:
            raise RuntimeError("LLM returned empty content for schema analysis.")

        try:
            spec = json.loads(response.content)
        except json.JSONDecodeError as e:
            logger.error(f"LLM response not valid JSON: {response.content[:300]}...")
            raise ValueError(f"Failed to parse analysis JSON: {e}")

        # Validate required keys
        for key in ("key_metrics", "dashboard_components"):
            if key not in spec:
                raise ValueError(f"Analysis JSON missing required key: {key}")

        return {
            "key_metrics": spec.get("key_metrics", []),
            "dashboard_components": spec.get("dashboard_components")
        }


class SQLExecutor:
    """Executes SQL queries against CSV data"""

    def __init__(self, tools: List):
        self.exec_tool = next(t for t in tools if t.name == "execute_polars_sql")
        logger.info(f"SQL Executor initialized with tool: {self.exec_tool.name}")

    async def execute_metrics(self, metrics: List[Dict], csv_path: str) -> List[Dict]:
        """Execute SQL queries for all metrics"""
        results = []

        for metric in metrics:
            logger.info(f"Executing query: {metric['sql']}")

            data = await self.exec_tool.ainvoke({
                "file_locations": [csv_path],
                "query": metric["sql"],
                "file_type": "csv"
            })

            results.append({
                "metric": metric["metric"],
                "description": metric["description"],
                "visualization_type": metric["visualization_type"],
                "data": data or []
            })

        return results


class HTMLRenderer:
    """Renders dashboard HTML from data"""

    def __init__(self, config: DashboardConfig):
        self.config = config
        self.llm = ChatGroq(
            model=config.model_id,
            api_key=config.api_key
        )

    async def render_dashboard(self, metrics_data: List[Dict]) -> str:
        """Generate HTML dashboard from metrics data"""
        response = await self.llm.ainvoke([
            {"role": "system", "content": DashboardConfig.INSTRUCTIONS_RENDER_HTML},
            {"role": "user", "content": json.dumps({"metrics": metrics_data})}
        ])

        return response.content


class PipelineNodes:
    """Pipeline node implementations"""

    def __init__(self, config: DashboardConfig):
        self.config = config
        self.schema_analyzer = SchemaAnalyzer(config)

    async def node_schema(self, state: PipelineState) -> PipelineState:
        """Extract and analyze schema"""
        try:
            tools = state['tool']
            get_schema = next((t for t in tools if t.name == "get_schema"), None)

            if get_schema is None:
                raise RuntimeError("get_schema tool not found")

            logger.info(f"CSV path: {state.get('csv_file_path')}")

            # Get schema from tool
            schema_raw = await get_schema.ainvoke({
                "file_location": state["csv_file_path"],
                "file_type": "csv"
            })

            logger.info(f"✅ Schema retrieved: {schema_raw}")

            # Parse schema
            schema_list = [
                (json.loads(item) if isinstance(item, str) else item)
                for item in schema_raw
            ]

            if not schema_list:
                raise ValueError("Empty schema returned")

            # Analyze schema with LLM
            user_question = state['messages'][-1].content
            logger.info(f"User question: {user_question}")

            spec = await self.schema_analyzer.analyze_schema(schema_list, user_question)

            return {
                "messages": [AIMessage(content=json.dumps(spec, ensure_ascii=False))]
            }

        except Exception as e:
            logger.error(f"node_schema failed: {e}")
            return {
                "error": "node_schema_failed",
                "details": str(e)
            }

    async def node_execute_sql(self, state: PipelineState) -> PipelineState:
        """Execute SQL queries for metrics"""
        tools = state['tool']
        executor = SQLExecutor(tools)

        # Parse previous message
        messages = state['messages'][-1]
        try:
            payload = json.loads(messages.content)
        except Exception as e:
            raise ValueError(f"Failed to parse AIMessage content as JSON: {e}")

        key_metrics = payload.get("key_metrics", [])
        logger.info(f"Executing {len(key_metrics)} metrics")

        results = await executor.execute_metrics(key_metrics, state['csv_file_path'])

        return {'messages': [AIMessage(content=results)]}

    async def node_render_html(self, state: PipelineState) -> PipelineState:
        """Render HTML dashboard"""
        messages = state['messages'][-1]
        metrics_data = messages.content

        renderer = HTMLRenderer(self.config)
        html = await renderer.render_dashboard(metrics_data)

        return {"messages": [AIMessage(content=html)]}


class DashboardPipelineBuilder:
    """Builds the dashboard pipeline graph"""

    def __init__(self, config: DashboardConfig):
        self.config = config
        self.nodes = PipelineNodes(config)

    def build(self) -> StateGraph:
        """Build and compile the pipeline graph"""
        graph = StateGraph(PipelineState)

        graph.add_node("schema", self.nodes.node_schema)
        graph.add_node("execute_sql", self.nodes.node_execute_sql)
        graph.add_node("render_html", self.nodes.node_render_html)

        graph.add_edge("schema", "execute_sql")
        graph.add_edge("execute_sql", "render_html")
        graph.add_edge("render_html", END)

        graph.set_entry_point("schema")

        return graph.compile()




class DashboardAgent:
    """Main Dashboard Agent orchestrator"""

    def __init__(self):
        self.config = DashboardConfig()
        self.file_cache = FileCache(self.config)
        self.auth_manager = AuthenticationManager(self.config)
        self.pipeline_builder = DashboardPipelineBuilder(self.config)

    async def run_stream(self, messages: str):
        """Main execution method with STREAMING - yields chunks"""
        start_time = time.time()

        bearer_token = self.auth_manager.get_bearer_token()

        headers = {
            "authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }

        print("🔗 Attempting streaming connection to MCP server...")

        async with streamablehttp_client(self.config.mcp_url, headers, timeout=120) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                tools_by_server = await load_mcp_tools(session)
                await self.file_cache.cache_file_path(tools_by_server)


                elapsed = time.time() - start_time
                logger.info(f"⏱ Tools loaded in {elapsed:.2f} seconds")

                # Build pipeline
                pipeline = self.pipeline_builder.build()
                messages = [HumanMessage(content=messages)]

                # Initialize state
                init_state = {
                    "messages": messages,
                    "tool": tools_by_server,
                    "csv_file_path": self.config.csv_path,
                }

                # Run pipeline
                result = await pipeline.ainvoke(init_state)

                total_time = time.time() - start_time
                logger.info(f"✅ Dashboard generated in {total_time:.2f} seconds")

                return result


# ============================================
# MAIN ENTRY POINT
# ============================================
# ============================================
# FINAL ENTRYPOINT FOR SYNCHRONOUS RETURN
@app.entrypoint
def agent_invocation(payload, context):
    """
    Bedrock Agent entrypoint - Executes LangGraph synchronously and
    returns the final response dictionary.
    """
    # 1. Extract question from payload
    question = payload['prompt']
    print(f"🔔 Received prompt: {question}")

    # 2. Initialize the agent (assuming CSVAnalysisAgent() is now defined elsewhere)
    agent = DashboardAgent()

    # 3. Setup synchronous execution loop
    # We must use run_until_complete because LangGraph's run is typically async
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # The agent.run_stream method must be called via run_until_complete
        # We assume agent.run_stream(question) returns the final result when complete.
        result = loop.run_until_complete(agent.run_stream(question))

        # Extract the final message content from the result structure
        final_message = result.get('messages', [])[-1].content if result.get('messages') else "Analysis complete."

        print(f"\nAgent Response: {final_message}")

        # 4. Return the final result payload
        return {"result": final_message}

    except Exception as e:
        print(f"❌ Pipeline execution failed: {e}")
        # Return a standard error response
        return {"result": f"Error executing analysis pipeline: {str(e)}"}

    finally:
        loop.close()


if __name__ == "__main__":
    app.run()