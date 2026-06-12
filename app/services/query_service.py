import json
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.repossitories.es.ValueEsRepository import ValueEsRepository
from app.repossitories.mysql.dw_mysql_repository import DwMysqlRepository
from app.repossitories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repossitories.qdrant.column_qdrant_repository import *
from app.repossitories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class QueryService:
    def __init__(self,
                 embedding_client:HuggingFaceEndpointEmbeddings,
                 column_qdrant_repository:ColumnQdrantRepository,
                 value_es_repository:ValueEsRepository,
                 metric_qdrant_repository:MetricQdrantRepository,
                 meta_mysql_repository:MetaMysqlRepository,
                 dw_mysql_repository:DwMysqlRepository):

        self.embedding_client = embedding_client
        self.column_qdrant_repository = column_qdrant_repository
        self.value_es_repository = value_es_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository

    async def query(self, query:str):
        """
        用户查询的业务处理
        :param query:
        :return:
        """
        # 创建上下文对象
        context = DataAgentContext(
            embedding_client=self.embedding_client,
            column_qdrant_repository=self.column_qdrant_repository,
            value_es_repository=self.value_es_repository,
            metric_qdrant_repository=self.metric_qdrant_repository,
            meta_mysql_repository=self.meta_mysql_repository,
            dw_mysql_repository=self.dw_mysql_repository
        )
        # 创建状态对象
        state = DataAgentState(query=query)
        try:
            # 调用图流式输出
            async for chunk in graph.astream(input=state, context=context, stream_mode="custom"):
                yield f"data: {json.dumps(chunk,ensure_ascii=False,default=str)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({"error":str(e)}, ensure_ascii=False, default=str)}\n\n"