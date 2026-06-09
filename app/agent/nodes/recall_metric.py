from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# 负责定义召回取值信息的节点
async def recall_metric(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		pass