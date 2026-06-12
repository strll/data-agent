import asyncio

from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.repossitories.mysql import dw_mysql_repository


# 负责定义执行sql信息的节点
async def execute_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"state": "执行sql"})

    # 获取sql

    dw_mysql_repository = runtime.context["dw_mysql_repository"]
    sql = state["sql"]

    # 执行sql
    result =await dw_mysql_repository.execute_sql(sql)

    # 响应结果

    writer({"state": "sql执行完成"})

    # writer({"state": f"生成的sql为\n{sql}\n查询的结果为:{result}"})

    # writer({"result": result})

    return {"result": result}