from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.repossitories.mysql.dw_mysql_repository import DwMysqlRepository


# 负责校验生成sql的节点
async def validate_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		# 校验sql
		sql = state["sql"]
		try:
			# i=1/0
			write=runtime.stream_writer

			write({"state":"开始校验sql"})



			dw_mssql_repositrory:DwMysqlRepository=runtime.context["dw_mysql_repository"]

			await dw_mssql_repositrory.validate_sql(sql)





			logger.info("校验sql正确")





			return {"error": None}





		except Exception as e:

			logger.error("校验sql错误")
			return {"error": str(e),"error_sql":sql}

