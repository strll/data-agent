from typing import Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# from qdrant_client.http.models import VectorParams
from sqlalchemy.dialects.oracle import vector

from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from conf.app_config import app_config


class ColumnQdrantRepository:
    collection_name: str = "data-agent-column"

    def __init__(self, client: AsyncQdrantClient):
        self.client: Optional[AsyncQdrantClient] = client

    async def ensure_collection(self):
        if not await self.client.collection_exists(self.collection_name):
            await self.client.create_collection(collection_name=self.collection_name,
                                                vectors_config=VectorParams(size=app_config.qdrant.embedding_size,
                                                                            distance=Distance.COSINE)
                                                )


    async def upsert_embeddings(self, ids: list[str], emdeddings: list[list[float]], paylods: ColumnInfoQdrant,batch_size:int=10  ):


        zipped = list(zip(ids, emdeddings, paylods))

        for i in range(0,len(zipped),batch_size):
            batch=zipped[i:i+batch_size]

            points = [PointStruct(
                id=id,
                vector=embedding,
                payload=payload
            ) for id, embedding, payload in batch]
            #保存批次数据

            await self.client.upsert(collection_name=self.collection_name,
                                 wait=True,
                                 points=points
                                 )


