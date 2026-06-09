from typing import TypedDict

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.repossitories.qdrant.column_qdrant_repository import ColumnQdrantRepository


# 定义RuntimeContext模块
class DataAgentContext(TypedDict):

        embedding_client: HuggingFaceEndpointEmbeddings
        column_qdrant_repository: ColumnQdrantRepository
