from pathlib import Path
from typing import Optional, List


class AppState:
    """
    アプリ全体で共有する状態。
    STEP1では identity とインスタンスルート、同階層フォルダ一覧のみ保持する。
    後続ステップでスキャン結果やスキーマをここに追加していく。
    """

    def __init__(self) -> None:
        self.identity_path: Optional[Path] = None
        self.instance_root: Optional[Path] = None
        self.sibling_folders: List[Path] = []

    def load_identity(self, identity: str) -> None:
        identity_path = Path(identity).resolve()

        if not identity_path.exists():
            raise FileNotFoundError(f"identity file not found: {identity_path}")

        self.identity_path = identity_path
        self.instance_root = identity_path.parent

        # 同階層のフォルダ一覧を取得
        self.sibling_folders = [
            p for p in self.instance_root.iterdir() if p.is_dir()
        ]
