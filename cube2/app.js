const FACE_LABELS = {
    TOP: 'TOP',
    FRONT: 'FRONT',
    RIGHT: 'RIGHT',
    BACK: 'BACK',
    LEFT: 'LEFT',
    BOTTOM: 'BOTTOM'
};

const NET_SLOT_ORDER = ['BACK', 'LEFT', 'TOP', 'RIGHT', 'FRONT', 'BOTTOM'];
const RECONSTRUCTION_NET_POSITIONS = {
    BACK: { row: 0, col: 1 },
    LEFT: { row: 1, col: 0 },
    TOP: { row: 1, col: 1 },
    RIGHT: { row: 1, col: 2 },
    FRONT: { row: 2, col: 1 },
    BOTTOM: { row: 3, col: 1 }
};

const DIRECTION_META = {
    N: { arrow: '^', label: 'Roll Up' },
    S: { arrow: 'v', label: 'Roll Down' },
    W: { arrow: '<', label: 'Roll Left' },
    E: { arrow: '>', label: 'Roll Right' }
};

const appState = {
    levelCodes: [],
    levelIndex: null,
    taskCache: new Map(),
    currentTask: null,
    currentTaskIndex: -1,
    playerMoves: [],
    playerTrace: null,
    playerVisibleTrace: null,
    referenceTrace: null,
    lastResult: null,
    debugOpen: false,
    debugTraceKind: 'player',
    debugStep: 0,
    cubeRenderer: null,
    rendererError: null,
    toastTimer: null
};

const els = {};

document.addEventListener('DOMContentLoaded', () => {
    cacheElements();
    bindEvents();
    initializeApp().catch((error) => {
        console.error(error);
        renderLoadError(error.message);
    });
});

function cacheElements() {
    Object.assign(els, {
        levelScreen: document.getElementById('level-screen'),
        gameScreen: document.getElementById('game-screen'),
        levelSearch: document.getElementById('level-search'),
        levelCount: document.getElementById('level-count'),
        levelGrid: document.getElementById('level-grid'),
        backBtn: document.getElementById('back-btn'),
        gameTitle: document.getElementById('game-title'),
        gameSubtitle: document.getElementById('game-subtitle'),
        gameMeta: document.getElementById('game-meta'),
        cubeContainer: document.getElementById('cube-container'),
        resetViewBtn: document.getElementById('reset-view-btn'),
        debugPanel: document.getElementById('debug-panel'),
        debugPlayerTab: document.getElementById('debug-player-tab'),
        debugAnswerTab: document.getElementById('debug-answer-tab'),
        debugStepText: document.getElementById('debug-step-text'),
        debugCurrentFace: document.getElementById('debug-current-face'),
        debugCurrentMeta: document.getElementById('debug-current-meta'),
        debugTargetFace: document.getElementById('debug-target-face'),
        debugTargetMeta: document.getElementById('debug-target-meta'),
        debugSequence: document.getElementById('debug-sequence'),
        debugPrevBtn: document.getElementById('debug-prev-btn'),
        debugNextBtn: document.getElementById('debug-next-btn'),
        debugCloseBtn: document.getElementById('debug-close-btn'),
        netGrid: document.getElementById('net-grid'),
        targetFaceCanvas: document.getElementById('target-face-canvas'),
        targetFaceMeta: document.getElementById('target-face-meta'),
        targetText: document.getElementById('target-text'),
        playerSequence: document.getElementById('player-sequence'),
        currentFaceCanvas: document.getElementById('current-face-canvas'),
        currentFaceMeta: document.getElementById('current-face-meta'),
        undoBtn: document.getElementById('undo-btn'),
        clearBtn: document.getElementById('clear-btn'),
        submitBtn: document.getElementById('submit-btn'),
        debugPlayerBtn: document.getElementById('debug-player-btn'),
        debugAnswerBtn: document.getElementById('debug-answer-btn'),
        resultModal: document.getElementById('result-modal'),
        resultTitle: document.getElementById('result-title'),
        resultText: document.getElementById('result-text'),
        resultPlayerFace: document.getElementById('result-player-face'),
        resultPlayerMeta: document.getElementById('result-player-meta'),
        resultTargetFace: document.getElementById('result-target-face'),
        resultTargetFaceMeta: document.getElementById('result-target-face-meta'),
        referenceSequenceBox: document.getElementById('reference-sequence-box'),
        resultCloseBtn: document.getElementById('result-close-btn'),
        resultDebugPlayerBtn: document.getElementById('result-debug-player-btn'),
        resultDebugAnswerBtn: document.getElementById('result-debug-answer-btn'),
        nextLevelBtn: document.getElementById('next-level-btn'),
        toast: document.getElementById('toast')
    });
}

