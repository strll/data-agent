import asyncio
from unittest import main
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker

from conf.app_config import app_config, DBConfig
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

class MysqlClientManager:
    def __init__(self, config:DBConfig):

        self.config = config

        self.engine:Optional[AsyncEngine]= None

    def _get_url(self):
        return (f"mysql+aiomysql://{self.config.user}:{self.config.password}"
                f"@{self.config.host}:{self.config.port}/"
                f"{self.config.database}")


    def init(self):
        self.engine=create_async_engine(
            self._get_url(),
            pool_size=10,
            pool_pre_ping=True

        )

        self.session_factory=async_sessionmaker(
            bind=self.engine,
            autoflush=True,
            autobegin=True,
            expire_on_commit=False
        )


    async def close(self):
        await self.engine.dispose()

dw_mysql_client_manager=MysqlClientManager(app_config.db_dw)
meta_mysql_client_manager=MysqlClientManager(app_config.db_meta)

if __name__ == '__main__':
    dw_mysql_client_manager.init()
    async def test():

        async with AsyncSession(bind=dw_mysql_client_manager.engine) as session:
            sql=text("select * from fact_order limit 10")
            result=await session.execute(sql)

            fetchall = result.fetchall()
            print(fetchall)

        await dw_mysql_client_manager.close()
    asyncio.run(test())

