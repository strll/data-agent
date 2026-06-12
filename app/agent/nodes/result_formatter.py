from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt
from app.repossitories.mysql.dw_mysql_repository import DwMysqlRepository


async def result_formatter(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    # 校验sql
    try:

        writer = runtime.stream_writer
        writer({"state": "开始渲染结果"})
        sql_message = state.get("result")

        query = state["query"]

        prompt = PromptTemplate(template=load_prompt("prompt_templates"),
                                input_variables=["query", "sql_message"])

        output_parser = StrOutputParser()

        chain = prompt | llm | output_parser

        result = await chain.ainvoke({"query": query,
                                      "sql_message": str(sql_message)})

        writer({"result": result})

    except Exception as e:

        logger.error(f"渲染结果错误 报错是{ str(e)}")
        return {"error": str(e)}