function bindEvents() {
    els.levelSearch.addEventListener('input', renderLevelGrid);
    els.backBtn.addEventListener('click', showLevelScreen);
    els.resetViewBtn.addEventListener('click', resetCubeView);
    els.undoBtn.addEventListener('click', handleUndo);
    els.clearBtn.addEventListener('click', handleClear);
    els.submitBtn.addEventListener('click', handleSubmit);
    els.debugPlayerBtn.addEventListener('click', () => openDebug('player'));
    els.debugAnswerBtn.addEventListener('click', () => openDebug('answer'));
    els.debugPlayerTab.addEventListener('click', () => switchDebugTrace('player'));
    els.debugAnswerTab.addEventListener('click', () => switchDebugTrace('answer'));
    els.debugPrevBtn.addEventListener('click', () => stepDebug(-1));
    els.debugNextBtn.addEventListener('click', () => stepDebug(1));
    els.debugCloseBtn.addEventListener('click', closeDebug);
    els.resultCloseBtn.addEventListener('click', closeResultModal);
    els.resultDebugPlayerBtn.addEventListener('click', () => {
        closeResultModal();
        openDebug('player');
    });
    els.resultDebugAnswerBtn.addEventListener('click', () => {
        closeResultModal();
        openDebug('answer');
    });
    els.nextLevelBtn.addEventListener('click', goToNextLevel);

    document.querySelectorAll('.move-btn').forEach((button) => {
        button.addEventListener('click', () => handleMove(button.dataset.direction));
    });

    window.addEventListener('resize', handleResize);
    window.addEventListener('keydown', handleKeydown);
}

async function initializeApp() {
    assertLaunchEnvironment();
    assertSharedDependencies();

    appState.levelIndex = await fetchJsonFromCandidates(
        [
            './data2/index.json',
            'data2/index.json'
        ],
        'data2/index.json'
    );
    appState.levelCodes = Array.isArray(appState.levelIndex.taskCodes) ? appState.levelIndex.taskCodes.slice() : [];
    renderLevelGrid();
}

function renderLevelGrid() {
    const keyword = els.levelSearch.value.trim().toUpperCase();
    const codes = appState.levelCodes.filter((code) => !keyword || code.includes(keyword));

    els.levelCount.textContent = `Total levels: ${appState.levelCodes.length} | Visible: ${codes.length}`;
    els.levelGrid.innerHTML = '';

    if (!codes.length) {
        const empty = document.createElement('div');
        empty.className = 'level-card';
        empty.textContent = 'No matching levels.';
        els.levelGrid.appendChild(empty);
        return;
    }

    codes.forEach((code) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'level-card';
        button.innerHTML = `
            <div class="level-card-code">${code}</div>
            <div class="level-card-note">Top-face target puzzle</div>
        `;
        button.addEventListener('click', () => {
            openLevel(code).catch((error) => {
                console.error(error);
                showToast(`Failed to load ${code}: ${error.message}`);
            });
        });
        els.levelGrid.appendChild(button);
    });
}

