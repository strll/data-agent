from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# 负责定义召回字段信息的节点
async def recall_column(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		pass