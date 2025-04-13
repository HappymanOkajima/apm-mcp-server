import os
import argparse
import re
import glob
from langchain_community.document_loaders import TextLoader, PlaywrightURLLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.docstore.document import Document
from typing import List, Optional
import hashlib # ID生成用にインポート
from dotenv import load_dotenv

load_dotenv()

# --- 定数定義 ---
DEFAULT_DB_PATH = "../data/chroma_db"
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_SPLIT_METHOD = "recursive" # 'recursive' or 'paragraph'

# 日本語文字クラス（クリーニング用）
JP_CHARS = r'\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF々〇〉》」』】〕〟＇｀．。，、？！：；＝ LINETAB'

def load_urls_from_file(file_path: str) -> List[str]:
    """指定されたファイルからURLリストを読み込む (1行1URL形式、#で始まる行は無視)"""
    urls = []
    print(f"URLリストファイル '{file_path}' を読み込み中...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url and not url.startswith('#'): # 空行とコメント行(#)を無視
                    urls.append(url)
        print(f"  {len(urls)} 個の有効なURLを読み込みました。")
    except FileNotFoundError:
        print(f"エラー: URLリストファイル '{file_path}' が見つかりません。")
    except Exception as e:
        print(f"エラー: URLリストファイル '{file_path}' の読み込み中にエラーが発生しました: {e}")
    return urls

def load_documents(input_dir: Optional[str], url_file: Optional[str]) -> List[Document]:
    """テキストファイルとWebページからドキュメントを読み込む (WebはPlaywrightを使用)"""
    all_docs: List[Document] = []

    # 1. テキストファイルの読み込み (input_dirが指定されている場合)
    if input_dir:
        if not os.path.isdir(input_dir):
            print(f"警告: 指定されたテキスト入力ディレクトリ '{input_dir}' が存在しません。スキップします。")
        else:
            print(f"テキストファイルディレクトリ '{input_dir}' を処理中...")
            txt_files = list(glob.iglob(os.path.join(input_dir, '**', '*.txt'), recursive=True))
            print(f"  {len(txt_files)} 個の .txt ファイルを検出しました。")
            loaded_count = 0
            for file_path in txt_files:
                try:
                    print(f"    ローディング: {file_path}")
                    loader = TextLoader(file_path, encoding='utf-8-sig') # BOM付きUTF-8考慮
                    loaded_docs = loader.load()
                    for doc in loaded_docs:
                        if not hasattr(doc, 'metadata'): doc.metadata = {}
                        if 'source' not in doc.metadata or not doc.metadata['source']:
                             doc.metadata['source'] = file_path
                    all_docs.extend(loaded_docs)
                    loaded_count += len(loaded_docs)
                except Exception as e:
                    print(f"    ファイル '{file_path}' のロード中にエラー: {e}")
            print(f"  テキストファイルからの読み込み完了。合計 {loaded_count} ドキュメントオブジェクト。")

    # 2. Webページの読み込み (url_fileが指定されている場合) - Playwrightを使用
    if url_file:
        if not os.path.isfile(url_file):
             print(f"警告: 指定されたURLリストファイル '{url_file}' が存在しません。スキップします。")
        else:
            print(f"URLリストファイル '{url_file}' を処理中...")
            urls = load_urls_from_file(url_file)
            if urls:
                print(f"  {len(urls)} 個のURLから Playwright を使用してWebページを読み込み中 (JavaScript実行)...")
                try:
                    # PlaywrightURLLoader を使用
                    # remove_selectors で不要なHTML要素をCSSセレクタで指定して読み込み前に削除可能
                    # 例: ヘッダー、フッター、ナビゲーション、スクリプト、スタイルシートなど
                    web_loader = PlaywrightURLLoader(
                        urls=urls,
                        remove_selectors=["header", "footer", "nav", "aside", "script", "style", ".sidebar", "#sidebar"], # 不要そうな要素を指定
                        continue_on_failure=True, # エラーが発生したURLはスキップして続行
                        # headless=True # デフォルトはTrue (バックグラウンドで実行)
                    )
                    # load() を実行すると内部で Playwright がブラウザを起動し、
                    # ページを読み込み、JavaScriptを実行し、指定された要素を削除した後、
                    # body内のテキストコンテンツを抽出します。
                    web_docs = web_loader.load()
                    print(f"  Webページからの読み込み完了 (Playwright)。{len(web_docs)} ドキュメント取得。")

                    # メタデータの確認と設定
                    for doc in web_docs:
                         if not hasattr(doc, 'metadata'): doc.metadata = {}
                         # PlaywrightURLLoaderは通常 'source' (URL) と 'title' をメタデータに設定する
                         if 'source' not in doc.metadata or not doc.metadata['source']:
                             # 万が一 source が設定されなかった場合のフォールバック
                             doc.metadata['source'] = "Unknown Web Source (Playwright)"
                         print(f"    Loaded: {doc.metadata.get('source')} (Title: {doc.metadata.get('title', 'N/A')})")

                    all_docs.extend(web_docs)
                except ImportError as ie:
                    print("\nエラー: Playwrightを使用したWebページの読み込みには 'playwright' ライブラリが必要です。")
                    print(f"詳細なエラー: {ie}")
                    print("1. pip install playwright")
                    print("2. playwright install (コマンドプロンプトやターミナルで実行)")
                    print("を実行してください。\n")
                except Exception as e:
                    print(f"  Playwrightを使用したWebページの読み込み中に予期せぬエラーが発生しました: {e}")
                    # Playwrightのタイムアウトエラーなどもここで捕捉される可能性あり
            else:
                print("  URLリストファイルから有効なURLが読み込めませんでした。")

    print(f"\n最終的な合計ドキュメントオブジェクト数: {len(all_docs)}")
    return all_docs

def clean_documents(documents: List[Document]) -> List[Document]:
    """ドキュメントリストのテキストコンテンツをクリーニングする"""
    print("\nドキュメントのクリーニング処理を実行中...")
    cleaned_documents = []
    # import re # main関数内でimport済みの想定 or ここでimport

    for i, doc in enumerate(documents):
        original_content = doc.page_content
        if not original_content:
             print(f"  警告: 内容が空のドキュメントがあります (Source: {doc.metadata.get('source', '不明')}, Index: {i})。スキップします。")
             continue

        cleaned_content = original_content

        # --- 1. 改行のクリーニング ---
        cleaned_content = re.sub(r'\n\s*\n', '<<PARAGRAPH_BREAK>>', cleaned_content)
        cleaned_content = re.sub(r'\r\n', '\n', cleaned_content)
        cleaned_content = re.sub(r'\n\s?', '', cleaned_content)
        cleaned_content = cleaned_content.replace('<<PARAGRAPH_BREAK>>', '\n\n')

        # --- 2. 文字間の不要なスペースを除去 (日本語テキスト向け) ---
        cleaned_content = re.sub(f'([{JP_CHARS}]) ([{JP_CHARS}])', r'\1\2', cleaned_content)

        # --- 3. 連続するスペースを単一に & 前後トリム ---
        cleaned_content = re.sub(r'\s+', ' ', cleaned_content).strip()

        # --- 4. 短すぎるコンテンツを除去 ---
        min_length = 20 # Webコンテンツは短い定型文が多いため、少し閾値を上げる (調整可能)
        if len(cleaned_content) < min_length:
            print(f"  警告: クリーニング後に内容が短すぎるためスキップ (長さ: {len(cleaned_content)}, 最低{min_length}文字, Source: {doc.metadata.get('source', '不明')})")
            continue

        cleaned_doc = Document(page_content=cleaned_content, metadata=doc.metadata.copy())
        cleaned_documents.append(cleaned_doc)

    print(f"クリーニング処理完了。有効なドキュメント数: {len(cleaned_documents)}")
    return cleaned_documents


def split_by_paragraph(documents: List[Document]) -> List[Document]:
    """ドキュメントを段落単位（空行区切り）で分割する (クリーニング後のテキスト用)"""
    print("段落単位でドキュメントを分割中...")
    split_docs = []
    for doc in documents:
        content = doc.page_content
        paragraphs = re.split(r'\n\n', content)
        for para in paragraphs:
            cleaned_para = para.strip()
            if cleaned_para:
                new_doc = Document(page_content=cleaned_para, metadata=doc.metadata.copy())
                split_docs.append(new_doc)
    print(f"  合計 {len(split_docs)} 個の段落チャンクに分割しました。")
    return split_docs

def main(input_dir, url_file, db_path, split_method, chunk_size, chunk_overlap):
    """メイン処理"""
    import re # ここでimport

    # --- 1. APIキーチェック & 埋め込みモデル初期化 ---
    if "OPENAI_API_KEY" not in os.environ:
        print("警告: OpenAI APIキーが環境変数 'OPENAI_API_KEY' に設定されていません。")
    print("埋め込みモデルを初期化中 (OpenAI)...")
    try:
        embeddings = OpenAIEmbeddings()
    except Exception as e:
        print(f"OpenAI埋め込みモデルの初期化に失敗しました: {e}")
        exit()

    # --- 2. ドキュメントの読み込み ---
    documents = load_documents(input_dir, url_file)
    if not documents:
        print("処理対象のドキュメントが見つかりませんでした。プログラムを終了します。")
        return

    # --- 3. ドキュメントのクリーニング ---
    cleaned_documents = clean_documents(documents)
    if not cleaned_documents:
        print("クリーニング後に有効なドキュメントが残っていません。プログラムを終了します。")
        return

    # --- 4. テキストの分割 ---
    splits = []
    print(f"\n分割メソッド '{split_method}' でドキュメントを分割中...")
    if split_method == "recursive":
        print(f"  チャンクサイズ {chunk_size}, オーバーラップ {chunk_overlap} で分割します。")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        try:
            splits = text_splitter.split_documents(cleaned_documents)
            print(f"  合計 {len(splits)} 個のチャンクに分割しました。")
        except Exception as e:
            print(f"  再帰的文字分割中にエラーが発生しました: {e}")
            return
    elif split_method == "paragraph":
        try:
            splits = split_by_paragraph(cleaned_documents)
        except Exception as e:
            print(f"  段落分割中にエラーが発生しました: {e}")
            return
    else:
        print(f"エラー: 未知の分割メソッド '{split_method}' です。")
        return

    if not splits:
        print("分割後のチャンクがありません。処理を終了します。")
        return

    # --- 5. ChromaDBへの接続とデータの追加 ---
    print(f"\nChromaDB '{db_path}' に接続/作成し、データを追加中...")
    try:
        vectorstore = Chroma(
            persist_directory=db_path,
            embedding_function=embeddings
        )
        print(f"  {len(splits)} 個のチャンクをベクトル化してDBに追加しています...")
        # IDを生成 (ソースURL/ファイルパス + チャンク内容のハッシュ)
        ids = []
        for i, doc in enumerate(splits):
            source_str = doc.metadata.get('source', f'unknown_{i}')
            # ファイルパスやURLに使えない文字を置換（オプション）
            safe_source_str = re.sub(r'[\\/*?:"<>|]', '_', source_str)
            content_hash = hashlib.md5(doc.page_content.encode()).hexdigest()[:8]
            # IDが長すぎると問題になる場合があるので注意
            ids.append(f"{safe_source_str}_{i}_{content_hash}")

        vectorstore.add_documents(splits, ids=ids)
        print("  DBへのデータの追加/更新が完了しました。")

    except Exception as e:
        print(f"ChromaDBへの接続またはデータ追加中にエラーが発生しました: {e}")
        return

    # --- 6. 処理結果の表示 ---
    print("-" * 50)
    print("処理が正常に完了しました。")
    if input_dir: print(f"  テキスト入力ディレクトリ: {input_dir}")
    if url_file: print(f"  URLリストファイル: {url_file}")
    print(f"  読み込んだ初期ドキュメントオブジェクト数: {len(documents)}")
    print(f"  クリーニング後の有効ドキュメント数: {len(cleaned_documents)}")
    print(f"  生成/DB追加されたチャンク数: {len(splits)}")
    print(f"  使用した分割メソッド: {split_method}")
    if split_method == 'recursive':
        print(f"    チャンクサイズ: {chunk_size}, オーバーラップ: {chunk_overlap}")
    print(f"  ChromaDB保存先: {db_path}")
    try:
        final_count = vectorstore._collection.count()
        print(f"  現在のDB内のチャンク総数: {final_count}")
    except Exception as e:
        print(f"  DB内のチャンク数取得中にエラー: {e}")
    print("-" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="テキストファイルや指定URLのWebページを読み込み、クリーニング、分割し、ChromaDBに永続化するスクリプト",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--input_dir", type=str, default=None, help="処理対象のテキストファイルが含まれるディレクトリ (オプション)")
    parser.add_argument("--url_file", type=str, default=None, help="処理対象のURLが1行ずつ記載されたファイルのパス (オプション)")
    parser.add_argument("--db_path", type=str, default=DEFAULT_DB_PATH, help="ChromaDBを保存するディレクトリパス")
    parser.add_argument("--split_method", type=str, default=DEFAULT_SPLIT_METHOD, choices=['recursive', 'paragraph'], help="テキストの分割方法")
    parser.add_argument("--chunk_size", type=int, default=DEFAULT_CHUNK_SIZE, help="テキスト分割のチャンクサイズ (recursiveモード時)")
    parser.add_argument("--chunk_overlap", type=int, default=DEFAULT_CHUNK_OVERLAP, help="テキスト分割のチャンクオーバーラップ (recursiveモード時)")

    args = parser.parse_args()

    # --- 入力チェック ---
    if not args.input_dir and not args.url_file:
        parser.error("エラー: --input_dir または --url_file の少なくとも一つを指定する必要があります。")
    # ファイル/ディレクトリの存在チェックは load_documents 関数内で行う

    # --- DBディレクトリ準備 ---
    db_parent_dir = os.path.dirname(args.db_path)
    if db_parent_dir and not os.path.exists(db_parent_dir):
        print(f"情報: DB保存先の親ディレクトリ '{db_parent_dir}' が存在しないため作成します。")
        try:
            os.makedirs(db_parent_dir, exist_ok=True)
        except Exception as e:
            print(f"エラー: DB保存先の親ディレクトリ作成に失敗しました: {e}")
            exit()

    if args.split_method == 'paragraph':
        print("\n情報: 'paragraph' モードが選択されました。")

    # main 関数の呼び出し
    main(args.input_dir, args.url_file, args.db_path, args.split_method, args.chunk_size, args.chunk_overlap)