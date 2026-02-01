import argparse
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
import uvicorn

from app.core.state import AppState


app = FastAPI()


@app.on_event("startup")
async def startup_event():
    state = app.state.manager
    print("Scanned files:")
    for f in state.files:
        print(" -", f)

@app.get("/instance-info")
def instance_info():
    """
    STEP1 の動作確認用エンドポイント。
    UI 実装前でもブラウザで確認できる。
    """
    state = app.state.manager
    return {
        "identity": str(state.identity_path),
        "instance_root": str(state.instance_root),
        "sibling_folders": [str(p) for p in state.sibling_folders],
    }


@app.get("/scan-result")
def scan_result():
    """
    STEP2 の動作確認用エンドポイント。
    スキャンされたファイル一覧を返す。
    """
    state = app.state.manager
    root = state.instance_root  # identity の親フォルダ

    result = []

    for p in state.files:
        # identity からの相対パス（Path）
        rel = p.relative_to(root)

        # UI 用に POSIX 文字列へ
        rel_posix = rel.as_posix()

        name = p.stem

        result.append({
            "path": rel_posix,
            "name": name,
        })

    return {
        "files": result
    }


@app.get("/ui")
def ui():
    html_path = Path(__file__).parent / "static" / "ui.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/file")
def download_file(path: str = Query(..., description="Relative POSIX path from identity root")):
    """
    STEP4: ファイルダウンロード用エンドポイント。
    path は絶対パスで渡す。
    """
    state = app.state.manager
    root = state.instance_root

    # 相対 POSIX パスを Path に戻す
    abs_path = (root / Path(path)).resolve()

    return FileResponse(abs_path, filename=abs_path.name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", required=True, help="Path to identity file")
    args = parser.parse_args()

    # identity をロード
    app.state.manager = AppState(identity_path=args.identity)

    # uvicorn 起動
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
