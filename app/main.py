import argparse
from fastapi import FastAPI
import uvicorn

from app.core.state import AppState


app = FastAPI()
state = AppState()


@app.on_event("startup")
async def startup_event():
    # STEP2: フォルダスキャン
    state.scan_files()

    print("Scanned files:")
    for f in state.files:
        print(" -", f)

@app.get("/instance-info")
def instance_info():
    """
    STEP1 の動作確認用エンドポイント。
    UI 実装前でもブラウザで確認できる。
    """
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
    return {
        "files": [str(p) for p in state.files]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", required=True, help="Path to identity file")
    args = parser.parse_args()

    # identity をロード
    state.load_identity(args.identity)

    # uvicorn 起動
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
