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
    const current = data.current;   // ★ 現在選択中の index

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
        opt.value = item.index;
        opt.textContent = item.database_path;

        // ★ 現在選択中の database をデフォルト選択
        if (item.index === current) {
            opt.selected = true;
        }

        databaseSelector.appendChild(opt);
    });
}

// -----------------------------
// database を適用
// -----------------------------
databaseApplyBtn.addEventListener("click", async () => {
    const index = databaseSelector.value;

    if (index === "") {
        return; // database がない場合
    }

    const fd = new FormData();
    fd.append("index", index);

    const res = await fetch("/set-database", {
        method: "POST",
        body: fd
    });

    const data = await res.json();
    if (!data.ok) {
        alert("database の切り替えに失敗しました");
        return;
    }

    // モーダルを閉じる
    databaseModal.style.display = "none";

    // テーブル再読み込み
    if (typeof load === "function") {
        load();
    }
});

async function updateDatabaseDisplay() {
    const span = document.getElementById("current-database");

    const res = await fetch("/databases");
    const data = await res.json();

    const list = data.databases || [];
    const current = data.current;

    if (current == null || list.length === 0) {
        span.textContent = "(databaseなし)";
        return;
    }

    span.textContent = list[current].database_path;
}
