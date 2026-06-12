from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


# 负责定义过滤表信息的节点

async def filter_table(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    try:
        writer = runtime.stream_writer
        writer({"state": "过滤表信息"})

        # 1.获取状态中的信息

        query = state["query"]

        table_infos = state["table_infos"]

        # 对接llm过滤无关的信息

        prompt = PromptTemplate(template=load_prompt("filter_table_info"), input_variables=["query", "table_infos"])

        output_parser = JsonOutputParser()

        chain = prompt | llm | output_parser


        result = await chain.ainvoke({"query": query, "table_infos": table_infos})

        for table_info in table_infos[:]:
            table_name = table_info["name"]
            if table_name not in result:
                table_infos.remove(table_info)
            else:
                for column in table_info["columns"][:]:
                    if column["name"] not in result[table_name]:
                        table_info["columns"].remove(column)

        logger.info(f"过滤后的表信息{[table_info["name"] for table_info in table_infos]}")

        return {"table_infos": table_infos}
    except Exception as e:
        logger.error(f"过滤表信息异常：{str(e)}")
        raise
