import importlib
import types
import sys
import os

import pytest

# Stub external dependencies that may not be installed
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if 'mcp.server.fastmcp' not in sys.modules:
    fastmcp_mod = types.ModuleType('fastmcp')
    class DummyFastMCP:
        def __init__(self, name):
            self.name = name
        def tool(self):
            def decorator(func):
                return func
            return decorator
        def resource(self, path):
            def decorator(func):
                return func
            return decorator
        def run(self, *args, **kwargs):
            pass
    fastmcp_mod.FastMCP = DummyFastMCP
    sys.modules['mcp.server.fastmcp'] = fastmcp_mod

def _stub(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod

if 'langchain_openai' not in sys.modules:
    sys.modules['langchain_openai'] = _stub('langchain_openai',
                                           OpenAIEmbeddings=object,
                                           ChatOpenAI=object)
if 'langchain_chroma' not in sys.modules:
    sys.modules['langchain_chroma'] = _stub('langchain_chroma', Chroma=object)
if 'langchain_core.prompts' not in sys.modules:
    sys.modules['langchain_core.prompts'] = _stub('prompts', ChatPromptTemplate=object)
if 'langchain_core.runnables' not in sys.modules:
    sys.modules['langchain_core.runnables'] = _stub('runnables',
                                                   RunnablePassthrough=object,
                                                   RunnableParallel=object)
if 'langchain_core.output_parsers' not in sys.modules:
    sys.modules['langchain_core.output_parsers'] = _stub('output_parsers', StrOutputParser=object)
if 'langchain_core.documents' not in sys.modules:
    sys.modules['langchain_core.documents'] = _stub('documents', Document=object)
if 'dotenv' not in sys.modules:
    sys.modules['dotenv'] = _stub('dotenv', load_dotenv=lambda *a, **k: None)

# Now import target modules
from apm_mcp_server.rag_chroma import core
from apm_mcp_server.rag_chroma.core import RAGManager
import apm_mcp_server.main as main


def test_initialize_rag_system_missing_key(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    assert core.initialize_rag_system() is None


def test_ragmanager_singleton(monkeypatch):
    RAGManager._instance = None
    called = {'count': 0}
    dummy_components = object()
    def fake_init():
        called['count'] += 1
        return dummy_components
    monkeypatch.setattr(core, 'initialize_rag_system', fake_init)

    mgr1 = RAGManager.get_instance()
    mgr2 = RAGManager.get_instance()
    assert mgr1 is mgr2
    assert not mgr1.is_initialized()

    mgr1.initialize()
    assert mgr1.is_initialized()
    assert called['count'] == 1

    mgr1.initialize()
    assert called['count'] == 1


def test_get_practice_url_and_names(monkeypatch):
    class DummyEmb:
        pass

    class DummyChroma:
        def __init__(self, *a, **k):
            pass
        def get(self, include=None):
            return {
                'metadatas': [
                    {'practice_name': 'foo', 'source': 'http://foo'},
                    {'practice_name': 'bar', 'source': 'http://bar'},
                ]
            }

    monkeypatch.setattr(core, 'OpenAIEmbeddings', DummyEmb)
    monkeypatch.setattr(core, 'Chroma', DummyChroma)

    assert core.get_practice_url('foo') == {'practice_name': 'foo', 'url': 'http://foo'}
    assert core.get_practice_url('none') == {'practice_name': 'none', 'url': None}
    assert core.get_practice_names() == ['bar', 'foo']


def test_main_query_and_list(monkeypatch):
    class DummyRM:
        def query(self, q):
            return 'ans:' + q, None
        def get_practices(self):
            return ['p1', 'p2']

    dummy_rm = DummyRM()
    monkeypatch.setattr(main.RAGManager, 'get_instance', lambda: dummy_rm)

    assert main.query_apm('q') == 'ans:q'
    assert main.list_apm_practices() == ['p1', 'p2']
