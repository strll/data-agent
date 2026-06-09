import asyncio
from pathlib import Path

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_clinet_manager import es_client_manager
from app.clients.mysql_client_manager import dw_mysql_client_manager, meta_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.core.log import logger
from argparse import ArgumentParser

from app.repossitories.es.ValueEsRepository import ValueEsRepository
from app.repossitories.mysql.dw_mysql_repository import DwMysqlRepository
from app.repossitories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repossitories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repossitories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.service.meta_konwledge_service import MetaKnowledgeService


async def build(file_path: Path):
    logger.info("build meat knowledge")

    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    qdrant_client_manager.init()
    embedding_client_manager.init()

    es_client_manager.init()

    # async with AsyncSession(bind=meta_mysql_client_manager.engine) as session:
    async with meta_mysql_client_manager.session_factory() as meta_session, dw_mysql_client_manager.session_factory() as dw_session:
        meta_mysql_repository = MetaMysqlRepository(meta_session)
        dw_mysql_repository = DwMysqlRepository(dw_session)
        column_qdrant_repository = ColumnQdrantRepository(qdrant_client_manager.client)
        value_es_repository = ValueEsRepository(es_client_manager.client)

        meta_qdrant_repository=MetricQdrantRepository(qdrant_client_manager.client)

        meta_konwledge_service = MetaKnowledgeService(meta_mysql_repository=meta_mysql_repository,
                                                      dw_mysql_repository=dw_mysql_repository,
                                                      column_qdrant_repository=column_qdrant_repository,
                                                      embedding_client=embedding_client_manager.client,
                                                      value_es_repository=value_es_repository,
                                                      meta_qdrant_repository=meta_qdrant_repository
                                                      )

        await meta_konwledge_service.build(file_path)

    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
    await qdrant_client_manager.close()
    await es_client_manager.close()
    await embedding_client_manager.close()


if __name__ == '__main__':
    # 创建一个命令行参数解析器对象
    parser = ArgumentParser(
        prog='data-age',  # 程序名称，在帮助信息中显示
        description='这是一个nl2sql的Rag架构的项目',  # 程序的简短描述
        epilog='需要严格按照文档进行使用'  # 帮助信息底部的附加文本
    )
    parser.add_argument('-c', '--config', dest='file_path', type=Path, required=True, help='配置文件的路径')

    # 修改2: 实际执行解析操作，获取命令行输入
    args = parser.parse_args()

    # 修改3: 将解析出来的 file_path 传入 build 函数
    asyncio.run(build(args.file_path))
