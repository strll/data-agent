import asyncio

from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# 负责定义校正sql信息的节点
async def correct_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):



		writer=runtime.stream_writer
		writer({"state":"校正sql信息"})


		pass