async function openLevel(code) {
    const task = await loadTask(code);
    appState.currentTask = task;
    appState.currentTaskIndex = appState.levelCodes.indexOf(code);
    appState.playerMoves = [];
    appState.lastResult = null;
    appState.debugOpen = false;
    appState.debugTraceKind = 'player';
    appState.debugStep = 0;
    appState.rendererError = null;
    appState.referenceTrace = hasReferenceTrace(task) ? buildTrace(task.answers?.directions ?? []) : null;
    appState.playerTrace = buildTrace([]);
    appState.playerVisibleTrace = buildTrace([], { visible: true });

    els.levelScreen.classList.add('hidden');
    els.gameScreen.classList.remove('hidden');

    renderTask();
    try {
        ensureRenderer();
        syncCubeToCurrentContext();
    } catch (error) {
        console.error('Failed to initialize the 3D renderer.', error);
        appState.rendererError = error?.message || String(error);
        renderRendererFallback(appState.rendererError);
        showToast(`3D preview unavailable: ${appState.rendererError}`);
    }
    closeResultModal();
    closeDebug();
    showToast(`${code} loaded.`);
}

async function loadTask(code) {
    if (appState.taskCache.has(code)) {
        return appState.taskCache.get(code);
    }

    const task = await fetchJsonFromCandidates(
        [
            `./data2/task_jsons/${code}.json`,
            `data2/task_jsons/${code}.json`
        ],
        code
    );
    appState.taskCache.set(code, task);
    return task;
}

function assertLaunchEnvironment() {
    if (window.location.protocol === 'file:') {
        throw new Error('Please launch this page from a local static server instead of file://.');
    }
}

function assertSharedDependencies() {
    const missing = [];
    if (typeof drawPattern !== 'function') {
        missing.push('patterns.js');
    }
    if (typeof cubeFromSolutionFaces !== 'function' || typeof simulatePathStates !== 'function') {
        missing.push('cube-engine.js');
    }
    if (typeof CubeRenderer !== 'function') {
        missing.push('cube-renderer.js');
    }

    if (missing.length) {
        throw new Error(`Missing shared dependency files: ${missing.join(', ')}`);
    }
}

async function fetchJsonFromCandidates(candidates, label) {
    let lastError = 'unknown error';

    for (const path of candidates) {
        try {
            const response = await fetch(path, { cache: 'no-store' });
            if (!response.ok) {
                lastError = `${path} returned ${response.status}`;
                continue;
            }
            return await response.json();
        } catch (error) {
            lastError = `${path} failed: ${error.message}`;
        }
    }

    throw new Error(`Failed to load ${label}. Last error: ${lastError}`);
}

function renderLoadError(message) {
    els.levelCount.textContent = `Failed to load levels: ${message}`;
    els.levelGrid.innerHTML = '';
    const card = document.createElement('div');
    card.className = 'level-card';
    card.textContent = message;
    els.levelGrid.appendChild(card);
}

function ensureRenderer() {
    if (appState.cubeRenderer) {
        handleResize();
        return;
    }

    els.cubeContainer.innerHTML = '';
    const rect = els.cubeContainer.getBoundingClientRect();
    const width = Math.max(320, Math.floor(rect.width || 420));
    const height = Math.max(320, Math.floor(rect.height || 420));
    appState.cubeRenderer = new CubeRenderer(els.cubeContainer, width, height);
    appState.cubeRenderer.setDirectionGuideVisible(true);
}

function renderRendererFallback(message) {
    els.cubeContainer.innerHTML = '';
    const fallback = document.createElement('div');
    fallback.className = 'cube-fallback';
    fallback.innerHTML = `
        <div class="cube-fallback-title">3D preview unavailable</div>
        <div class="cube-fallback-text">${message}</div>
    `;
    els.cubeContainer.appendChild(fallback);
}

function renderTask() {
    const task = appState.currentTask;
    if (!task) {
        return;
    }

    const target = task.targetTopFace;
    const tier = task.metadata?.tier ?? '--';
    const referenceCount = task.answers?.moveCount ?? task.answers?.directions?.length ?? 0;

    els.gameTitle.textContent = `${task.code} - ${task.name || 'Top Face Target'}`;
    els.gameSubtitle.textContent = 'Design a roll sequence so the final top face, viewed from above, matches the target exactly.';
    els.gameMeta.textContent = `Tier ${tier} - Reference moves ${referenceCount} - Target step ${target?.stepNumber ?? '--'}`;
    els.targetText.textContent = 'The target below shows the top face seen from above after the cube stops rolling.';

    renderNet(task.initialCube?.net?.cells ?? []);
    renderFaceCanvas(els.targetFaceCanvas, target, '#241F49');
    els.targetFaceMeta.textContent = formatFaceDetails(target);

    const hasReference = hasReferenceTrace(task);
    els.debugAnswerBtn.classList.toggle('hidden', !hasReference);
    els.resultDebugAnswerBtn.classList.toggle('hidden', !hasReference);
    els.debugAnswerTab.classList.toggle('hidden', !hasReference);

    renderPlayerSequence();
    renderCurrentTopFace();
    syncCubeToCurrentContext();
}

