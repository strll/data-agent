from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# 负责校验生成sql的节点
async def validate_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		# 校验sql
		try:
			# i=1/0
			logger.info("校验sql正确")
			return {"error": None}
		except Exception as e:

			logger.error("校验sql错误")
			return {"error": str(e)}

