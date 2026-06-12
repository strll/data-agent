import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


# 负责定义生成sql的节点
async def generate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    sql=""
    try:
        writer = runtime.stream_writer
        writer({"state": "生成sql信息"})

        # 获取所需要的数据
        query = state["query"]
        table_infos = state["table_infos"]
        metric_infos = state["metric_infos"]
        db_info = state["db_info"]
        date_info = state["date_info"]

        # 对接llm生成sql

        prompt = PromptTemplate(template=load_prompt("generate_sql"),
                                input_variables=["query",
                                                 "table_infos",
                                                 "metric_infos",
                                                 "db_info",
                                                 "date_info"])

        out_put_parser = StrOutputParser()

        chain = prompt | llm | out_put_parser

        sql = await chain.ainvoke({"query": query,
                                   "table_infos": yaml.dump(table_infos,
                                                            allow_unicode=True,
                                                            sort_keys=False,
                                                            ),
                                   "metric_infos": yaml.dump(metric_infos,
                                                             allow_unicode=True,
                                                             sort_keys=False,
                                                             ),
                                   "db_info": yaml.dump(db_info,
                                                        allow_unicode=True,
                                                        sort_keys=False,
                                                        ),
                                   "date_info": yaml.dump(date_info,
                                                          allow_unicode=True,
                                                          sort_keys=False,
                                                          ),

                                   })

        logger.info(f"生成的sql为{sql}")
        return {"sql": sql}
    except Exception as e:
        logger.error(f"生成sql异常{str(e)}")



        raise

