from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# 负责定义添加额外上下文信息的节点
async def add_extra_context(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		pass