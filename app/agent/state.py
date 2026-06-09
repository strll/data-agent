from typing import TypedDict

# 定义state模块
class DataAgentState(TypedDict):
    error: str
    query: str
    keywords:list[str]