from typing import TypedDict

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.repossitories.es.ValueEsRepository import ValueEsRepository
from app.repossitories.mysql.dw_mysql_repository import DwMysqlRepository
from app.repossitories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repossitories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repossitories.qdrant.metric_qdrant_repository import MetricQdrantRepository


# 定义RuntimeContext模块
class DataAgentContext(TypedDict):

        embedding_client: HuggingFaceEndpointEmbeddings
        column_qdrant_repository: ColumnQdrantRepository
        metric_qdrant_repository: MetricQdrantRepository

        value_es_repository: ValueEsRepository
        meta_mysql_repository: MetaMysqlRepository
        dw_mysql_repository: DwMysqlRepository