function renderNet(cells) {
    els.netGrid.innerHTML = '';
    const cellByKey = new Map(cells.map((cell) => [cell.faceKey, cell]));

    NET_SLOT_ORDER.forEach((slotKey) => {
        const slot = document.createElement('div');
        slot.className = 'net-slot';
        slot.style.gridColumn = String(RECONSTRUCTION_NET_POSITIONS[slotKey].col + 1);
        slot.style.gridRow = String(RECONSTRUCTION_NET_POSITIONS[slotKey].row + 1);

        const face = cellByKey.get(slotKey) || {
            faceKey: slotKey,
            patternId: '?',
            rotation: 0
        };
        slot.classList.add(face.patternId === '?' ? 'unknown' : 'known');

        const label = document.createElement('div');
        label.className = 'net-slot-label';
        label.textContent = FACE_LABELS[slotKey] || slotKey;

        const canvas = document.createElement('canvas');
        canvas.width = 96;
        canvas.height = 96;
        renderFaceCanvas(canvas, face, '#241F49');

        const angle = document.createElement('div');
        angle.className = 'net-slot-angle';
        angle.textContent = face.patternId === '?' ? '?' : String(Number(face.rotation ?? 0));

        slot.appendChild(label);
        slot.appendChild(canvas);
        slot.appendChild(angle);
        els.netGrid.appendChild(slot);
    });
}

function renderFaceCanvas(canvas, face, bgColor = '#231F48') {
    const ctx = canvas.getContext('2d');
    const size = Math.min(canvas.width, canvas.height);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawPattern(ctx, face || { patternId: '?', rotation: 0 }, 0, 0, 0, size, bgColor);
}

function renderCurrentTopFace() {
    const currentFace = getCurrentObservedFace({ visible: true, includeInitial: true });
    renderFaceCanvas(els.currentFaceCanvas, currentFace, '#241F49');
    els.currentFaceMeta.textContent = currentFace
        ? `Current top face: ${formatFaceDetails(currentFace)}`
        : 'No moves yet.';
}

function handleMove(direction) {
    if (!appState.currentTask || !DIRECTION_META[direction]) {
        return;
    }

    appState.playerMoves = [...appState.playerMoves, direction];
    appState.playerTrace = buildTrace(appState.playerMoves);
    appState.playerVisibleTrace = buildTrace(appState.playerMoves, { visible: true });
    renderPlayerSequence();
    renderCurrentTopFace();

    if (appState.debugOpen && appState.debugTraceKind === 'player') {
        appState.debugStep = appState.playerTrace.states.length - 1;
        renderDebugPanel();
    } else {
        syncCubeToCurrentContext();
    }
}

function handleUndo() {
    if (!appState.playerMoves.length) {
        showToast('There are no moves to undo.');
        return;
    }

    appState.playerMoves = appState.playerMoves.slice(0, -1);
    appState.playerTrace = buildTrace(appState.playerMoves);
    appState.playerVisibleTrace = buildTrace(appState.playerMoves, { visible: true });
    renderPlayerSequence();
    renderCurrentTopFace();

    if (appState.debugOpen && appState.debugTraceKind === 'player') {
        appState.debugStep = Math.min(appState.debugStep, appState.playerTrace.states.length - 1);
        renderDebugPanel();
    } else {
        syncCubeToCurrentContext();
    }
}

