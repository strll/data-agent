import asyncio
import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


# 负责定义校正sql信息的节点
async def correct_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    try:
        # 1. 控制重试次数
        retry_count = state.get("retry_count", 0)
        if retry_count >= 3:
            logger.warning("SQL修复已达到最大重试次数 (3次)，退出循环")
            return {"sql": state.get("error_sql", "")}

        writer = runtime.stream_writer
        writer({"state": f"校正sql信息 (第 {retry_count + 1} 次尝试)"})

        # 2. 获取所有的错误历史和SQL历史
        error_history = state.get("error_history", [])
        sql_history = state.get("sql_history", [])

        current_error = state.get("error")
        current_sql = state.get("error_sql")

        if current_error and current_error not in error_history:
            error_history.append(current_error)
        if current_sql and current_sql not in sql_history:
            sql_history.append(current_sql)

        # 3. 【核心修改】将两个列表拼接为你想要的格式文本
        history_info = ""
        # 使用 zip 将 sql 和 error 一一对应拼接
        for i, (past_sql, past_error) in enumerate(zip(sql_history, error_history)):
            history_info += f"第 {i + 1} 次生成的sql是:\n{past_sql}\n产生的错误信息是:\n{past_error}\n\n"

        # 获取所需要的数据
        query = state["query"]
        table_infos = state["table_infos"]
        metric_infos = state["metric_infos"]
        db_info = state["db_info"]
        date_info = state["date_info"]

        # 对接llm生成sql，将之前两个历史变量替换为统一的 history_info
        prompt = PromptTemplate(template=load_prompt("correct_sql"),
                                input_variables=["query",
                                                 "table_infos",
                                                 "metric_infos",
                                                 "db_info",
                                                 "date_info",
                                                 "history_info"  # <--- 替换在这里
                                                 ])

        out_put_parser = StrOutputParser()
        chain = prompt | llm | out_put_parser

        # 准备统一的输入参数字典
        invoke_inputs = {
            "query": query,
            "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False),
            "metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False),
            "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False),
            "date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
            "history_info": history_info  # <--- 传入拼接好的字符串，不再用 yaml.dump
        }

        # 打印完整提示词
        formatted_prompt = prompt.format(**invoke_inputs)
        # logger.info(
        #     f"========== 第 {retry_count + 1} 次请求，发送给大模型的完整提示词 ==========\n{formatted_prompt}\n============================================================================")

        # 【优化】直接将准备好的 invoke_inputs 传给大模型，避免重复写字典
        sql = await chain.ainvoke(invoke_inputs)

        logger.info(f"第 {retry_count + 1} 次修复的sql为: \n {sql}")

        # 返回时更新重试次数，并将最新的 SQL 加入历史记录
        return {
            "sql": sql,
            "retry_count": retry_count + 1,
            "sql_history": sql_history,
            "error_history": error_history
        }

    except Exception as e:
        logger.error(f"修复的sql出现异常 {str(e)}")
        raise