import asyncio
import os
import time
import json

from textwrap import dedent
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import requests
from dotenv import load_dotenv
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
from langchain_groq import ChatGroq
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.errors import GraphRecursionError
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langgraph.graph.message import add_messages
from typing import Annotated
from bedrock_agentcore.runtime import BedrockAgentCoreApp
import asyncio
import queue
import threading
from typing import Generator
app = BedrockAgentCoreApp()
load_dotenv()


@dataclass
class MessagesState:
    """State container for agent messages"""
    messages: Annotated[List[BaseMessage], add_messages]


class CSVAnalysisConfig:
    """Configuration management for CSV Analysis Agent"""

    INSTRUCTIONS = dedent("""
You are an intelligent **CSV Data Analyst Agent** with access to the following MCP tools:
- get_files_list: List available CSV files.
- read_file / read_file_list: Read a CSV file or list of files (≤100 rows for sampling).
- get_schema: Return column names and data types of a CSV file.
- execute_polars_sql: Execute a **single atomic Polars SQL query** on one or more CSVs with the same schema. Use `self` as the table name.
 2. **IMPORTANT PRE-CHECK**:
   - If there are **no files available** (`get_files_list` returns empty) **or** the schema (`get_schema`) is empty, you must **immediately respond with**:
     "**No file is present and there is nothing to analyze.**"
   - Under these conditions, you **must not attempt any queries** or further analysis. This is a strict rule — the agent should stop execution and return this message immediately.
🚨 **CRITICAL TOOL USAGE RULES**:

**execute_polars_sql** - MUST follow this exact format:
{
"file_locations": ["/exact/path/to/file.csv"],
"query": "SELECT column_name FROM self WHERE condition"
}

*– No extra keys allowed.

**POLARS SQL SYNTAX RULES**:
1. Table name is always `self`.
2. Column names must match schema **exactly** (case-sensitive).
3. Use `AS alias_name` for all derived tables (mandatory).
4. **No subqueries** in SELECT, WHERE, or HAVING; use **WITH CTEs** only.
5. For UNION ALL, ensure identical column names with `AS` aliases.
   - ✅ `SELECT team1 AS team FROM self UNION ALL SELECT team2 AS team FROM self`
   - ❌ `SELECT team1, team2 UNION SELECT team2, team1`

**BEFORE WRITING SQL**:
- Inspect schema context for available columns.
- Validate column names match schema exactly.
- Plan a single CTE-based query; test logic mentally.
- Add aliases to every CTE and derived table.

**COMMON MISTAKES & FIXES**:
- ❌ Using `FROM (SELECT …)`
- ✅ Use `WITH temp AS (SELECT …) SELECT * FROM temp`
- ❌ `HAVING count = (SELECT COUNT(*) FROM …)`
- ✅ Use CTE: `WITH total AS (SELECT COUNT(*) AS cnt FROM …) … HAVING COUNT(*) = total.cnt`

🧠 ROLE & THINKING:
- Think step-by-step like a data analyst.
- Reason internally; do not expose reasoning.
- Validate everything before executing any tool.

🧭 GOAL:
- Use tools only when necessary to answer precisely.
- Complete in ≤2 tool calls and ≤2 reasoning iterations.
- End with `END` immediately after providing the answer.

⚙️ WORKFLOW:
1. Understand user intent and question clearly and Effectively
2. Understand the Schema and choose the Best Column Don't choose the Column which is not present in schema
3. Use cached schema and file path context.
4. Decide if a tool call is needed; if yes, choose the minimal direct tool.
5. For SQL, write one perfect CTE-only query, then execute.
6. Format output and end with `END`.

🧱 RULES:
- Never modify or delete files.
- Always validate column names.
- Report missing columns/files clearly.
- Maximum 2 tool calls per question.
- Maximum 2 reasoning iterations.
- One flawless SQL query; no trial-and-error.

🧾 OUTPUT FORMAT (STRICT):
When responding, follow this exact structure — nothing more, nothing less.

---

📊 **Answer Summary**
A one-line concise summary of the main finding or insight.

---

📋 **Key Insights**
• 3–5 short bullet points summarizing patterns, comparisons, or important metrics.
• Keep each bullet factual and insight-driven — no reasoning or speculation.

---

📈 **Table Output (if applicable)**
If the result involves tabular data:
- Present it as a clean Markdown table.
- Include only relevant columns and ≤10 rows for readability.
- Do NOT include raw JSON or Pandas/Polars printouts.

Example:
| Team | Runs | Matches |
|------|-------|----------|
| MI   | 1800  | 10       |
| CSK  | 1750  | 10       |

---

🚀 **Next Step Suggestion**
End with a helpful next-step prompt (e.g.,
“Would you like me to plot this trend over time?”
or
“Shall I drill down by category?”)

---

💡 RULES:
- Never output reasoning or raw tool responses.
- Use **Markdown formatting** only (no HTML, JSON, or LaTeX unless explicitly asked).
- Always end with the word `END` on a new line after the full response.

✅ Example (Final Output):

📊 **Answer Summary**
Top 3 teams by average score.

📋 **Key Insights**
• MI leads with 180 average runs.
• CSK follows closely with 175.
• RCB trails with 165.

📈 **Table Output**
| Team | Avg Runs |
|------|-----------|
| MI   | 180 |
| CSK  | 175 |
| RCB  | 165 |

🚀 **Next Step Suggestion**
Would you like a year-over-year trend chart for these averages?

⚡ MINDSET:
- Be authoritative, concise, and efficient.
- **VALIDATE BEFORE EXECUTE** — avoid all tool failures.
- Write perfect SQL on the first try.
- Finish decisively.
""")

    def __init__(self):
        self.agent_arn = os.getenv('AGENT_ARN')
        self.region = os.getenv('REGION')
        self.discovery_url = os.getenv('DISCOVERY_URL')
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.model_id = os.getenv("MODEL_ID", "openai/gpt-oss-20b")
        self.api_key = os.getenv("GROQ_API_KEY")

        self._validate_config()
        self.mcp_url = self._construct_mcp_url()

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

    def __init__(self, config: CSVAnalysisConfig):
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