function handleClear() {
    appState.playerMoves = [];
    appState.playerTrace = buildTrace([]);
    appState.playerVisibleTrace = buildTrace([], { visible: true });
    renderPlayerSequence();
    renderCurrentTopFace();

    if (appState.debugOpen && appState.debugTraceKind === 'player') {
        appState.debugStep = 0;
        renderDebugPanel();
    } else {
        syncCubeToCurrentContext();
    }
}

function handleSubmit() {
    if (!appState.currentTask) {
        return;
    }

    const target = appState.currentTask.targetTopFace;
    const finalFace = getCurrentObservedFace({ visible: false, includeInitial: true });
    const visibleFinalFace = getCurrentObservedFace({ visible: true, includeInitial: true });
    const matched = compareFaces(finalFace, target);
    const patternMatched = compareFacePatterns(finalFace, target);
    const referenceMoves = appState.currentTask.answers?.directions ?? [];

    appState.lastResult = {
        matched,
        patternMatched,
        finalFace,
        visibleFinalFace,
        target,
        referenceMoves
    };

    renderResultModal();
}

function renderResultModal() {
    if (!appState.lastResult) {
        return;
    }

    const { matched, patternMatched, finalFace, visibleFinalFace, target, referenceMoves } = appState.lastResult;
    const displayFace = visibleFinalFace ?? finalFace;
    els.resultTitle.textContent = matched ? 'Correct' : 'Not Yet';
    els.resultText.textContent = matched
        ? `Your ${appState.playerMoves.length}-move sequence reaches the target top face exactly.`
        : patternMatched
            ? 'The final top-face pattern is correct, but the orientation is still wrong.'
            : 'Your current roll sequence does not reach the target top face yet.';

    renderFaceCanvas(els.resultPlayerFace, displayFace, '#241F49');
    renderFaceCanvas(els.resultTargetFace, target, '#241F49');
    els.resultPlayerMeta.textContent = displayFace ? formatFaceDetails(displayFace) : 'No final state.';
    els.resultTargetFaceMeta.textContent = formatFaceDetails(target);
    els.referenceSequenceBox.innerHTML = `
        <div><strong>Your sequence:</strong> ${formatDirectionSequence(appState.playerMoves)}</div>
        <div><strong>Reference status:</strong> ${
            hasReferenceTrace(appState.currentTask)
                ? formatDirectionSequence(referenceMoves)
                : 'Reference directions are disabled for this validator-only task.'
        }</div>
    `;

    els.resultModal.classList.remove('hidden');
}

function closeResultModal() {
    els.resultModal.classList.add('hidden');
}

function openDebug(kind) {
    if (!appState.currentTask) {
        return;
    }

    if (kind === 'answer' && !appState.referenceTrace) {
        showToast('This task does not expose a reference sequence.');
        return;
    }

    appState.debugOpen = true;
    appState.debugTraceKind = kind;
    appState.debugStep = 0;
    renderDebugPanel();
}

function closeDebug() {
    appState.debugOpen = false;
    els.debugPanel.classList.add('hidden');
    syncCubeToCurrentContext();
}

function switchDebugTrace(kind) {
    if (kind === 'answer' && !appState.referenceTrace) {
        return;
    }

    if (!appState.debugOpen) {
        openDebug(kind);
        return;
    }

    appState.debugTraceKind = kind;
    appState.debugStep = 0;
    renderDebugPanel();
}

function stepDebug(offset) {
    if (!appState.debugOpen) {
        return;
    }

    const trace = getActiveDebugTrace();
    const maxStep = Math.max((trace?.states?.length ?? 1) - 1, 0);
    appState.debugStep = Math.max(0, Math.min(maxStep, appState.debugStep + offset));
    renderDebugPanel();
}

