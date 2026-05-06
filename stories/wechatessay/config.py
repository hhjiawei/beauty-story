from pathlib import Path

from deepagents.backends import CompositeBackend, FilesystemBackend
from dotenv import find_dotenv
from langgraph.store.memory import InMemoryStore

root = Path(find_dotenv()).parent
print(" 项目根目录是：" + str(root))

MEMORY_DIR = (root / "workspaces" / "memories").as_posix()
SKILLS_DIR = (root / "workspaces" / "skills").as_posix()  # 或根据实际结构调整
WORKSPACE_DIR = (root / "workspaces").as_posix()

composite_backend = CompositeBackend(
    default=FilesystemBackend(root_dir=root, virtual_mode=True),
    routes={
        "/memories/": FilesystemBackend(root_dir=MEMORY_DIR, virtual_mode=True),
        "/skills/": FilesystemBackend(root_dir=SKILLS_DIR, virtual_mode=True),
        "/workplace/": FilesystemBackend(root_dir=WORKSPACE_DIR, virtual_mode=True)
    },
)
store = InMemoryStore()
