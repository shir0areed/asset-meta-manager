let editMode = false;

/* ------------------------------
   編集モード（セル編集）
------------------------------ */
const editToggleBtn = document.getElementById("edit-toggle");

editToggleBtn.onclick = () => {
    editMode = !editMode;
    editToggleBtn.textContent =
        editMode ? "編集モード: ON" : "編集モード: OFF";

    load(); // 再描画
};

/* ------------------------------
   列編集モーダルの開閉
------------------------------ */
const columnModal = document.getElementById("column-modal");
const columnEditBtn = document.getElementById("column-edit");
const closeColumnModalBtn = document.getElementById("close-column-modal");

// モーダルを開く
columnEditBtn.onclick = () => {
    columnModal.style.display = "flex";
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
