from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# 负责定义过滤表信息的节点

async def filter_table(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		writer=runtime.stream_writer
		writer({"state":"过滤表信息"})