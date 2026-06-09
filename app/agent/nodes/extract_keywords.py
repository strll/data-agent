from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# 负责定义关键词抽取的节点
#提取关键字的节点
async def extract_keywords(state:DataAgentState,runtime:Runtime[DataAgentContext]):


		writer=runtime.stream_writer
		writer({"state":"正在提取关键词"})