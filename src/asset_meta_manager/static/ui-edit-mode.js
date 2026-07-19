let editMode = false;

/* ------------------------------
   編集モード（セル編集）
------------------------------ */
const editToggleBtn = document.getElementById("edit-toggle-checkbox");

editToggleBtn.onchange = () => {
    editMode = editToggleBtn.checked;
    load(); // 再描画
};

/* ------------------------------
   列編集モーダルの開閉
------------------------------ */
const columnModal = document.getElementById("column-modal");
const columnEditBtn = document.getElementById("column-edit");
const closeColumnModalBtn = document.getElementById("close-column-modal");

// --- フォーマット関連要素は一度だけ取得してキャッシュする ---
const formatSelect = document.getElementById("format-select");
const formatApplyBtn = document.getElementById("format-apply");

// モーダルを開く
columnEditBtn.onclick = () => {
    columnModal.style.display = "flex";
    // 開いたらフォーマット一覧と現在値を取得して初期化
    populateFormatSelect();
};

// モーダルを閉じる
closeColumnModalBtn.onclick = () => {
    columnModal.style.display = "none";
};

// モーダル外クリックで閉じる（任意）
columnModal.onclick = (e) => {
    if (e.target === columnModal) {
        columnModal.style.display = "none";
    }
};

/* ------------------------------
   フォーマット一覧取得と初期化
   （読み込み中プレースホルダは表示しない）
------------------------------ */
async function populateFormatSelect() {
    if (!formatSelect) return;

    // 既存項目をクリア（プレースホルダは入れない）
    formatSelect.innerHTML = "";

    try {
        // フォーマット一覧を取得
        const resFormats = await fetch("/formats");
        if (!resFormats.ok) throw new Error("formats fetch failed");
        const formatsJson = await resFormats.json();
        const formats = Array.isArray(formatsJson.formats) ? formatsJson.formats : [];

        // 現在のデータベース設定を軽量に取得（/instance-info を利用）
        let currentFormat = null;
        try {
            const resInfo = await fetch("/instance-info");
            if (resInfo.ok) {
                const info = await resInfo.json();
                currentFormat = info.format || null;
            }
        } catch (e) {
            currentFormat = null;
        }

        // セレクトを構築（空リストでも空のまま表示）
        formatSelect.innerHTML = "";
        formats.forEach((f) => {
            const opt = document.createElement("option");
            opt.value = f;
            opt.textContent = f;
            formatSelect.appendChild(opt);
        });

        // 選択: currentFormat があればそれ、なければ先頭（存在する場合）
        if (currentFormat && formats.includes(currentFormat)) {
            formatSelect.value = currentFormat;
        } else if (formats.length > 0) {
            formatSelect.selectedIndex = 0;
        }

        // 適用ボタンは項目があるときだけ有効にする（それ以外は無効）
        if (formatApplyBtn) {
            formatApplyBtn.disabled = !(formats.length > 0);
        }
    } catch (err) {
        console.error("populateFormatSelect error:", err);
        // 取得失敗時はセレクトを空のままにして適用ボタンを無効化
        formatSelect.innerHTML = "";
        if (formatApplyBtn) formatApplyBtn.disabled = true;
    }
}

/* ------------------------------
   フォーマット適用（ボタン押下）
   （シンプルに POST して結果に応じて load() を呼ぶ）
   二重送信対策は行わない（他のボタンと同様の扱い）
------------------------------ */
formatApplyBtn.addEventListener("click", async () => {
    const fmt = formatSelect.value;
    if (!fmt) {
        alert("フォーマットを選択してください。");
        return;
    }

    try {
        // 軽量チェック: データベースが選択されているか確認
        const infoRes = await fetch("/instance-info");
        if (!infoRes.ok) throw new Error("failed to fetch instance-info");
        const info = await infoRes.json();
        if (!info.database) {
            alert("データベースが選択されていません。先にデータベースを選択してください。");
            await populateFormatSelect();
            return;
        }

        const form = new FormData();
        form.append("fmt", fmt);

        const res = await fetch("/set-format", {
            method: "POST",
            body: form,
        });

        const j = await res.json();

        if (!res.ok || !j.ok) {
            const supported = j && j.supported ? j.supported.join(", ") : "";
            alert("フォーマット適用に失敗しました: " + (j && j.error ? j.error : res.statusText) + (supported ? ("\nサポート: " + supported) : ""));
            // 失敗したら選択を再取得して復元
            await populateFormatSelect();
        } else {
            // 成功: UI を更新（ファイル一覧等を再描画）
            if (typeof load === "function") {
                load();
            }
        }
    } catch (err) {
        console.error("set-format error:", err);
        alert("フォーマット適用中にエラーが発生しました");
        await populateFormatSelect();
    }
});
