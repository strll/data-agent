import os

os.environ["no_proxy"] = os.environ.get("no_proxy", "") + ",api.deepseek.com"

import asyncio
from datetime import datetime

from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, DateInfoState
from app.core.log import logger
from app.repossitories.mysql import dw_mysql_repository



# 负责定义添加额外上下文信息的节点
async def add_extra_context(state:DataAgentState,runtime:Runtime[DataAgentContext]):


	try:
		writer=runtime.stream_writer
		writer({"state":"添加额外上下文信息"})

		today=datetime.today()

		date=today.strftime("%Y年%m月%d日")
		#星期
		week=today.strftime("%A")
		#月份
		month=today.strftime("%B")
		#季度
		quarter=f"Q{(today.month-1)//3+1}"

		date_info_state=DateInfoState(date=date,
									  weekday=week,
									  quarter=quarter)

		dw_mysql_repository= runtime.context["dw_mysql_repository"]
		db_info=await dw_mysql_repository.get_db_info()
		logger.info(f"数据库信息:{db_info},数据信息是{date_info_state}  添加额外上下文信息成功")
		return {"date_info":date_info_state,"db_info":db_info}
	except Exception as e:
		logger.error(f"添加额外上下文信息异常：{str(e)}")
		pass






