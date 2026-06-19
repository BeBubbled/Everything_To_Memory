const dropzone = document.querySelector("#dropzone");
const fileInput = document.querySelector("#fileInput");
const statusEl = document.querySelector("#status");
const messageEl = document.querySelector("#message");
const sheetField = document.querySelector("#sheetField");
const sheetSelect = document.querySelector("#sheetSelect");
const frontSelect = document.querySelector("#frontSelect");
const backSelect = document.querySelector("#backSelect");
const controls = document.querySelector("#controls");
const generateButton = document.querySelector("#generateButton");

let currentToken = null;

function setMessage(text, isError = false) {
  messageEl.textContent = text;
  messageEl.classList.toggle("error", isError);
}

function setStatus(text) {
  statusEl.textContent = text;
}

function fillSelect(select, values, preferredIndex = 0) {
  select.innerHTML = "";
  values.forEach((value, index) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    if (index === preferredIndex) {
      option.selected = true;
    }
    select.appendChild(option);
  });
}

function setColumns(columns) {
  fillSelect(frontSelect, columns, 0);
  fillSelect(backSelect, columns, Math.min(1, columns.length - 1));
  generateButton.disabled = columns.length < 2;
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "请求失败");
  }
  return data;
}

async function uploadFile(file) {
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);
  setStatus("读取中");
  setMessage("");
  generateButton.disabled = true;

  try {
    const data = await requestJson("/api/inspect", {
      method: "POST",
      body: formData,
    });

    currentToken = data.token;
    if (data.sheets.length) {
      sheetField.classList.remove("hidden");
      fillSelect(sheetSelect, data.sheets, 0);
    } else {
      sheetField.classList.add("hidden");
      sheetSelect.innerHTML = "";
    }

    setColumns(data.columns);
    setStatus("已载入");
    setMessage(`${data.filename} 已载入，选择正面和背面列后生成。`);
  } catch (error) {
    currentToken = null;
    setStatus("读取失败");
    setMessage(error.message, true);
  }
}

async function loadSheetColumns() {
  if (!currentToken || !sheetSelect.value) return;

  setStatus("读取列");
  setMessage("");
  generateButton.disabled = true;

  try {
    const data = await requestJson("/api/columns", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token: currentToken,
        sheet: sheetSelect.value,
      }),
    });
    setColumns(data.columns);
    setStatus("已载入");
  } catch (error) {
    setStatus("读取失败");
    setMessage(error.message, true);
  }
}

async function generateCards(event) {
  event.preventDefault();
  if (!currentToken) return;

  setStatus("生成中");
  setMessage("");
  generateButton.disabled = true;

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token: currentToken,
        sheet: sheetSelect.value || null,
        front: frontSelect.value,
        back: backSelect.value,
      }),
    });

    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || "生成失败");
    }

    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : "anki_cards.txt";
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setStatus("已生成");
    setMessage("Anki TXT 已生成并下载。");
  } catch (error) {
    setStatus("生成失败");
    setMessage(error.message, true);
  } finally {
    generateButton.disabled = false;
  }
}

dropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropzone.classList.add("dragover");
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("dragover");
});

dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropzone.classList.remove("dragover");
  uploadFile(event.dataTransfer.files[0]);
});

fileInput.addEventListener("change", () => {
  uploadFile(fileInput.files[0]);
});

sheetSelect.addEventListener("change", loadSheetColumns);
controls.addEventListener("submit", generateCards);