class AgentOptimizer:
    """Optimizes agent execution with caching and routing"""

    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self._cached_file_path: str = ""
        self._cached_schema: Dict[str, str] = {}

    def create_optimized_pre_model_hook(self):
        """Inject cached context without altering existing messages"""
        def pre_model_hook(state: MessagesState) -> Dict[str, Any]:
            msgs = state.messages
            context_parts = []

            if self._cached_file_path:
                context_parts.append(f"Data file: {self._cached_file_path}")
            if self._cached_schema:
                cols = ", ".join(self._cached_schema.keys())
                context_parts.append(f"Columns: {cols}")

            if context_parts:
                ctx = " | ".join(context_parts)
                new_messages = [SystemMessage(content=f"CONTEXT: {ctx}")] + msgs
            else:
                new_messages = msgs

            return {"llm_input_messages": new_messages}

        return pre_model_hook

    def create_smart_router(self):
        """Enhanced router with early termination conditions"""
        def router_function(state: MessagesState):
            messages = state.messages

            if not messages:
                return END

            last_msg = messages[-1]

            if isinstance(last_msg, dict):
                content = last_msg.get("content", "")
            else:
                content = getattr(last_msg, "content", "")

            if not content:
                return END

            stop_conditions = [
                content.strip().endswith("END"),
                len(messages) > 6,
                "final answer" in content.lower(),
                "complete" in content.lower(),
                "done" in content.lower(),
                "finished" in content.lower()
            ]

            if any(stop_conditions):
                return END

            return "reason"

        return router_function


class SchemaCache:
    """Manages file path and schema caching"""

    def __init__(self, optimizer: AgentOptimizer):
        self.optimizer = optimizer

    async def cache_file_path(self, tools: List):
        """Cache file path from get_files_list tool"""
        if not self.optimizer._cached_file_path:
            get_files_tool = next(t for t in tools if t.name == "get_files_list")
            raw_path = await get_files_tool.ainvoke({})
            self.optimizer._cached_file_path = raw_path.strip()
            print(f"File path cached: {self.optimizer._cached_file_path}")

    async def cache_schema(self, tools: List):
        """Cache schema from get_schema tool"""



        # Check if file path is valid
        if not self.optimizer._cached_file_path:
            print("⚠️ No file path provided — schema cache is empty.")
            self.optimizer._cached_schema = {}
            return # mark as empty


        if not self.optimizer._cached_schema:
            get_schema_tool = next(t for t in tools if t.name == "get_schema")
            raw_schema = await get_schema_tool.ainvoke({
                "file_location": self.optimizer._cached_file_path
            })

            if isinstance(raw_schema, str):
                items = json.loads(raw_schema)
            else:
                items = raw_schema

            for obj in items:
                if isinstance(obj, str):
                    obj_data = json.loads(obj)
                else:
                    obj_data = obj
                self.optimizer._cached_schema[obj_data["name"]] = obj_data["dtype"]

            print(f"Schema cached: {list(self.optimizer._cached_schema.keys())}")


