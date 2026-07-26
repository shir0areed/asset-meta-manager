// ui-database.js
// database 選択モーダルの制御

// -----------------------------
// 要素取得
// -----------------------------
const databaseModal = document.getElementById("database-modal");
const databaseSelectBtn = document.getElementById("database-select");
const databaseSelector = document.getElementById("database-selector");
const databaseApplyBtn = document.getElementById("database-apply");
const databaseCloseBtn = document.getElementById("close-database-modal");

// -----------------------------
// モーダル開閉
// -----------------------------
databaseSelectBtn.addEventListener("click", async () => {
    await loadDatabaseList();
    databaseModal.style.display = "flex";
});

databaseCloseBtn.addEventListener("click", () => {
    databaseModal.style.display = "none";
});

// -----------------------------
// database 一覧をロードしてセレクタに反映
// -----------------------------
async function loadDatabaseList() {
    const res = await fetch("/databases");
    const data = await res.json();

    const list = data.databases || [];

    // URL の db=key を現在選択中として扱う
    const params = new URLSearchParams(location.search);
    const current = params.get("db");

    // セレクタをクリア
    databaseSelector.innerHTML = "";

    if (list.length === 0) {
        // database が 0 個の場合
        const opt = document.createElement("option");
        opt.textContent = "(database がありません)";
        opt.value = "";
        databaseSelector.appendChild(opt);
        databaseApplyBtn.disabled = true;
        return;
    }

    databaseApplyBtn.disabled = false;

    // database をセレクタに追加
    list.forEach(item => {
        const opt = document.createElement("option");
        opt.value = item.key;
        opt.textContent = item.database_path;

        // ★ 現在選択中の database をデフォルト選択
        if (item.key === current) {
            opt.selected = true;
        }

        databaseSelector.appendChild(opt);
    });
}

// -----------------------------
// database を適用
// -----------------------------
databaseApplyBtn.addEventListener("click", async () => {
    const key = databaseSelector.value;

    if (key === "") {
        return; // database がない場合
    }

    // ★ ステートレス化により /set-database は不要
    //   URL の db=key を更新するだけでよい
    history.replaceState(null, "", `?db=${key}`);

    // モーダルを閉じる
    databaseModal.style.display = "none";

    // テーブル再読み込み
    loadCategoryColumns(key);
    loadAnnotationColumns(key);
    load(key);
});

async function updateDatabaseDisplay() {
    const span = document.getElementById("current-database");

    const res = await fetch("/databases");
    const data = await res.json();
    
    const list = data.databases || [];
    const params = new URLSearchParams(location.search);
    const current = params.get("db");

    const found = list.find(x => x.key === current);
    if (current == null || !found) {
        span.textContent = "(databaseなし)";
        return;
    }

    span.textContent = found.database_path;
}
