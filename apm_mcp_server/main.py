from .rag_chroma.core import initialize_rag_system, ask_question
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("agile_practice_map")

load_dotenv()

# グローバル変数としてRAGコンポーネントを保持
rag_components = None

def initialize_rag():
    """RAGシステムを初期化する関数"""
    global rag_components
    if rag_components is None:
        rag_components = initialize_rag_system()
    return rag_components

@mcp.tool()
def apm_query(question):
    """
    Agile Practice Map（アジャイルプラクティスマップ）に関する質問に答える関数。

    引数:
    question -- ユーザーからの質問
    戻り値:
    質問に対する回答の文字列
    """
    # print(f"質問を処理中: {question}")
    
    # RAGシステムの初期化確認
    global rag_components
    if rag_components is None:
        rag_components = initialize_rag()
        if not rag_components:
            return "エラー: RAGシステムの初期化に失敗しました。"
    
    # 質問処理と回答生成
    answer, _ = ask_question(rag_components, question, debug=False)
    # print(f"回答を生成しました: {answer[:100]}..." if len(answer) > 100 else f"回答を生成しました: {answer}")
    
    return answer

def main():
    
    # RAGシステムを初期化
    initialize_rag()
    # print("Agile Practice Map MCP SERVER starting up...")
  
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()