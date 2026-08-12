"""pytest 共享 fixture。"""
import sys
from pathlib import Path

# 让 rag-manager 自身可导入（rag_manager.py）
sys.path.insert(0, str(Path(__file__).parent.parent))
# 让 shared 可导入（RAGStore 公共位置，在项目根）
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
