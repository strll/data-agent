from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# 负责校验生成sql的节点
async def validate_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		pass