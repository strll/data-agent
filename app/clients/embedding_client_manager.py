import os

os.environ["NO_PROXY"] = "localhost,127.0.0.1,0.0.0.0"
os.environ["no_proxy"] = "localhost,127.0.0.1,0.0.0.0"

import asyncio
from typing import Optional

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from conf.app_config import app_config, EmbeddingConfig
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from huggingface_hub import InferenceClient, AsyncInferenceClient
class EmbeddingClientManager:
    def __init__(self, config: EmbeddingConfig):
        self.embedding_client: Optional[HuggingFaceEndpointEmbeddings] = None
        self.config = config

    def init(self):
        # self.client=HuggingFaceEndpointEmbeddings(
        #
        #     model=self._get_url(),
        #
        # )

        self.client = HuggingFaceEndpointEmbeddings(
            model="sentence-transformers/all-MiniLM-L6-v2"
        )

        local_url = self._get_url()
        self.client.client = InferenceClient(model=local_url)
        self.client.async_client = AsyncInferenceClient(model=local_url)


    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"

embedding_client_managert=EmbeddingClientManager(app_config.embedding)

if __name__ == '__main__':
    embedding_client_managert.init()
    async def test():
        text="你好 我爱中国"
        client=embedding_client_managert.client

        result=await client.aembed_query( text)

        print( result)

    asyncio.run(test())