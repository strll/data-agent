

from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# 负责定义合并召回信息的节点

async def merge_retrieved_info(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		pass