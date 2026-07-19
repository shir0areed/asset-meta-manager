// ui-identity.js
// identity 選択モーダルの制御

// -----------------------------
// 要素取得
// -----------------------------
const identityModal = document.getElementById("identity-modal");
const identitySelectBtn = document.getElementById("identity-select");
const identitySelector = document.getElementById("identity-selector");
const identityApplyBtn = document.getElementById("identity-apply");
const identityCloseBtn = document.getElementById("close-identity-modal");

// -----------------------------
// モーダル開閉
// -----------------------------
identitySelectBtn.addEventListener("click", async () => {
    await loadIdentityList();
    identityModal.style.display = "flex";
});

identityCloseBtn.addEventListener("click", () => {
    identityModal.style.display = "none";
});

// -----------------------------
// identity 一覧をロードしてセレクタに反映
// -----------------------------
async function loadIdentityList() {
    const res = await fetch("/identities");
    const data = await res.json();

    const list = data.identities || [];
    const current = data.current;   // ★ 現在選択中の index

    // セレクタをクリア
    identitySelector.innerHTML = "";

    if (list.length === 0) {
        // identity が 0 個の場合
        const opt = document.createElement("option");
        opt.textContent = "(identity がありません)";
        opt.value = "";
        identitySelector.appendChild(opt);
        identityApplyBtn.disabled = true;
        return;
    }

    identityApplyBtn.disabled = false;

    // identity をセレクタに追加
    list.forEach(item => {
        const opt = document.createElement("option");
        opt.value = item.index;
        opt.textContent = item.identity_path;

        // ★ 現在選択中の identity をデフォルト選択
        if (item.index === current) {
            opt.selected = true;
        }

        identitySelector.appendChild(opt);
    });
}

// -----------------------------
// identity を適用
// -----------------------------
identityApplyBtn.addEventListener("click", async () => {
    const index = identitySelector.value;

    if (index === "") {
        return; // identity がない場合
    }

    const fd = new FormData();
    fd.append("index", index);

    const res = await fetch("/set-identity", {
        method: "POST",
        body: fd
    });

    const data = await res.json();
    if (!data.ok) {
        alert("identity の切り替えに失敗しました");
        return;
    }

    // モーダルを閉じる
    identityModal.style.display = "none";

    // テーブル再読み込み
    if (typeof load === "function") {
        load();
    }
});

async function updateIdentityDisplay() {
    const span = document.getElementById("current-identity");

    const res = await fetch("/identities");
    const data = await res.json();

    const list = data.identities || [];
    const current = data.current;

    if (current == null || list.length === 0) {
        span.textContent = "(identityなし)";
        return;
    }

    span.textContent = list[current].identity_path;
}
