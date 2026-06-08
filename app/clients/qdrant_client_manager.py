import os
# 强制让 Python 在访问这些本地地址时不走代理
os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"

import asyncio
import random
from typing import Optional

from qdrant_client import qdrant_client, models

from qdrant_client import AsyncQdrantClient

from conf.app_config import QdrantConfig, app_config


class QdrantClinetManager:
    def __init__(self, config: QdrantConfig):
        self.client: Optional[AsyncQdrantClient] = None
        self.config = config

    def init(self):
        self.client = AsyncQdrantClient(url=self._get_url()
                                        )

    async def close(self):
        await self.client.close()

    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"


qdrant_client_manager = QdrantClinetManager(app_config.qdrant)

if __name__ == '__main__':
    qdrant_client_manager.init()
    client = qdrant_client_manager.client


    async def test():
        if not await client.collection_exists("my_collection"):
            await client.create_collection(collection_name="my_collection",
                                          vectors_config=models.VectorParams(size=app_config.qdrant.embedding_size,
                                                                             distance=models.Distance.COSINE)
                                          )

        # 2. 批量插入100个10维随机向量到集合中
        await client.upsert(
            collection_name="my_collection",
            # 列表推导式生成100个PointStruct对象（包含ID和随机向量）
            points=[
                models.PointStruct(
                    id=i,  # 向量唯一标识ID
                    vector=[random.random() for _ in range(app_config.qdrant.embedding_size)]  # 生成10维随机向量
                )
                for i in range(100)
            ],
        )

        # 3. 向量相似度检索：查找最相似的10个向量
        res = await client.query_points(
            collection_name="my_collection",  # 检索的集合名称
            query=[random.random() for _ in range(app_config.qdrant.embedding_size)],  # 10维随机查询向量（type: ignore忽略类型提示）
            limit=10,  # 返回最相似的前10个向量
            score_threshold=0.5  # 相似度得分阈值：只返回得分≥0.5的结果
        )
        # 打印检索结果中的向量点信息（包含ID、向量、得分等）
        print(res.points)

    # 运行异步测试函数（asyncio.run是执行异步函数的标准方式）
    asyncio.run(test())