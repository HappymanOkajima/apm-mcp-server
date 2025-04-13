import os
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document # format_docsの型ヒント用
from dotenv import load_dotenv
from typing import List, Dict, Any, Tuple, Optional # 型ヒント用

load_dotenv()

# --- 設定値 ---
DEFAULT_DB_PATH = "./data/chroma_db"
LLM_MODEL_NAME = "gpt-4o" # LLMモデル名を定数化
RETRIEVER_K = 3 # 取得するチャンク数を定数化

# --- ヘルパー関数 ---
def format_docs(docs: List[Document]) -> str:
    """取得したドキュメントリストを整形する関数"""
    return "\n\n".join(doc.page_content for doc in docs)

# --- RAGシステム初期化関数 ---
def initialize_rag_system(db_path: str = DEFAULT_DB_PATH,
                           embedding_model_name: str = "text-embedding-ada-002", # 使用する埋め込みモデルを指定可能に
                           llm_model_name: str = LLM_MODEL_NAME,
                           retriever_k: int = RETRIEVER_K
                           ) -> Optional[Dict[str, Any]]:
    """
    RAGシステムに必要なコンポーネントを初期化し、構築する。

    Args:
        db_path: ChromaDBの永続化ディレクトリパス。
        embedding_model_name: 使用するOpenAI埋め込みモデル名。
        llm_model_name: 使用するOpenAIチャットモデル名。
        retriever_k: 検索時に取得するチャンク数。

    Returns:
        初期化されたRAGチェーンと関連コンポーネントを含む辞書。
        エラー発生時は None を返す。
    """
    # 1. 環境変数チェック
    if "OPENAI_API_KEY" not in os.environ:
        return None

    # 2. 埋め込みモデル初期化
    try:
        embeddings = OpenAIEmbeddings(model=embedding_model_name)
    except Exception as e:
        return None

    # 3. ChromaDB接続
    if not os.path.exists(db_path):
        return None
    try:
        vectorstore = Chroma(
            persist_directory=db_path,
            embedding_function=embeddings
        )
        db_count = vectorstore._collection.count()
        if db_count == 0:
             pass
    except Exception as e:
        return None

    # 4. リトリーバー作成
    retriever = vectorstore.as_retriever(search_kwargs={"k": retriever_k})

    # 5. LLM初期化
    try:
        llm = ChatOpenAI(model_name=llm_model_name, temperature=0)
    except Exception as e:
        return None

    # 6. プロンプトテンプレート定義
    template = """
以下の提供されたコンテキスト情報だけを使って、質問に答えてください。
コンテキスト外の情報や、あなたの一般的な知識は使用しないでください。
ただし、質問の意図を読み取って、適宜質問を読み替えてください。
もしコンテキストに答えが含まれていない場合は、「回答が見つかりませんでした。https://www.agile-studio.jp/agile-practice-map を読んでみてください。」と正直に答えてください。

コンテキスト:
{context}

質問: {question}

回答:"""
    prompt = ChatPromptTemplate.from_template(template)

    # 7. RAGチェーン構築
    rag_chain = (
        RunnableParallel( # retrieverとquestionを並行処理
            context=(retriever | format_docs),
            question=RunnablePassthrough()
        )
        | prompt
        | llm
        | StrOutputParser()
    )

    return {
        "chain": rag_chain,
        "retriever": retriever,
        "prompt": prompt,
        "llm": llm # 他の用途で使うかもしれないので返す
    }

# --- 質問応答関数 ---
def ask_question(rag_components: Dict[str, Any],
                 question: str,
                 debug: bool = False
                 ) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    初期化されたRAGシステムを使用して質問に回答する。

    Args:
        rag_components: initialize_rag_system() が返した辞書。
        question: ユーザーからの質問文字列。
        debug: デバッグ情報を表示/返すかどうか。

    Returns:
        回答文字列と、デバッグ情報を含む辞書（debug=Trueの場合）。
        エラー時は ("エラーが発生しました。", debug_info) のようなタプルを返す可能性あり。
    """
    if not rag_components:
        return "エラー: RAGシステムが初期化されていません。", None

    chain = rag_components.get("chain")
    retriever = rag_components.get("retriever")
    prompt = rag_components.get("prompt")

    if not chain or not retriever or not prompt:
         return "エラー: RAGコンポーネントが不足しています。", None

    debug_info = {}

    if debug:
        try:
            # 1. ドキュメント検索
            retrieved_docs = retriever.invoke(question)
            debug_info["retrieved_docs"] = retrieved_docs
            if retrieved_docs:
                 for i, doc in enumerate(retrieved_docs):
                    source = doc.metadata.get('source', '不明')
            else:
                pass

            # 2. コンテキスト整形
            context_text = format_docs(retrieved_docs)
            debug_info["context_text"] = context_text

            # 3. プロンプト入力データ
            prompt_input_data = {"context": context_text, "question": question}
            debug_info["prompt_input_data"] = prompt_input_data

            # 4. 最終プロンプト
            final_prompt_object = prompt.invoke(prompt_input_data)
            final_prompt_string = final_prompt_object.to_string()
            debug_info["final_prompt_string"] = final_prompt_string

        except Exception as e:
            debug_info["error"] = str(e)
        finally:
             pass

    # 回答生成
    try:
        answer = chain.invoke(question)
        return answer, (debug_info if debug else None)
    except Exception as e:
        return f"エラーが発生しました: {e}", (debug_info if debug else None)


# --- メイン実行部分 ---
if __name__ == "__main__":
    # RAGシステムの初期化
    rag_components = initialize_rag_system()

    if rag_components:
        while True:
            try:
                user_question = input("\n質問を入力してください: ")
                if user_question.lower() == 'exit':
                    break
                if not user_question:
                    continue

                # 質問応答関数を呼び出す (デバッグモードはTrueにする)
                answer, debug_data = ask_question(rag_components, user_question, debug=True)
                print(answer)  # 回答を表示

            except Exception as e:
                pass