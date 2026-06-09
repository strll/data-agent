from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# 负责定义生成sql的节点
async def generate_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		writer=runtime.stream_writer
		writer({"state":"生成sql信息"})
