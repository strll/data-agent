from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# 负责定义过滤指标信息的节点
async def filter_metric(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		pass