function renderDebugPanel() {
    const trace = getActiveDebugTrace();
    if (!trace) {
        return;
    }

    appState.debugOpen = true;
    els.debugPanel.classList.remove('hidden');
    els.debugPlayerTab.classList.toggle('active', appState.debugTraceKind === 'player');
    els.debugAnswerTab.classList.toggle('active', appState.debugTraceKind === 'answer');

    const step = Math.max(0, Math.min(appState.debugStep, trace.states.length - 1));
    appState.debugStep = step;
    const currentState = trace.states[step];
    const currentFace = extractTopFace(currentState);
    const traceLabel = appState.debugTraceKind === 'player' ? 'your sequence' : 'the reference sequence';

    els.debugStepText.textContent = step === 0
        ? `Inspecting the initial state for ${traceLabel}.`
        : `Inspecting step ${step}: ${getDirectionLabel(trace.moves[step - 1])}.`;

    renderFaceCanvas(els.debugCurrentFace, currentFace, '#241F49');
    renderFaceCanvas(els.debugTargetFace, appState.currentTask.targetTopFace, '#241F49');
    els.debugCurrentMeta.textContent = formatFaceDetails(currentFace);
    els.debugTargetMeta.textContent = formatFaceDetails(appState.currentTask.targetTopFace);
    renderDirectionSequence(trace.moves, els.debugSequence, step);

    els.debugPrevBtn.disabled = step <= 0;
    els.debugNextBtn.disabled = step >= trace.states.length - 1;

    renderCubeState(currentState);
}

function getActiveDebugTrace() {
    return appState.debugTraceKind === 'answer' ? appState.referenceTrace : appState.playerTrace;
}

function syncCubeToCurrentContext() {
    if (!appState.currentTask) {
        return;
    }

    if (appState.debugOpen) {
        const trace = getActiveDebugTrace();
        const state = trace?.states?.[appState.debugStep] ?? trace?.states?.[0];
        renderCubeState(state);
        return;
    }

    const currentState = appState.playerVisibleTrace?.states?.[appState.playerVisibleTrace.states.length - 1]
        ?? appState.referenceTrace?.states?.[0]
        ?? buildTrace([], { visible: true }).states[0];
    renderCubeState(currentState);
}

function renderCubeState(cubeState) {
    if (!cubeState || !appState.cubeRenderer) {
        return;
    }

    if (!appState.cubeRenderer.cubeMesh) {
        appState.cubeRenderer.createCube(cubeState);
    } else {
        appState.cubeRenderer.updateTextures(cubeState);
    }
}

function buildVisibleCubeFaceMap(task) {
    const faces = task?.initialCube?.solutionFaces ?? {};
    return {
        TOP: normalizeFace(faces.TOP ?? { patternId: '?', rotation: 0 }),
        BOTTOM: normalizeFace(faces.BOTTOM ?? { patternId: '?', rotation: 0 }),
        FRONT: normalizeFace(faces.FRONT ?? { patternId: '?', rotation: 0 }),
        BACK: normalizeFace(faces.BACK ?? { patternId: '?', rotation: 0 }),
        LEFT: normalizeFace(faces.LEFT ?? { patternId: '?', rotation: 0 }),
        RIGHT: normalizeFace(faces.RIGHT ?? { patternId: '?', rotation: 0 })
    };
}

function buildTrace(directions, options = {}) {
    if (!appState.currentTask) {
        return { moves: [], states: [], observedFaces: [] };
    }

    const faceMap = buildVisibleCubeFaceMap(appState.currentTask);
    const initialState = cubeFromSolutionFaces(faceMap);
    const states = simulatePathStates(initialState, directions);
    const observedFaces = states.map((cubeState) => extractTopFace(cubeState));

    return {
        moves: directions.slice(),
        states,
        observedFaces
    };
}

function extractTopFace(cubeState) {
    if (!cubeState?.top) {
        return null;
    }
    return normalizeFace(cubeState.top);
}

function getCurrentObservedFace(options = {}) {
    const trace = options.visible ? appState.playerVisibleTrace : appState.playerTrace;
    if (!trace?.observedFaces?.length) {
        return null;
    }
    if (options.includeInitial) {
        return trace.observedFaces[trace.observedFaces.length - 1];
    }
    return trace.observedFaces[trace.observedFaces.length - 1];
}

function normalizeFace(face) {
    return {
        patternId: String(face?.patternId ?? '?'),
        rotation: normalizeRotation(face?.rotation ?? 0)
    };
}

function compareFaces(left, right) {
    if (!left || !right) {
        return false;
    }

    return String(left.patternId) === String(right.patternId)
        && normalizeRotation(left.rotation ?? 0) === normalizeRotation(right.rotation ?? 0);
}

