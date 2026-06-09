import asyncio

from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# 负责定义执行sql信息的节点
async def execute_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):


		writer=runtime.stream_writer
		writer({"state":"执行sql"})