(function () {
  const mineBoard = document.getElementById("mine-board");
  const mineStatus = document.getElementById("mine-status");
  const mineLevel = document.getElementById("mine-level");
  let mineState = null;
  let mineTimer = null;

  function shuffled(values) {
    const result = [...values];
    for (let i = result.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [result[i], result[j]] = [result[j], result[i]];
    }
    return result;
  }

  function neighbors(index, rows, cols) {
    const row = Math.floor(index / cols), col = index % cols, values = [];
    for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) {
      const r = row + dr, c = col + dc;
      if ((dr || dc) && r >= 0 && r < rows && c >= 0 && c < cols) values.push(r * cols + c);
    }
    return values;
  }

  function updateMineStatus(stateLabel = t("game_ready")) {
    if (!mineState || !mineStatus) return;
    const flags = mineState.cells.filter(cell => cell.flag).length;
    mineStatus.textContent = `${stateLabel} | ${t("game_mines_left")}: ${Math.max(0, mineState.mines - flags)} | ${t("game_time")}: ${mineState.elapsed}s`;
  }

  function startMineTimer() {
    if (mineTimer || !mineState) return;
    mineState.startedAt = Date.now();
    mineTimer = setInterval(() => {
      if (!mineState || mineState.over) return;
      mineState.elapsed = Math.min(999, Math.floor((Date.now() - mineState.startedAt) / 1000));
      updateMineStatus();
    }, 500);
  }

  function stopMineTimer() {
    clearInterval(mineTimer);
    mineTimer = null;
  }

  function placeMines(firstIndex) {
    const s = mineState;
    const protectedCells = new Set([firstIndex, ...neighbors(firstIndex, s.rows, s.cols)]);
    const positions = shuffled([...s.cells.keys()].filter(index => !protectedCells.has(index))).slice(0, s.mines);
    positions.forEach(index => { s.cells[index].mine = true; });
    s.cells.forEach((cell, index) => {
      cell.count = neighbors(index, s.rows, s.cols).filter(neighbor => s.cells[neighbor].mine).length;
    });
    s.placed = true;
  }

  function newMinesweeper() {
    if (!mineBoard) return;
    stopMineTimer();
    const [rows, cols, mines] = (mineLevel?.value || "9x9x10").split("x").map(Number);
    mineState = {
      rows, cols, mines, over: false, placed: false, elapsed: 0,
      cells: Array.from({length: rows * cols}, () => ({mine: false, open: false, flag: false, count: 0})),
    };
    updateMineStatus();
    renderMines();
  }

  function floodOpen(startIndex) {
    const s = mineState;
    const queue = [startIndex];
    while (queue.length) {
      const index = queue.shift();
      const cell = s.cells[index];
      if (!cell || cell.open || cell.flag) continue;
      cell.open = true;
      if (!cell.mine && cell.count === 0) {
        neighbors(index, s.rows, s.cols).forEach(neighbor => {
          if (!s.cells[neighbor].open && !s.cells[neighbor].mine) queue.push(neighbor);
        });
      }
    }
  }

  function finishMineGame(won) {
    const s = mineState;
    s.over = true;
    stopMineTimer();
    if (won) s.cells.forEach(cell => { if (cell.mine) cell.flag = true; });
    else s.cells.forEach(cell => { if (cell.mine) cell.open = true; });
    updateMineStatus(won ? t("game_won") : t("game_lost"));
  }

  function openMine(index) {
    const s = mineState, cell = s?.cells[index];
    if (!s || !cell || s.over || cell.open || cell.flag) return;
    if (!s.placed) { placeMines(index); startMineTimer(); }
    if (cell.mine) { cell.exploded = true; finishMineGame(false); renderMines(); return; }
    floodOpen(index);
    if (s.cells.every(candidate => candidate.mine || candidate.open)) finishMineGame(true);
    renderMines();
  }

  function chordMine(index) {
    const s = mineState, cell = s?.cells[index];
    if (!s || s.over || !cell?.open || !cell.count) return;
    const around = neighbors(index, s.rows, s.cols);
    if (around.filter(neighbor => s.cells[neighbor].flag).length !== cell.count) return;
    around.forEach(openMine);
  }

  function toggleMineFlag(index) {
    const s = mineState, cell = s?.cells[index];
    if (!s || !cell || s.over || cell.open) return;
    cell.flag = !cell.flag;
    updateMineStatus();
    renderMines();
  }

  function renderMines() {
    const s = mineState;
    if (!s || !mineBoard) return;
    mineBoard.style.gridTemplateColumns = `repeat(${s.cols}, 28px)`;
    mineBoard.innerHTML = s.cells.map((cell, index) => {
      const numberClass = cell.open && cell.count ? ` n${cell.count}` : "";
      const content = cell.flag ? "F" : cell.open ? (cell.mine ? "*" : cell.count || "") : "";
      return `<button class="mine-cell ${cell.open ? "open" : ""}${cell.exploded ? " exploded" : ""}${numberClass}" data-i="${index}" aria-label="cell ${index + 1}">${content}</button>`;
    }).join("");
    mineBoard.querySelectorAll(".mine-cell").forEach(button => {
      const index = Number(button.dataset.i);
      button.onclick = () => openMine(index);
      button.ondblclick = () => chordMine(index);
      button.oncontextmenu = event => { event.preventDefault(); toggleMineFlag(index); };
    });
  }

  document.getElementById("mine-new")?.addEventListener("click", newMinesweeper);
  mineLevel?.addEventListener("change", newMinesweeper);
  window.refreshGamesTranslations = () => updateMineStatus();
  newMinesweeper();
})();
