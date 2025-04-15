from apm_mcp_server.rag_chroma.core import RAGManager
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("agile_practice_map")

load_dotenv()

@mcp.tool()
def query_apm(question):
    """
    Agile Practice Map（アジャイルプラクティスマップ）に関する質問に答える関数。

    引数:
    question -- ユーザーからの質問
    戻り値:
    質問に対する回答の文字列
    """
    # RAGマネージャーから回答を取得
    answer, _ = RAGManager.get_instance().query(question)
    return answer

@mcp.tool()
def list_apm_practices():
    """
    Agile Practice Map（アジャイルプラクティスマップ）のプラクティス一覧を取得する関数。
    
    戻り値:
    プラクティス名の一覧（リスト）
    """
    practices = RAGManager.get_instance().get_practices()
    return practices

def main():
    # RAGシステムを初期化
    if not RAGManager.get_instance().initialize():
        print("警告: RAGシステムの初期化に失敗しました。")
  
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