function compareFacePatterns(left, right) {
    if (!left || !right) {
        return false;
    }
    return String(left.patternId) === String(right.patternId);
}

function formatFaceDetails(face) {
    if (!face) {
        return 'No face data.';
    }

    return `${face.patternId} - ${normalizeRotation(face.rotation ?? 0)}`;
}

function getDirectionLabel(direction) {
    return appState.currentTask?.instructions?.directionVocabulary?.[direction]
        || appState.currentTask?.instructions?.directionVocabularyZh?.[direction]
        || DIRECTION_META[direction]?.label
        || direction;
}

function formatDirectionSequence(moves) {
    if (!moves?.length) {
        return '(empty)';
    }
    return moves.map((direction, index) => `${index + 1}.${DIRECTION_META[direction]?.arrow ?? direction} ${getDirectionLabel(direction)}`).join('  ');
}

function renderPlayerSequence(activeStep = null, container = els.playerSequence, moves = appState.playerMoves) {
    renderDirectionSequence(moves, container, activeStep);
}

function renderDirectionSequence(moves, container, activeStep = null) {
    container.innerHTML = '';

    if (!moves?.length) {
        container.classList.add('empty');
        container.textContent = 'No moves yet.';
        return;
    }

    container.classList.remove('empty');
    moves.forEach((direction, index) => {
        const chip = document.createElement('div');
        chip.className = 'sequence-chip';
        if (activeStep !== null && activeStep === index + 1) {
            chip.classList.add('active');
        }
        chip.innerHTML = `
            <span class="chip-index">${index + 1}.</span>
            <span>${DIRECTION_META[direction]?.arrow ?? direction}</span>
            <span>${getDirectionLabel(direction)}</span>
        `;
        container.appendChild(chip);
    });
}

function hasReferenceTrace(task) {
    return Boolean(task?.answers?.referenceValid && task?.answers?.directions?.length);
}

function showLevelScreen() {
    closeDebug();
    closeResultModal();
    appState.currentTask = null;
    appState.lastResult = null;
    els.gameScreen.classList.add('hidden');
    els.levelScreen.classList.remove('hidden');
}

function goToNextLevel() {
    if (appState.currentTaskIndex < 0 || appState.currentTaskIndex >= appState.levelCodes.length - 1) {
        showToast('This is already the last level.');
        return;
    }

    const nextCode = appState.levelCodes[appState.currentTaskIndex + 1];
    closeResultModal();
    openLevel(nextCode).catch((error) => {
        console.error(error);
        showToast(`Failed to load the next level: ${error.message}`);
    });
}

function handleResize() {
    if (!appState.cubeRenderer) {
        return;
    }
    const rect = els.cubeContainer.getBoundingClientRect();
    const width = Math.max(320, Math.floor(rect.width || 420));
    const height = Math.max(320, Math.floor(rect.height || 420));
    appState.cubeRenderer.resize(width, height);
}

function resetCubeView() {
    if (appState.cubeRenderer) {
        appState.cubeRenderer.resetView();
    }
}

function handleKeydown(event) {
    if (els.gameScreen.classList.contains('hidden')) {
        return;
    }

    switch (event.key) {
        case 'ArrowUp':
            event.preventDefault();
            handleMove('N');
            break;
        case 'ArrowDown':
            event.preventDefault();
            handleMove('S');
            break;
        case 'ArrowLeft':
            event.preventDefault();
            handleMove('W');
            break;
        case 'ArrowRight':
            event.preventDefault();
            handleMove('E');
            break;
        case 'Escape':
            if (!els.resultModal.classList.contains('hidden')) {
                closeResultModal();
            } else if (appState.debugOpen) {
                closeDebug();
            }
            break;
        default:
            break;
    }
}

function showToast(message) {
    if (!els.toast) {
        return;
    }

    els.toast.textContent = message;
    els.toast.classList.add('visible');
    window.clearTimeout(appState.toastTimer);
    appState.toastTimer = window.setTimeout(() => {
        els.toast.classList.remove('visible');
    }, 2200);
}