class WorkflowBuilder:
    """Builds and compiles the agent workflow"""

    def __init__(self, config: CSVAnalysisConfig, optimizer: AgentOptimizer):
        self.config = config
        self.optimizer = optimizer
        self.memory = MemorySaver()

    def create_llm(self):
        """Create ChatGroq LLM instance"""
        return ChatGroq(
            model=self.config.model_id,
            api_key=self.config.api_key,
            temperature=0,
        )

    def build_workflow(self, llm, tools: List):
        """Build the complete workflow graph"""
        react_agent = create_react_agent(
            llm,
            tools=tools,
            prompt=CSVAnalysisConfig.INSTRUCTIONS,
            checkpointer=self.memory,
            pre_model_hook=self.optimizer.create_optimized_pre_model_hook()
        )

        workflow = StateGraph(MessagesState)
        workflow.add_node("reason", react_agent)
        workflow.add_edge(START, "reason")
        workflow.add_conditional_edges(
            "reason",
            self.optimizer.create_smart_router(),
            {"reason": "reason", END: END}
        )

        return workflow.compile(
            checkpointer=self.memory,
            interrupt_before=[]
        )


class AgentExecutor:
    """Executes the agent workflow with STREAMING support"""

    def __init__(self, app, recursion_limit: int = 3):
        self.app = app
        self.recursion_limit = recursion_limit

    async def execute(self, message: str, thread_id: str = "1"):
        """Execute the agent workflow fully and return last message"""
        config = {"configurable": {"thread_id": thread_id}}
        messages = [HumanMessage(content=message)]

        start_time_run = time.perf_counter()
        init_state = MessagesState(messages=messages)

        try:
            print("\n🚀 Starting full invoke...\n")
            result = await self.app.ainvoke(init_state, config=config)
            elapsed_run = time.perf_counter() - start_time_run
            print(f"\n✅ Agent completed in {elapsed_run:.2f} seconds")

            # Return last message text
            if "messages" in result and len(result["messages"]) > 0:
                last_msg = result["messages"][-1]
                if hasattr(last_msg, "content"):
                    return last_msg.content

            return "⚠️ No output returned."

        except GraphRecursionError:
            print("⚠️ Recursion limit hit — returning partial result.")
            return "Partial result due to recursion limit."
        except Exception as e:
            print(f"❌ AgentExecutor.execute failed: {e}")
            return f"Error: {str(e)}"


class CSVAnalysisAgent:
    """Main CSV Analysis Agent class with STREAMING support"""

    def __init__(self, user_id: str = "default_user"):
        self.config = CSVAnalysisConfig()
        self.auth_manager = AuthenticationManager(self.config)
        self.optimizer = AgentOptimizer(user_id)
        self.schema_cache = SchemaCache(self.optimizer)
        self.workflow_builder = WorkflowBuilder(self.config, self.optimizer)

    async def run(self, message: str):
        """Main execution method with STREAMING - yields chunks"""
        start_time = time.time()

        try:
            bearer_token = self.auth_manager.get_bearer_token()

            headers = {
                "authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json"
            }

            print("🔗 Attempting streaming connection to MCP server...")

            async with streamablehttp_client(self.config.mcp_url, headers, timeout=120) as (r, w, _):
                async with ClientSession(r, w) as session:
                    try:
                        await session.initialize()
                        tools_by_server = await load_mcp_tools(session)

                        print("------------------------------------------------")
                        print("✅ MCP CONNECTION AND HANDSHAKE SUCCESSFUL (JWT)! ✅")

                        print("Discovering tools...")
                        for tool in tools_by_server:
                            name = getattr(tool, "name", "<unknown>")
                            desc = (getattr(tool, "description", "") or "").strip()
                            print(f"- {name} :: {desc}")

                        await self.schema_cache.cache_file_path(tools_by_server)
                        await self.schema_cache.cache_schema(tools_by_server)

                        llm = self.workflow_builder.create_llm()
                        app = self.workflow_builder.build_workflow(llm, tools_by_server)

                        executor = AgentExecutor(app, recursion_limit=3)

                        # get the response
                        response = await executor.execute(message)

                        elapsed_total = time.time() - start_time
                        print(f"⏱ Total execution time: {elapsed_total:.2f} seconds")
                        return response

                    except Exception as e:
                        print(f"❌ Error during session workflow: {e}")
                        return f"Error during workflow: {str(e)}"

        except Exception as e:
            print(f"❌ Failed to connect or initialize MCP client: {e}")
            return f"Connection/Initialization error: {str(e)}"


# ============================================
# SIMPLE TEST WITHOUT BEDROCK
@app.entrypoint
def agent_invocation(payload, context):
    """
    Bedrock Agent simple entrypoint (non-streaming)
    For testing and debugging WITHOUT streaming logic.
    """
    print("🔔 Received payload:", payload)

    question = payload['prompt']
    if not question:
        return "⚠️ No prompt provided in payload."

    # Create your agent
    agent = CSVAnalysisAgent()

    # Run async -> sync bridge (no queue needed)
    async def async_invoke():
        return await agent.run(question)

    # Just run once
    try:
        result = asyncio.run(async_invoke())
        print("✅ Agent run completed successfully!")
        return result
    except Exception as e:
        print(f"❌ Agent run failed: {e}")
        return f"Error: {str(e)}"




if __name__ == "__main__":
    app.run()



