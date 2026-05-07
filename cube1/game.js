/**
 * Main Game Controller
 * Supports two modes:
 *   - forward: given a path, guess the bottom face at each step
 *   - reverse: given a target bottom-face sequence, design a rolling path
 */

const GAME_MODES = {
    forward: {
        label: '正向推理',
        intro: '给定展开图和滚动路径，预测每一步底面图案与朝向。',
        gridTitle: '已知滚动路径',
        revealLabel: '查看结果'
    },
    reverse: {
        label: '逆向设计',
        intro: '给定一个可达成的目标底面序列，设计滚动方式让它按顺序出现。',
        gridTitle: '逆向任务',
        revealLabel: '检查路径'
    }
};

const DIR_META = {
    N: { arrow: '↑', short: '上滚', long: '向上滚动' },
    S: { arrow: '↓', short: '下滚', long: '向下滚动' },
    E: { arrow: '→', short: '右滚', long: '向右滚动' },
    W: { arrow: '←', short: '左滚', long: '向左滚动' }
};

GAME_MODES.forward = {
    label: '正向推理',
    intro: '给定立方体展开图和滚动路径，预测每一步底面图案与朝向。',
    gridTitle: '已知滚动路径',
    revealLabel: '查看结果'
};

GAME_MODES.reverse = {
    label: '逆向设计',
    intro: '给定一个可达成的底面图案序列，设计滚动路径让它按顺序出现。',
    gridTitle: '逆向任务',
    revealLabel: '检查路径'
};

GAME_MODES.reconstruct = {
    label: '立方体还原',
    intro: '给定固定滚动序列和观测到底面的图案序列，反推出这个未知立方体各个面的图案分布。',
    gridTitle: '立方体还原任务',
    revealLabel: '检查还原'
};

DIR_META.N = { arrow: '↑', short: '上滚', long: '向上滚动' };
DIR_META.S = { arrow: '↓', short: '下滚', long: '向下滚动' };
DIR_META.E = { arrow: '→', short: '右滚', long: '向右滚动' };
DIR_META.W = { arrow: '←', short: '左滚', long: '向左滚动' };

GAME_MODES.reconstruct = {
    label: '立方体还原',
    intro: '给定固定滚动序列和从正上方看到的路径图案序列，还原立方体六个面的图案与朝向。',
    gridTitle: '还原任务',
    revealLabel: '检查还原'
};

const RECONSTRUCTION_UNKNOWN = '?';
const RECONSTRUCTION_SLOT_LABELS = {
    TOP: '顶面',
    BOTTOM: '底面',
    FRONT: '前面',
    BACK: '后面',
    LEFT: '左面',
    RIGHT: '右面'
};
const RECONSTRUCTION_NET_SLOTS = [
    { key: 'BACK', netIndex: 3, col: 2, row: 1 },
    { key: 'LEFT', netIndex: 4, col: 1, row: 2 },
    { key: 'TOP', netIndex: 0, col: 2, row: 2 },
    { key: 'RIGHT', netIndex: 2, col: 3, row: 2 },
    { key: 'FRONT', netIndex: 1, col: 2, row: 3 },
    { key: 'BOTTOM', netIndex: 5, col: 2, row: 4 }
];

class Game {
    constructor() {
        this.gameMode = 'reconstruct';
        this.currentLevel = null;
        this.levelIndex = -1;

        this.initialCube = null;
        this.cubeState = null;
        this.cubeStates = [];
        this.pathResults = [];

        this.playerAnswers = [];
        this.playerMoves = [];
        this.reconstructionAnswers = {};
        this.reconstructionRotations = {};
        this.reconstructionData = null;
        this.reconstructionValidationStates = [];
        this.reconstructionValidationStampFaces = [];
        this.validationStepIndex = 0;

        this.currentStep = 0;
        this.isRevealed = false;
        this.score = 0;
        this.totalSteps = 0;

        this.cubeRenderer = null;

        this.el = {
            levelSelect: document.getElementById('level-select'),
            levelList: document.getElementById('level-list'),
            gameArea: document.getElementById('game-area'),
            mainContent: document.querySelector('.main-content'),
            levelTitle: document.getElementById('level-title'),
            levelDesc: document.getElementById('level-desc'),
            stepIndicator: document.getElementById('step-indicator'),
            stepHint: document.getElementById('step-hint'),
            gridPanelTitle: document.getElementById('grid-panel-title'),
            modeIntro: document.getElementById('mode-intro'),
            backToLevels: document.getElementById('back-to-levels'),
            reverseTaskPanel: document.getElementById('reverse-task-panel'),
            reconstructionTaskPanel: document.getElementById('reconstruction-task-panel'),

            cubeView: document.getElementById('cube-3d-container'),
            netCanvas: document.getElementById('net-canvas'),
            reconstructionNet: document.getElementById('reconstruction-net'),
            gridCanvas: document.getElementById('grid-canvas'),

            forwardControls: document.getElementById('forward-controls'),
            reverseControls: document.getElementById('reverse-controls'),
            reconstructionControls: document.getElementById('reconstruction-controls'),
            patternPalette: document.getElementById('pattern-palette'),
            rotationControl: document.getElementById('rotation-control'),
            answerPreview: document.getElementById('answer-preview'),
            selectedInfo: document.getElementById('selected-info'),
            targetSequence: document.getElementById('target-sequence'),
            movePreview: document.getElementById('move-preview'),
            undoMoveBtn: document.getElementById('undo-move-btn'),
            resetMovesBtn: document.getElementById('reset-moves-btn'),
            reconstructionDirections: document.getElementById('reconstruction-directions'),
            reconstructionObservedSequence: document.getElementById('reconstruction-observed-sequence'),
            reconstructionPalette: document.getElementById('reconstruction-palette'),
            reconstructionRotationControl: document.getElementById('reconstruction-rotation-control'),
            reconstructionSelectedInfo: document.getElementById('reconstruction-selected-info'),
            reconstructionValidatorPanel: document.getElementById('reconstruction-validator-panel'),
            validatorStepInfo: document.getElementById('validator-step-info'),
            validatorStepFace: document.getElementById('validator-step-face'),
            validatorPrevBtn: document.getElementById('validator-prev-btn'),
            validatorNextBtn: document.getElementById('validator-next-btn'),
            validatorResetViewBtn: document.getElementById('validator-reset-view-btn'),

            submitBtn: document.getElementById('submit-btn'),
            revealBtn: document.getElementById('reveal-btn'),
            validatorOpenBtn: document.getElementById('validator-open-btn'),
            restartBtn: document.getElementById('restart-btn'),
            nextLevelBtn: document.getElementById('next-level-btn'),
            resultPanel: document.getElementById('result-panel'),
            scoreDisplay: document.getElementById('score-display')
        };

        this.selectedPattern = null;
        this.selectedRotation = 0;

        this.init();
    }

    init() {
        if (typeof syncActiveLevelsForMode === 'function') {
            syncActiveLevelsForMode(this.gameMode);
        }
        this.ensureReconstructionRotationPlacement();
        this.buildLevelSelect();
        this.setupEventListeners();
        this.syncModeUI();
        this.showLevelSelect();
    }

    ensureReconstructionRotationPlacement() {
        const control = this.el.reconstructionRotationControl;
        const controlsContainer = this.el.reconstructionControls;

        if (!control || !controlsContainer) return;

        const rotationCard = control.closest('.panel-card');
        if (!rotationCard || controlsContainer.contains(rotationCard)) return;

        const anchorCard = controlsContainer.querySelector('.answer-preview-card');
        if (anchorCard) {
            controlsContainer.insertBefore(rotationCard, anchorCard);
        } else {
            controlsContainer.appendChild(rotationCard);
        }
    }

    setupEventListeners() {
        document.querySelectorAll('.mode-btn').forEach((btn) => {
            btn.addEventListener('click', () => this.setMode(btn.dataset.mode));
        });

        this.el.rotationControl.querySelectorAll('.rot-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                if (this.gameMode !== 'forward' || this.isRevealed) return;
                this.selectedRotation = parseInt(btn.dataset.rotation, 10);
                this.el.rotationControl.querySelectorAll('.rot-btn').forEach((item) => {
                    item.classList.toggle('active', item === btn);
                });
                this.updateAnswerPreview();
            });
        });

        this.el.reconstructionRotationControl.querySelectorAll('.reconstruction-rot-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                if (this.gameMode !== 'reconstruct' || this.isRevealed) return;
                this.selectedRotation = parseInt(btn.dataset.rotation, 10);
                this.syncReconstructionRotationButtons();
                this.updateAnswerPreview();
            });
        });

        document.querySelectorAll('.move-btn').forEach((btn) => {
            btn.addEventListener('click', () => this.handleMoveInput(btn.dataset.direction));
        });

        this.el.submitBtn.addEventListener('click', () => this.submitAnswer());
        this.el.revealBtn.addEventListener('click', () => this.revealAnswers());
        if (this.el.validatorOpenBtn) {
            this.el.validatorOpenBtn.addEventListener('click', () => this.openReconstructionValidator());
        }
        this.el.restartBtn.addEventListener('click', () => this.startLevel(this.levelIndex));
        this.el.nextLevelBtn.addEventListener('click', () => this.goNextLevel());
        this.el.backToLevels.addEventListener('click', () => this.showLevelSelect());
        this.el.undoMoveBtn.addEventListener('click', () => this.undoMove());
        this.el.resetMovesBtn.addEventListener('click', () => this.resetMoves());
        this.el.reconstructionNet.addEventListener('click', (event) => this.handleReconstructionNetClick(event));
        if (this.el.validatorPrevBtn) {
            this.el.validatorPrevBtn.addEventListener('click', () => this.stepReconstructionValidator(-1));
        }
        if (this.el.validatorNextBtn) {
            this.el.validatorNextBtn.addEventListener('click', () => this.stepReconstructionValidator(1));
        }
        if (this.el.validatorResetViewBtn) {
            this.el.validatorResetViewBtn.addEventListener('click', () => this.resetReconstructionValidatorView());
        }
    }

    setMode(mode) {
        mode = 'reconstruct';
        if (!GAME_MODES[mode] || mode === this.gameMode) {
            this.syncModeUI();
            return;
        }

        this.gameMode = mode;
        if (typeof syncActiveLevelsForMode === 'function') {
            syncActiveLevelsForMode(this.gameMode);
        }
        this.syncModeUI();
        this.buildLevelSelect();

        if (this.currentLevel) {
            const nextIndex = LEVELS.length ? Math.min(this.levelIndex, LEVELS.length - 1) : -1;
            if (nextIndex >= 0) {
                this.startLevel(nextIndex);
            } else {
                this.showLevelSelect();
            }
        }
    }

    syncModeUI() {
        document.querySelectorAll('.mode-btn').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.mode === this.gameMode);
        });

        if (this.el.modeIntro) {
            this.el.modeIntro.textContent = GAME_MODES[this.gameMode].intro;
        }

        if (this.el.gridPanelTitle) {
            this.el.gridPanelTitle.textContent = GAME_MODES[this.gameMode].gridTitle;
        }

        if (this.el.revealBtn) {
            this.el.revealBtn.textContent = GAME_MODES[this.gameMode].revealLabel;
        }
    }

    showLevelSelect() {
        this.el.levelSelect.classList.remove('hidden');
        this.el.gameArea.classList.add('hidden');
        this.el.resultPanel.classList.add('hidden');
        this.syncModeUI();
        this.buildLevelSelect();
    }

    buildLevelSelect() {
        const list = this.el.levelList;
        list.innerHTML = '';

        if (!LEVELS.length) {
            const empty = document.createElement('div');
            empty.className = 'level-empty';
            empty.textContent = '暂无可用关卡，请先生成并加载关卡数据。';
            list.appendChild(empty);
            return;
        }

        this.getGroupedLevels().forEach((group) => {
            const section = document.createElement('section');
            section.className = 'level-group';

            const header = document.createElement('div');
            header.className = 'level-group-header';
            header.innerHTML = `
                <div class="level-group-title">${group.label}</div>
                <div class="level-group-desc">${group.description}</div>
            `;

            const grid = document.createElement('div');
            grid.className = 'level-group-grid';
            group.items.forEach(({ level, index }) => {
                grid.appendChild(this.createLevelCard(level, index));
            });

            section.appendChild(header);
            section.appendChild(grid);
            list.appendChild(section);
        });
    }

    getGroupedLevels() {
        const indexedLevels = LEVELS.map((level, index) => ({ level, index }));
        const metaGroups = window.LEVELS_META?.groups || [];

        if (metaGroups.length) {
            const grouped = metaGroups
                .map((group) => ({
                    ...group,
                    items: indexedLevels.filter(({ level }) => {
                        const moveCount = level.moveCount ?? level.path.length;
                        return moveCount >= group.minMoves && moveCount <= group.maxMoves;
                    })
                }))
                .filter((group) => group.items.length > 0);

            if (grouped.length) return grouped;
        }

        return [{
            label: '全部关卡',
            description: '按编号顺序选择',
            items: indexedLevels
        }];
    }

    createLevelCard(level, index) {
        const card = document.createElement('div');
        card.className = 'level-card';
        card.dataset.levelIndex = index;

        const moveCount = level.moveCount ?? level.path.length;
        const stars = '★'.repeat(level.difficulty) + '☆'.repeat(5 - level.difficulty);
        const stepText = this.gameMode === 'forward'
            ? `预测 ${moveCount + 1} 个底面`
            : `设计 ${moveCount} 步滚动`;
        const modeTag = this.gameMode === 'forward' ? '正向' : '逆向';

        card.innerHTML = `
            <div class="level-card-number">${level.id}</div>
            <div class="level-card-mode">${modeTag}</div>
            <div class="level-card-name">${level.name}</div>
            <div class="level-card-desc">${this.getLevelCardDescription(level)}</div>
            <div class="level-card-stars">${stars}</div>
            <div class="level-card-steps">${stepText}</div>
        `;

        const reconstructSummary = this.getReconstructionSummary(level);
        const meta = this.getLevelCardMeta(level, reconstructSummary);
        card.querySelector('.level-card-mode').textContent = meta.modeTag;
        card.querySelector('.level-card-desc').textContent = meta.description;
        card.querySelector('.level-card-stars').textContent = '★'.repeat(level.difficulty) + '☆'.repeat(5 - level.difficulty);
        card.querySelector('.level-card-steps').textContent = meta.stepText;

        card.addEventListener('click', () => this.startLevel(index));
        return card;
    }

    getLevelCardDescription(level) {
        if (this.gameMode === 'forward') {
            return level.description;
        }
        return `${level.description} · 根据目标底面序列设计路径`;
    }

    getLevelCardMeta(level, reconstructSummary = this.getReconstructionSummary(level)) {
        const moveCount = level.moveCount ?? level.path.length;

        if (this.gameMode === 'reverse') {
            return {
                modeTag: '逆向',
                description: `${level.description}，根据目标底面序列设计一条可达成的滚动路径。`,
                stepText: `设计 ${moveCount} 步滚动`
            };
        }

        if (this.gameMode === 'reconstruct') {
            return {
                modeTag: '还原',
                description: `${level.description}，根据底面观测结果还原未知立方体，最多可还原 ${reconstructSummary.requiredCount} 个确定面。`,
                stepText: `观察 ${moveCount} 次 · 至少可确定 ${reconstructSummary.requiredCount} 面`
            };
        }

        return {
            modeTag: '正向',
            description: level.description,
            stepText: `预测 ${moveCount + 1} 个底面`
        };
    }

    getReconstructionSummary(level) {
        return {
            observedCount: level.path.length,
            requiredCount: Number.isFinite(Number(level.prompt?.requiredCount))
                ? Number(level.prompt.requiredCount)
                : [...new Set(
                    simulatePath(this.createSlotTrackingCube(), level.path)
                        .slice(1)
                        .map((face) => face.patternId)
                )].length
        };
    }

    startLevel(levelIndex) {
        this.currentLevel = LEVELS[levelIndex];
        this.levelIndex = levelIndex;
        this.isRevealed = false;
        this.score = 0;

        this.initialCube = cubeFromNet(
            Array.isArray(this.currentLevel.netFaces) && this.currentLevel.netFaces.length
                ? this.currentLevel.netFaces
                : this.currentLevel.netPatterns
        );
        this.initialCube.x = this.currentLevel.startX;
        this.initialCube.y = this.currentLevel.startY;

        this.pathResults = Array.isArray(this.currentLevel.gtBottomFaces) && this.currentLevel.gtBottomFaces.length
            ? this.currentLevel.gtBottomFaces.map((face) => ({ ...face }))
            : simulatePath(this.initialCube, this.currentLevel.path);

        if (this.gameMode === 'forward') {
            this.initForwardLevelState();
        } else if (this.gameMode === 'reverse') {
            this.initReverseLevelState();
        } else {
            this.initReconstructionLevelState();
        }

        this.el.levelSelect.classList.add('hidden');
        this.el.gameArea.classList.remove('hidden');
        this.el.resultPanel.classList.add('hidden');

        this.el.levelTitle.textContent = `关卡 ${this.currentLevel.id}: ${this.currentLevel.name} · ${GAME_MODES[this.gameMode].label}`;
        this.el.levelDesc.textContent = this.getInGameLevelDescription();

        this.syncModeUI();
        this.configureModePanels();
        this.initCubeRenderer();
        this.refreshModeView();
    }

    initForwardLevelState() {
        this.cubeStates = [];
        const tempCube = this.initialCube.clone();
        this.cubeStates.push(tempCube.clone());

        for (const dir of this.currentLevel.path) {
            tempCube.roll(dir);
            this.cubeStates.push(tempCube.clone());
        }

        this.cubeState = this.cubeStates[0].clone();
        this.playerAnswers = new Array(this.pathResults.length).fill(null);
        this.playerMoves = [];
        this.reconstructionAnswers = {};
        this.reconstructionRotations = {};
        this.reconstructionData = null;
        this.totalSteps = this.pathResults.length;
        this.currentStep = 0;
        this.selectedPattern = null;
        this.selectedRotation = 0;
    }

    initReverseLevelState() {
        this.cubeState = this.initialCube.clone();
        this.cubeStates = [this.cubeState.clone()];
        this.playerAnswers = [];
        this.playerMoves = [];
        this.reconstructionAnswers = {};
        this.reconstructionRotations = {};
        this.reconstructionData = null;
        this.totalSteps = this.currentLevel.path.length;
        this.currentStep = 0;
        this.selectedPattern = null;
        this.selectedRotation = 0;
    }

    initReconstructionLevelState() {
        this.cubeState = this.initialCube.clone();
        this.cubeStates = [this.cubeState.clone()];
        this.playerAnswers = [];
        this.playerMoves = [];
        this.reconstructionData = this.buildReconstructionData();
        this.reconstructionAnswers = {};
        this.reconstructionRotations = {};
        this.reconstructionValidationStates = [];
        this.reconstructionValidationStampFaces = [];
        this.validationStepIndex = 0;
        RECONSTRUCTION_NET_SLOTS.forEach((slot) => {
            this.reconstructionAnswers[slot.key] = null;
            this.reconstructionRotations[slot.key] = 0;
        });
        this.totalSteps = RECONSTRUCTION_NET_SLOTS.length;
        this.currentStep = 0;
        this.selectedPattern = null;
        this.selectedRotation = 0;
    }

    createSlotTrackingCube() {
        return new CubeState([
            { patternId: 'TOP', rotation: 0 },
            { patternId: 'BOTTOM', rotation: 0 },
            { patternId: 'FRONT', rotation: 0 },
            { patternId: 'BACK', rotation: 0 },
            { patternId: 'LEFT', rotation: 0 },
            { patternId: 'RIGHT', rotation: 0 }
        ]);
    }

    buildReconstructionData() {
        const slotCube = this.createSlotTrackingCube();
        const slotResults = simulatePath(slotCube, this.currentLevel.path);
        const slotSequence = slotResults.slice(1).map((face) => face.patternId);
        const observedFaces = this.pathResults.slice(1).map((face) => ({
            patternId: face.patternId,
            rotation: face.rotation
        }));
        const requiredSlots = [...new Set(slotSequence)];

        return {
            directions: [...this.currentLevel.path],
            observedFaces,
            slotSequence,
            requiredSlots,
            requiredSlotSet: new Set(requiredSlots),
            actualFaces: this.getSlotFaceMap(),
            actualPatterns: this.getSlotPatternMap(),
            palettePatterns: [...new Set(observedFaces.map((face) => face.patternId))]
        };
    }

    getSlotPatternMap(level = this.currentLevel) {
        const solutionFaces = level.answers?.solutionFaces || level.solutionFaces;
        if (solutionFaces) {
            return {
                TOP: solutionFaces.TOP?.patternId,
                FRONT: solutionFaces.FRONT?.patternId,
                RIGHT: solutionFaces.RIGHT?.patternId,
                BACK: solutionFaces.BACK?.patternId,
                LEFT: solutionFaces.LEFT?.patternId,
                BOTTOM: solutionFaces.BOTTOM?.patternId
            };
        }

        return {
            TOP: level.netPatterns[0],
            FRONT: level.netPatterns[1],
            RIGHT: level.netPatterns[2],
            BACK: level.netPatterns[3],
            LEFT: level.netPatterns[4],
            BOTTOM: level.netPatterns[5]
        };
    }

    getSlotFaceMap() {
        const solutionFaces = this.currentLevel?.answers?.solutionFaces || this.currentLevel?.solutionFaces;
        if (solutionFaces) {
            return {
                TOP: { ...solutionFaces.TOP },
                BOTTOM: { ...solutionFaces.BOTTOM },
                FRONT: { ...solutionFaces.FRONT },
                BACK: { ...solutionFaces.BACK },
                LEFT: { ...solutionFaces.LEFT },
                RIGHT: { ...solutionFaces.RIGHT }
            };
        }

        return {
            TOP: { patternId: this.initialCube.top.patternId, rotation: this.initialCube.top.rotation },
            BOTTOM: { patternId: this.initialCube.bottom.patternId, rotation: this.initialCube.bottom.rotation },
            FRONT: { patternId: this.initialCube.front.patternId, rotation: this.initialCube.front.rotation },
            BACK: { patternId: this.initialCube.back.patternId, rotation: this.initialCube.back.rotation },
            LEFT: { patternId: this.initialCube.left.patternId, rotation: this.initialCube.left.rotation },
            RIGHT: { patternId: this.initialCube.right.patternId, rotation: this.initialCube.right.rotation }
        };
    }

    getInGameLevelDescription() {
        if (this.gameMode === 'reconstruct') {
            return `${this.currentLevel.description}，系统会给出固定滚动序列和观测到底面的图案序列。请把能确定的面填到左侧展开图里，无法确定的面可以填 ?。`;
        }

        if (this.gameMode === 'reverse') {
            return `${this.currentLevel.description}，只根据目标图案序列设计滚动方式，不需要考虑棋盘位置，也不考察图案朝向。`;
        }

        if (this.gameMode === 'forward') {
            return this.currentLevel.description;
        }
        return `${this.currentLevel.description} · 只根据目标图案序列设计滚动方式，不需要考虑棋盘位置，也不需要考虑图案朝向，逆向题允许多解。`;
    }

    configureModePanels() {
        const isForward = this.gameMode === 'forward';
        const isReverse = this.gameMode === 'reverse';
        const isReconstruct = this.gameMode === 'reconstruct';

        this.el.forwardControls.classList.toggle('hidden', !isForward);
        this.el.reverseControls.classList.toggle('hidden', !isReverse);
        this.el.reconstructionControls.classList.toggle('hidden', !isReconstruct);
        if (this.el.reconstructionValidatorPanel) {
            this.el.reconstructionValidatorPanel.classList.toggle('hidden', !isReconstruct || !this.isRevealed);
        }

        this.el.netCanvas.classList.toggle('hidden', isReconstruct);
        this.el.reconstructionNet.classList.toggle('hidden', !isReconstruct);

        this.el.gridCanvas.classList.toggle('hidden', !isForward);
        this.el.reverseTaskPanel.classList.toggle('hidden', !isReverse);
        this.el.reconstructionTaskPanel.classList.toggle('hidden', !isReconstruct);

        this.el.submitBtn.classList.toggle('hidden', isReverse);
        this.el.submitBtn.textContent = isReconstruct ? '清空展开图' : '提交答案';
        this.el.revealBtn.textContent = GAME_MODES[this.gameMode].revealLabel;
        this.el.mainContent.classList.toggle('reconstruct-layout', isReconstruct);

        if (isForward) {
            this.buildPatternPalette();
        } else {
            this.el.patternPalette.innerHTML = '';
        }

        if (isReconstruct) {
            this.buildReconstructionPalette();
            this.syncReconstructionRotationButtons();
        } else {
            this.el.reconstructionPalette.innerHTML = '';
            this.el.reconstructionDirections.innerHTML = '';
            this.el.reconstructionObservedSequence.innerHTML = '';
        }

        if (!isReverse) {
            this.el.targetSequence.innerHTML = '';
            this.el.movePreview.innerHTML = '';
        }

        return;
    }

    refreshModeView() {
        this.drawNet();
        this.drawGrid();
        this.updateAnswerPreview();
        this.renderTargetSequence();
        this.renderMovePreview();
        this.renderReconstructionChallenge();
        this.updateStepUI();
    }

    initCubeRenderer() {
        const legacyContainer = this.el.cubeView;
        legacyContainer.innerHTML = '';

        const legacyWidth = legacyContainer.clientWidth || 300;
        const legacyHeight = legacyContainer.clientHeight || 300;
        this.cubeRenderer = new CubeRenderer(legacyContainer, legacyWidth, legacyHeight);
        this.cubeRenderer.createCube(this.getDisplayCubeState());
        this.cubeRenderer.setDirectionGuideVisible(this.gameMode !== 'forward');
        return;
    }

    getDisplayCubeState() {
        if (this.gameMode === 'reconstruct') {
            return this.getReconstructionCubeState();
        }

        if (this.gameMode === 'forward') {
            const index = Math.min(this.currentStep, this.cubeStates.length - 1);
            return this.cubeStates[index];
        }
        return this.cubeStates[this.cubeStates.length - 1];
    }

    getMaskedCubeState(sourceCube) {
        const masked = sourceCube.clone();
        masked.faces = masked.faces.map((face) => ({
            ...face,
            patternId: RECONSTRUCTION_UNKNOWN,
            rotation: 0
        }));
        return masked;
    }

    getReconstructionCubeState() {
        if (!this.initialCube) {
            return this.getMaskedCubeState(new CubeState([
                { patternId: RECONSTRUCTION_UNKNOWN, rotation: 0 },
                { patternId: RECONSTRUCTION_UNKNOWN, rotation: 0 },
                { patternId: RECONSTRUCTION_UNKNOWN, rotation: 0 },
                { patternId: RECONSTRUCTION_UNKNOWN, rotation: 0 },
                { patternId: RECONSTRUCTION_UNKNOWN, rotation: 0 },
                { patternId: RECONSTRUCTION_UNKNOWN, rotation: 0 }
            ]));
        }

        const cube = this.initialCube.clone();
        const faceIndexMap = {
            TOP: 0,
            BOTTOM: 1,
            FRONT: 2,
            BACK: 3,
            LEFT: 4,
            RIGHT: 5
        };

        Object.entries(faceIndexMap).forEach(([slotKey, faceIndex]) => {
            const actualFace = this.reconstructionData.actualFaces[slotKey];
            const patternId = this.isRevealed
                ? actualFace.patternId
                : (this.reconstructionAnswers[slotKey] || RECONSTRUCTION_UNKNOWN);
            const rotation = this.isRevealed
                ? actualFace.rotation
                : (this.reconstructionAnswers[slotKey] ? this.reconstructionRotations[slotKey] : 0);

            cube.faces[faceIndex] = {
                patternId,
                rotation: patternId === RECONSTRUCTION_UNKNOWN ? 0 : rotation
            };
        });

        return cube;
    }

    updateCubeRendererState() {
        if (!this.cubeRenderer) return;
        this.cubeRenderer.resetTransform();
        this.cubeRenderer.updateTextures(this.getDisplayCubeState());
    }

    drawNet() {
        if (this.gameMode === 'reconstruct') {
            this.renderReconstructionNet();
            return;
        }

        const canvas = this.el.netCanvas;
        const ctx = canvas.getContext('2d');
        const cellSize = 60;
        const pad = 10;

        canvas.width = cellSize * 4 + pad * 2;
        canvas.height = cellSize * 4 + pad * 2;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const netPositions = [
            { index: 3, col: 1, row: 0 },
            { index: 4, col: 0, row: 1 },
            { index: 0, col: 1, row: 1 },
            { index: 2, col: 2, row: 1 },
            { index: 1, col: 1, row: 2 },
            { index: 5, col: 1, row: 3 }
        ];

        const netFaces = Array.isArray(this.currentLevel.netFaces) && this.currentLevel.netFaces.length
            ? this.currentLevel.netFaces
            : this.currentLevel.netPatterns.map((patternId) => ({ patternId, rotation: 0 }));

        for (const pos of netPositions) {
            const x = pad + pos.col * cellSize;
            const y = pad + pos.row * cellSize;

            ctx.fillStyle = '#1e1e3a';
            ctx.fillRect(x, y, cellSize, cellSize);

            drawPattern(ctx, netFaces[pos.index].patternId, netFaces[pos.index].rotation, x, y, cellSize);

            ctx.strokeStyle = 'rgba(255,255,255,0.4)';
            ctx.lineWidth = 2;
            ctx.strokeRect(x, y, cellSize, cellSize);
        }
    }

    renderReconstructionNet() {
        const container = this.el.reconstructionNet;
        container.innerHTML = '';

        RECONSTRUCTION_NET_SLOTS.forEach((slot) => {
            const cell = document.createElement('button');
            cell.type = 'button';
            cell.className = 'reconstruction-face-slot';
            cell.dataset.slotKey = slot.key;
            cell.style.gridColumn = `${slot.col}`;
            cell.style.gridRow = `${slot.row}`;
            cell.title = RECONSTRUCTION_SLOT_LABELS[slot.key];
            cell.disabled = this.isRevealed;

            const label = document.createElement('div');
            label.className = 'reconstruction-face-label';
            label.textContent = RECONSTRUCTION_SLOT_LABELS[slot.key];
            cell.appendChild(label);

            const answerPattern = this.reconstructionAnswers[slot.key];
            const answerRotation = this.reconstructionRotations[slot.key] ?? 0;
            const actualFace = this.reconstructionData.actualFaces[slot.key];
            const displayPattern = this.isRevealed ? actualFace.patternId : answerPattern;
            const displayRotation = this.isRevealed ? actualFace.rotation : answerRotation;

            if (!this.isRevealed && answerPattern) {
                cell.classList.add('filled');
            }

            if (this.isRevealed) {
                if (this.reconstructionData.requiredSlotSet.has(slot.key)) {
                    const exact = !!answerPattern &&
                        answerPattern === actualFace.patternId &&
                        answerRotation === actualFace.rotation;
                    cell.classList.add(exact ? 'correct' : 'wrong');
                } else {
                    cell.classList.add('neutral');
                }
            }

            if (!displayPattern) {
                const placeholder = document.createElement('div');
                placeholder.className = 'reconstruction-face-placeholder';
                cell.appendChild(placeholder);
            } else {
                const canvas = document.createElement('canvas');
                canvas.width = 64;
                canvas.height = 64;
                const ctx = canvas.getContext('2d');
                drawPattern(ctx, displayPattern, displayRotation, 0, 0, 64, '#1e1e3a');
                cell.appendChild(canvas);

                const angle = document.createElement('div');
                angle.className = 'reconstruction-face-angle';
                angle.textContent = displayPattern === RECONSTRUCTION_UNKNOWN ? '?' : `${displayRotation}°`;
                cell.appendChild(angle);
            }

            container.appendChild(cell);
        });
    }

    drawGrid() {
        const canvas = this.el.gridCanvas;
        const ctx = canvas.getContext('2d');

        if (this.gameMode !== 'forward') {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            return;
        }

        const level = this.currentLevel;
        const cellSize = 70;
        const pad = 40;

        canvas.width = level.gridWidth * cellSize + pad * 2;
        canvas.height = level.gridHeight * cellSize + pad * 2;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        this.drawGridBase(ctx, cellSize, pad);

        if (this.gameMode === 'forward') {
            this.drawForwardGrid(ctx, cellSize, pad);
        } else {
            this.drawReverseGrid(ctx, cellSize, pad);
        }

        const startX = pad + level.startX * cellSize + cellSize / 2;
        const startY = pad + level.startY * cellSize + cellSize / 2;
        ctx.fillStyle = 'rgba(100, 200, 255, 0.9)';
        ctx.font = 'bold 10px "Outfit", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        ctx.fillText('起点', startX, pad + level.startY * cellSize + 8);
    }

    drawGridBase(ctx, cellSize, pad) {
        const level = this.currentLevel;
        ctx.strokeStyle = 'rgba(255,255,255,0.1)';
        ctx.lineWidth = 1;

        for (let row = 0; row <= level.gridHeight; row++) {
            ctx.beginPath();
            ctx.moveTo(pad, pad + row * cellSize);
            ctx.lineTo(pad + level.gridWidth * cellSize, pad + row * cellSize);
            ctx.stroke();
        }

        for (let col = 0; col <= level.gridWidth; col++) {
            ctx.beginPath();
            ctx.moveTo(pad + col * cellSize, pad);
            ctx.lineTo(pad + col * cellSize, pad + level.gridHeight * cellSize);
            ctx.stroke();
        }
    }

    drawForwardGrid(ctx, cellSize, pad) {
        const positions = this.getPositionsForDirections(this.currentLevel.path);

        this.drawPathLine(ctx, positions, {
            strokeStyle: 'rgba(100, 200, 255, 0.4)',
            lineWidth: 3,
            dash: [5, 5]
        });

        for (let i = 0; i < this.currentLevel.path.length; i++) {
            const from = positions[i];
            const to = positions[i + 1];
            const midX = pad + ((from.x + to.x + 1) * cellSize) / 2;
            const midY = pad + ((from.y + to.y + 1) * cellSize) / 2;
            this.drawArrowOnGrid(ctx, midX, midY, this.currentLevel.path[i]);
        }

        const allAnswered = this.currentStep >= this.totalSteps;

        positions.forEach((pos, index) => {
            const cx = pad + pos.x * cellSize + cellSize / 2;
            const cy = pad + pos.y * cellSize + cellSize / 2;
            const radius = cellSize * 0.38;

            const isCurrent = !this.isRevealed && !allAnswered && index === this.currentStep;
            const hasAnswer = this.playerAnswers[index] !== null;

            if (isCurrent) {
                ctx.fillStyle = 'rgba(100, 200, 255, 0.15)';
                ctx.fillRect(pad + pos.x * cellSize + 2, pad + pos.y * cellSize + 2, cellSize - 4, cellSize - 4);
            }

            ctx.beginPath();
            ctx.arc(cx, cy, radius, 0, Math.PI * 2);

            if (this.isRevealed) {
                const result = this.pathResults[index];
                const answer = this.playerAnswers[index];
                const isCorrect = this.facesEqual(answer, result);
                ctx.fillStyle = isCorrect ? 'rgba(0, 200, 100, 0.3)' : 'rgba(255, 80, 80, 0.3)';
                ctx.fill();
                ctx.strokeStyle = isCorrect ? '#00c864' : '#ff5050';
                ctx.lineWidth = 3;
                ctx.stroke();

                drawPattern(ctx, result.patternId, result.rotation, cx - radius + 4, cy - radius + 4, (radius - 4) * 2);
            } else if (hasAnswer) {
                const answer = this.playerAnswers[index];
                ctx.fillStyle = 'rgba(100, 200, 255, 0.15)';
                ctx.fill();
                ctx.strokeStyle = 'rgba(100, 200, 255, 0.6)';
                ctx.lineWidth = 2;
                ctx.stroke();
                drawPattern(ctx, answer.patternId, answer.rotation, cx - radius + 4, cy - radius + 4, (radius - 4) * 2);
            } else if (isCurrent) {
                ctx.fillStyle = 'rgba(100, 200, 255, 0.08)';
                ctx.fill();
                ctx.strokeStyle = '#64c8ff';
                ctx.lineWidth = 3;
                ctx.stroke();
                ctx.fillStyle = 'rgba(100, 200, 255, 0.8)';
                ctx.font = 'bold 14px "Outfit", sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText('?', cx, cy);
            } else {
                ctx.fillStyle = 'rgba(255,255,255,0.05)';
                ctx.fill();
                ctx.strokeStyle = 'rgba(255,255,255,0.2)';
                ctx.lineWidth = 1;
                ctx.stroke();
            }

            this.drawStepNumber(ctx, index, cx, pad + pos.y * cellSize + cellSize - 16, isCurrent);
        });
    }

    drawReverseGrid(ctx, cellSize, pad) {
        const positions = this.getPositionsForDirections(this.playerMoves);
        const playerResults = this.getReverseResults();
        const allPlanned = this.playerMoves.length >= this.totalSteps;

        this.drawPathLine(ctx, positions, {
            strokeStyle: 'rgba(100, 200, 255, 0.55)',
            lineWidth: 4
        });

        for (let i = 0; i < this.playerMoves.length; i++) {
            const from = positions[i];
            const to = positions[i + 1];
            const midX = pad + ((from.x + to.x + 1) * cellSize) / 2;
            const midY = pad + ((from.y + to.y + 1) * cellSize) / 2;
            this.drawArrowOnGrid(ctx, midX, midY, this.playerMoves[i]);
        }

        positions.forEach((pos, index) => {
            const cx = pad + pos.x * cellSize + cellSize / 2;
            const cy = pad + pos.y * cellSize + cellSize / 2;
            const radius = cellSize * 0.38;
            const isCurrent = !this.isRevealed && !allPlanned && index === positions.length - 1;

            if (isCurrent) {
                ctx.fillStyle = 'rgba(100, 200, 255, 0.15)';
                ctx.fillRect(pad + pos.x * cellSize + 2, pad + pos.y * cellSize + 2, cellSize - 4, cellSize - 4);
            }

            ctx.beginPath();
            ctx.arc(cx, cy, radius, 0, Math.PI * 2);

            if (index === 0) {
                ctx.fillStyle = 'rgba(100, 200, 255, 0.14)';
                ctx.fill();
                ctx.strokeStyle = '#64c8ff';
                ctx.lineWidth = 3;
                ctx.stroke();
            } else if (this.isRevealed) {
                const isCorrect = this.facesEqual(playerResults[index], this.pathResults[index]);
                ctx.fillStyle = isCorrect ? 'rgba(0, 200, 100, 0.3)' : 'rgba(255, 80, 80, 0.3)';
                ctx.fill();
                ctx.strokeStyle = isCorrect ? '#00c864' : '#ff5050';
                ctx.lineWidth = 3;
                ctx.stroke();
            } else {
                ctx.fillStyle = 'rgba(100, 200, 255, 0.12)';
                ctx.fill();
                ctx.strokeStyle = isCurrent ? '#64c8ff' : 'rgba(100, 200, 255, 0.55)';
                ctx.lineWidth = isCurrent ? 3 : 2;
                ctx.stroke();
            }

            if (playerResults[index]) {
                drawPattern(
                    ctx,
                    playerResults[index].patternId,
                    playerResults[index].rotation,
                    cx - radius + 4,
                    cy - radius + 4,
                    (radius - 4) * 2
                );
            }

            this.drawStepNumber(ctx, index, cx, pad + pos.y * cellSize + cellSize - 16, isCurrent);
        });
    }

    drawPathLine(ctx, positions, options = {}) {
        if (positions.length < 2) return;

        const cellSize = 70;
        const pad = 40;

        ctx.strokeStyle = options.strokeStyle || 'rgba(100, 200, 255, 0.4)';
        ctx.lineWidth = options.lineWidth || 3;
        ctx.setLineDash(options.dash || []);

        ctx.beginPath();
        ctx.moveTo(pad + positions[0].x * cellSize + cellSize / 2, pad + positions[0].y * cellSize + cellSize / 2);

        for (let i = 1; i < positions.length; i++) {
            ctx.lineTo(pad + positions[i].x * cellSize + cellSize / 2, pad + positions[i].y * cellSize + cellSize / 2);
        }

        ctx.stroke();
        ctx.setLineDash([]);
    }

    drawArrowOnGrid(ctx, x, y, direction) {
        const size = 8;
        ctx.fillStyle = 'rgba(100, 200, 255, 0.65)';
        ctx.beginPath();

        switch (direction) {
            case 'N':
                ctx.moveTo(x, y - size);
                ctx.lineTo(x - size * 0.6, y + size * 0.3);
                ctx.lineTo(x + size * 0.6, y + size * 0.3);
                break;
            case 'S':
                ctx.moveTo(x, y + size);
                ctx.lineTo(x - size * 0.6, y - size * 0.3);
                ctx.lineTo(x + size * 0.6, y - size * 0.3);
                break;
            case 'E':
                ctx.moveTo(x + size, y);
                ctx.lineTo(x - size * 0.3, y - size * 0.6);
                ctx.lineTo(x - size * 0.3, y + size * 0.6);
                break;
            case 'W':
                ctx.moveTo(x - size, y);
                ctx.lineTo(x + size * 0.3, y - size * 0.6);
                ctx.lineTo(x + size * 0.3, y + size * 0.6);
                break;
        }

        ctx.closePath();
        ctx.fill();
    }

    drawStepNumber(ctx, step, x, y, active) {
        ctx.fillStyle = active ? '#64c8ff' : 'rgba(255,255,255,0.45)';
        ctx.font = 'bold 11px "Outfit", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(`${step}`, x, y);
    }

    buildPatternPalette() {
        const palette = this.el.patternPalette;
        palette.innerHTML = '';

        const usedPatterns = [...new Set(
            (Array.isArray(this.currentLevel.netFaces) && this.currentLevel.netFaces.length
                ? this.currentLevel.netFaces
                : this.currentLevel.netPatterns.map((patternId) => ({ patternId })))
                .map((face) => face.patternId)
        )];

        usedPatterns.forEach((patternId) => {
            const btn = document.createElement('button');
            btn.className = 'pattern-btn';
            btn.dataset.patternId = patternId;
            btn.title = getPatternLabel(patternId);

            const canvas = document.createElement('canvas');
            canvas.width = 48;
            canvas.height = 48;
            const ctx = canvas.getContext('2d');
            drawPattern(ctx, patternId, 0, 0, 0, 48, '#1e1e3a');
            btn.appendChild(canvas);

            btn.addEventListener('click', () => this.selectPattern(patternId));
            palette.appendChild(btn);
        });
    }

    selectPattern(patternId) {
        if (this.gameMode !== 'forward' || this.isRevealed) return;

        this.selectedPattern = patternId;
        this.el.patternPalette.querySelectorAll('.pattern-btn').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.patternId === patternId);
        });
        this.updateAnswerPreview();
    }

    buildReconstructionPalette() {
        const palette = this.el.reconstructionPalette;
        palette.innerHTML = '';

        const patterns = [...this.reconstructionData.palettePatterns, RECONSTRUCTION_UNKNOWN];
        patterns.forEach((patternId) => {
            const btn = this.createPatternButton(patternId, 48, () => this.selectReconstructionPattern(patternId));
            btn.classList.toggle('active', this.selectedPattern === patternId);
            if (patternId === RECONSTRUCTION_UNKNOWN) {
                btn.classList.add('unknown');
            }
            palette.appendChild(btn);
        });
    }

    createPatternButton(patternId, size, onClick) {
        const btn = document.createElement('button');
        btn.className = 'pattern-btn';
        btn.dataset.patternId = patternId;
        btn.title = patternId === RECONSTRUCTION_UNKNOWN ? '问号' : getPatternLabel(patternId);

        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d');
        drawPattern(ctx, patternId, 0, 0, 0, size, '#1e1e3a');
        btn.appendChild(canvas);

        btn.addEventListener('click', onClick);
        return btn;
    }

    selectReconstructionPattern(patternId) {
        if (this.gameMode !== 'reconstruct' || this.isRevealed) return;

        this.selectedPattern = patternId;
        this.el.reconstructionPalette.querySelectorAll('.pattern-btn').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.patternId === patternId);
        });
        this.updateAnswerPreview();
    }

    syncReconstructionRotationButtons() {
        this.el.reconstructionRotationControl.querySelectorAll('.reconstruction-rot-btn').forEach((btn) => {
            btn.classList.toggle('active', parseInt(btn.dataset.rotation, 10) === this.selectedRotation);
        });
    }

    updateAnswerPreview() {
        if (this.gameMode === 'reconstruct') {
            if (!this.selectedPattern) {
                this.el.reconstructionSelectedInfo.textContent = '先选一个观测到的图案，再点击左侧展开图上的格子填入';
            } else if (this.selectedPattern === RECONSTRUCTION_UNKNOWN) {
                this.el.reconstructionSelectedInfo.textContent = '当前选择：?，可把暂时无法确定的面标成问号';
            } else {
                this.el.reconstructionSelectedInfo.textContent = `当前选择：${getPatternLabel(this.selectedPattern)}，点击左侧展开图填入对应位置`;
            }
            return;
        }

        const canvas = this.el.answerPreview;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (this.selectedPattern) {
            drawPattern(ctx, this.selectedPattern, this.selectedRotation, 0, 0, canvas.width, '#1e1e3a');
            ctx.strokeStyle = '#64c8ff';
            ctx.lineWidth = 2;
            ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
            this.el.selectedInfo.textContent = `${getPatternLabel(this.selectedPattern)} · 旋转 ${this.selectedRotation}°`;
        } else {
            ctx.fillStyle = '#1e1e3a';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = 'rgba(255,255,255,0.3)';
            ctx.font = '14px "Outfit", sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('选择图案', canvas.width / 2, canvas.height / 2);
            ctx.strokeStyle = 'rgba(255,255,255,0.2)';
            ctx.lineWidth = 1;
            ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
            this.el.selectedInfo.textContent = '请先选择一个图案';
        }
    }

    updateAnswerPreview() {
        if (this.gameMode === 'reconstruct') {
            if (!this.selectedPattern) {
                this.el.reconstructionSelectedInfo.textContent = '先选一个观测到的图案，再点击左侧展开图上的格子填入';
            } else if (this.selectedPattern === RECONSTRUCTION_UNKNOWN) {
                this.el.reconstructionSelectedInfo.textContent = '当前选择：?，可把暂时无法确定的面标成问号';
            } else {
                this.el.reconstructionSelectedInfo.textContent = `当前选择：${getPatternLabel(this.selectedPattern)}，点击左侧展开图填入对应位置`;
            }
            return;
        }

        const canvas = this.el.answerPreview;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (this.selectedPattern) {
            drawPattern(ctx, this.selectedPattern, this.selectedRotation, 0, 0, canvas.width, '#1e1e3a');
            ctx.strokeStyle = '#64c8ff';
            ctx.lineWidth = 2;
            ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
            this.el.selectedInfo.textContent = `${getPatternLabel(this.selectedPattern)} · 旋转 ${this.selectedRotation}°`;
        } else {
            ctx.fillStyle = '#1e1e3a';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = 'rgba(255,255,255,0.3)';
            ctx.font = '14px "Outfit", sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('选择图案', canvas.width / 2, canvas.height / 2);
            ctx.strokeStyle = 'rgba(255,255,255,0.2)';
            ctx.lineWidth = 1;
            ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
            this.el.selectedInfo.textContent = '请先选择一个图案';
        }
    }

    renderTargetSequence() {
        if (this.gameMode !== 'reverse') return;

        const container = this.el.targetSequence;
        container.innerHTML = '';

        const playerResults = this.getReverseResults();
        const targets = this.pathResults.slice(1);
        const nextTargetIndex = Math.min(this.playerMoves.length, targets.length - 1);

        targets.forEach((face, index) => {
            const card = document.createElement('div');
            card.className = 'target-card';

            if (!this.isRevealed) {
                if (index < this.playerMoves.length) {
                    card.classList.add('done');
                }
                if (index === nextTargetIndex && this.playerMoves.length < this.totalSteps) {
                    card.classList.add('current');
                }
            } else {
                card.classList.add(this.patternsEqual(playerResults[index + 1], face) ? 'matched' : 'wrong');
            }

            const tag = document.createElement('div');
            tag.className = 'target-step';
            tag.textContent = `目标 ${index + 1}`;

            const canvas = document.createElement('canvas');
            canvas.width = 52;
            canvas.height = 52;
            const ctx = canvas.getContext('2d');
            drawPattern(ctx, face.patternId, 0, 0, 0, 52, '#1e1e3a');

            const label = document.createElement('div');
            label.className = 'target-label';
            label.textContent = getPatternLabel(face.patternId);

            card.appendChild(tag);
            card.appendChild(canvas);
            card.appendChild(label);
            container.appendChild(card);
        });
    }

    renderMovePreview() {
        if (this.gameMode !== 'reverse') return;

        const container = this.el.movePreview;
        container.innerHTML = '';

        const summary = document.createElement('div');
        summary.className = 'move-preview-summary';
        summary.textContent = `已输入 ${this.playerMoves.length} / ${this.totalSteps} 步`;
        container.appendChild(summary);

        if (!this.playerMoves.length) {
            container.classList.add('empty');
            const empty = document.createElement('div');
            empty.textContent = '还没有输入滚动方向';
            container.appendChild(empty);
            return;
        }

        container.classList.remove('empty');
        const results = this.getReverseResults();

        this.playerMoves.forEach((dir, index) => {
            const chip = document.createElement('div');
            chip.className = 'move-chip';

            if (this.isRevealed) {
                chip.classList.add(this.patternsEqual(results[index + 1], this.pathResults[index + 1]) ? 'matched' : 'wrong');
            }

            chip.textContent = `${index + 1}. ${DIR_META[dir].arrow} ${DIR_META[dir].short}`;
            container.appendChild(chip);
        });
    }

    renderReconstructionChallenge() {
        if (this.gameMode !== 'reconstruct') return;

        const directions = this.el.reconstructionDirections;
        directions.innerHTML = '';
        this.reconstructionData.directions.forEach((dir, index) => {
            const chip = document.createElement('div');
            chip.className = 'direction-chip';
            chip.textContent = `${index + 1}. ${DIR_META[dir].arrow} ${DIR_META[dir].short}`;
            directions.appendChild(chip);
        });

        const observed = this.el.reconstructionObservedSequence;
        observed.innerHTML = '';
        this.reconstructionData.observedFaces.forEach((face, index) => {
            const card = document.createElement('div');
            card.className = 'target-card observed-card';

            const tag = document.createElement('div');
            tag.className = 'target-step';
            tag.textContent = `观测 ${index + 1}`;

            const canvas = document.createElement('canvas');
            canvas.width = 52;
            canvas.height = 52;
            const ctx = canvas.getContext('2d');
            drawPattern(ctx, face.patternId, face.rotation, 0, 0, 52, '#1e1e3a', face);

            const label = document.createElement('div');
            label.className = 'target-label';
            label.textContent = getPatternLabel(face.patternId);

            const rotation = document.createElement('div');
            rotation.className = 'target-rotation';
            rotation.textContent = `${face.rotation}°`;

            card.appendChild(tag);
            card.appendChild(canvas);
            observed.appendChild(card);
        });
    }

    submitAnswer() {
        if (this.gameMode === 'reconstruct') {
            this.clearReconstructionAnswers();
            return;
        }

        if (this.gameMode !== 'forward') return;

        if (!this.selectedPattern) {
            this.showToast('请先选择一个图案');
            return;
        }

        this.playerAnswers[this.currentStep] = {
            patternId: this.selectedPattern,
            rotation: this.selectedRotation
        };

        if (this.currentStep < this.totalSteps - 1) {
            this.currentStep += 1;
            this.cubeState = this.cubeStates[this.currentStep].clone();
            this.updateCubeRendererState();
            this.resetForwardSelection();
        } else {
            this.currentStep += 1;
        }

        this.drawGrid();
        this.updateAnswerPreview();
        this.updateStepUI();
    }

    resetForwardSelection() {
        this.selectedPattern = null;
        this.selectedRotation = 0;

        this.el.patternPalette.querySelectorAll('.pattern-btn').forEach((btn) => btn.classList.remove('active'));
        this.el.rotationControl.querySelectorAll('.rot-btn').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.rotation === '0');
        });
    }

    handleMoveInput(direction) {
        if (this.gameMode !== 'reverse' || this.isRevealed) return;

        if (this.playerMoves.length >= this.totalSteps) {
            this.showToast('滚动序列已经填满了');
            return;
        }

        const nextCube = this.cubeState.clone();
        nextCube.roll(direction);

        this.playerMoves.push(direction);
        this.cubeState = nextCube;
        this.cubeStates.push(nextCube.clone());
        this.currentStep = this.playerMoves.length;

        this.drawGrid();
        this.updateCubeRendererState();
        this.renderTargetSequence();
        this.renderMovePreview();
        this.updateStepUI();
    }

    undoMove() {
        if (this.gameMode !== 'reverse' || this.isRevealed || !this.playerMoves.length) return;

        this.playerMoves.pop();
        this.cubeStates.pop();
        this.cubeState = this.cubeStates[this.cubeStates.length - 1].clone();
        this.currentStep = this.playerMoves.length;

        this.drawGrid();
        this.updateCubeRendererState();
        this.renderTargetSequence();
        this.renderMovePreview();
        this.updateStepUI();
    }

    resetMoves() {
        if (this.gameMode !== 'reverse' || this.isRevealed || !this.playerMoves.length) return;

        this.playerMoves = [];
        this.cubeState = this.initialCube.clone();
        this.cubeStates = [this.cubeState.clone()];
        this.currentStep = 0;

        this.drawGrid();
        this.updateCubeRendererState();
        this.renderTargetSequence();
        this.renderMovePreview();
        this.updateStepUI();
    }

    clearReconstructionAnswers() {
        if (this.gameMode !== 'reconstruct' || this.isRevealed) return;

        RECONSTRUCTION_NET_SLOTS.forEach((slot) => {
            this.reconstructionAnswers[slot.key] = null;
            this.reconstructionRotations[slot.key] = 0;
        });
        this.currentStep = 0;
        this.renderReconstructionNet();
        this.updateCubeRendererState();
        this.updateStepUI();
    }

    handleReconstructionNetClick(event) {
        if (this.gameMode !== 'reconstruct' || this.isRevealed) return;

        const slotButton = event.target.closest('.reconstruction-face-slot');
        if (!slotButton) return;

        if (!this.selectedPattern) {
            this.showToast('请先从右侧选择一个图案或 ?');
            return;
        }

        this.reconstructionAnswers[slotButton.dataset.slotKey] = this.selectedPattern;
        this.reconstructionRotations[slotButton.dataset.slotKey] = this.selectedPattern === RECONSTRUCTION_UNKNOWN
            ? 0
            : this.selectedRotation;
        this.currentStep = this.countReconstructionFilledSlots();
        this.renderReconstructionNet();
        this.updateCubeRendererState();
        this.updateStepUI();
    }

    revealAnswers() {
        if (this.gameMode === 'forward') {
            this.revealForwardAnswers();
        } else if (this.gameMode === 'reverse') {
            this.revealReverseAnswers();
        } else {
            this.revealReconstructionAnswers();
        }
    }

    revealForwardAnswers() {
        this.isRevealed = true;
        this.score = 0;

        for (let i = 0; i < this.totalSteps; i++) {
            if (this.facesEqual(this.playerAnswers[i], this.pathResults[i])) {
                this.score += 1;
            }
        }

        this.drawGrid();
        this.updateStepUI();
        this.showResults();
    }

    revealReverseAnswers() {
        if (this.playerMoves.length < this.totalSteps) {
            this.showToast('请先把整条滚动路径设计完整');
            return;
        }

        this.isRevealed = true;
        this.score = 0;

        const playerResults = this.getReverseResults();
        for (let i = 1; i < this.pathResults.length; i++) {
            if (this.patternsEqual(playerResults[i], this.pathResults[i])) {
                this.score += 1;
            }
        }

        this.drawGrid();
        this.renderTargetSequence();
        this.renderMovePreview();
        this.updateStepUI();
        this.showResults();
    }

    revealReconstructionAnswers() {
        this.isRevealed = true;
        this.score = 0;

        this.reconstructionData.requiredSlots.forEach((slotKey) => {
            const answer = this.reconstructionAnswers[slotKey];
            const answerRotation = this.reconstructionRotations[slotKey] ?? 0;
            const actualFace = this.reconstructionData.actualFaces[slotKey];

            if (
                answer &&
                answer !== RECONSTRUCTION_UNKNOWN &&
                answer === actualFace.patternId &&
                answerRotation === actualFace.rotation
            ) {
                this.score += 1;
            }
        });

        this.renderReconstructionNet();
        this.updateCubeRendererState();
        this.updateStepUI();
        this.showResults();
    }

    showResults() {
        {
        this.el.resultPanel.classList.remove('hidden');

        const legacyMaxScore = this.totalSteps;
        const legacyPct = legacyMaxScore ? Math.round((this.score / legacyMaxScore) * 100) : 100;

        let emoji = '🎯';
        if (pct < 30) emoji = '😄';
        else if (pct < 60) emoji = '🤔';
        else if (pct < 90) emoji = '😎';

        let subtitle = '图案和朝向都对才算完全正确。';
        let scoreText = `${this.score} / ${maxScore} 步正确`;

        if (this.gameMode === 'reverse') {
            subtitle = '逆向模式允许多解，只要得到的底面图案序列一致就算正确，不看图案朝向。';
            scoreText = `${this.score} / ${maxScore} 步达成目标`;
        } else if (this.gameMode === 'reconstruct') {
            subtitle = '还原模式只统计能从观测序列中确定出来的那些面，其他面填 ? 不扣分。';
            scoreText = `${this.score} / ${maxScore} 个可确定面正确`;
        }

        this.el.scoreDisplay.innerHTML = `
            <div class="score-emoji">${emoji}</div>
            <div class="score-text">${scoreText}</div>
            <div class="score-pct">${pct}%</div>
            <div class="score-subtitle">${subtitle}</div>
            <div class="score-detail">${this.buildResultDetail()}</div>
        `;

        if (this.levelIndex < LEVELS.length - 1) {
            this.el.nextLevelBtn.classList.remove('hidden');
        } else {
            this.el.nextLevelBtn.classList.add('hidden');
        }

        return;
        }
        this.el.resultPanel.classList.remove('hidden');

        const legacyMaxScore = this.totalSteps;
        const legacyPct = legacyMaxScore ? Math.round((this.score / legacyMaxScore) * 100) : 100;

        let emoji = '🏁';
        if (pct < 30) emoji = '😅';
        else if (pct < 60) emoji = '🙂';
        else if (pct < 90) emoji = '😎';

        const subtitle = this.gameMode === 'forward'
            ? '图案和朝向都对才算完全正确。'
            : '逆向模式允许多解，只要你得到的底面图案序列一致就算正确，不看朝向。';
        const scoreText = this.gameMode === 'forward'
            ? `${this.score} / ${maxScore} 步正确`
            : `${this.score} / ${maxScore} 步达成目标`;

        this.el.scoreDisplay.innerHTML = `
            <div class="score-emoji">${emoji}</div>
            <div class="score-text">${scoreText}</div>
            <div class="score-pct">${pct}%</div>
            <div class="score-subtitle">${subtitle}</div>
            <div class="score-detail">${this.buildResultDetail()}</div>
        `;

        if (this.levelIndex < LEVELS.length - 1) {
            this.el.nextLevelBtn.classList.remove('hidden');
        } else {
            this.el.nextLevelBtn.classList.add('hidden');
        }
    }

    buildResultDetail() {
        if (this.gameMode === 'reconstruct') {
            return this.buildReconstructionResultDetail();
        }

        if (this.gameMode === 'forward') {
            return this.buildForwardResultDetail();
        }

        return this.buildReverseResultDetail();
        
        return this.gameMode === 'forward'
            ? this.buildForwardResultDetail()
            : this.buildReverseResultDetail();
    }

    buildForwardResultDetail() {
        let html = '<div class="result-steps">';

        for (let i = 0; i < this.totalSteps; i++) {
            const target = this.pathResults[i];
            const answer = this.playerAnswers[i];
            const exact = this.facesEqual(answer, target);
            const patternMatch = this.patternsEqual(answer, target);

            html += `<div class="result-step ${exact ? 'correct' : 'wrong'}">`;
            html += `<span class="result-step-num">步骤 ${i}</span>`;
            html += `<span class="result-step-icon">${exact ? '✓' : patternMatch ? '≈' : '✗'}</span>`;
            html += '<span class="result-step-detail">';

            if (!answer) {
                html += '未作答';
            } else if (exact) {
                html += '图案与朝向都正确';
            } else if (patternMatch) {
                html += `图案正确，但朝向不对（你: ${answer.rotation}° / 正确: ${target.rotation}°）`;
            } else {
                html += `正确答案：${this.formatFace(target)}`;
            }

            html += '</span></div>';
        }

        html += '</div>';
        return html;
    }

    buildReverseResultDetail() {
        const playerResults = this.getReverseResults();
        let html = '<div class="result-note">逆向题可能不止一种解，系统只按你是否成功达成目标图案序列评分，不看旋转朝向。</div>';
        html += '<div class="result-steps">';

        for (let i = 1; i < this.pathResults.length; i++) {
            const target = this.pathResults[i];
            const actual = playerResults[i];
            const matched = this.patternsEqual(actual, target);
            const move = this.playerMoves[i - 1];

            html += `<div class="result-step ${matched ? 'correct' : 'wrong'}">`;
            html += `<span class="result-step-num">步骤 ${i}</span>`;
            html += `<span class="result-step-icon">${matched ? '✓' : '✗'}</span>`;
            html += '<span class="result-step-detail">';

            if (matched) {
                html += `${DIR_META[move].short} 后成功得到 ${this.formatPattern(target)}`;
            } else {
                html += `${DIR_META[move].short} 后得到 ${this.formatPattern(actual)}，目标是 ${this.formatPattern(target)}`;
            }

            html += '</span></div>';
        }

        html += '</div>';
        html += `<div class="reference-path">参考路径之一：${this.formatDirectionSequence(this.currentLevel.path)}</div>`;
        return html;
    }

    buildReconstructionResultDetail() {
        let html = `<div class="result-note">本题的滚动序列一共暴露了 ${this.totalSteps} 个可确定面，这些位置会计分；没有被序列确定到的面可以保留为 ?。</div>`;
        html += '<div class="result-steps">';

        this.reconstructionData.requiredSlots.forEach((slotKey) => {
            const answer = this.reconstructionAnswers[slotKey];
            const actual = this.reconstructionData.actualPatterns[slotKey];
            const matched = answer === actual;

            html += `<div class="result-step ${matched ? 'correct' : 'wrong'}">`;
            html += `<span class="result-step-num">${this.getSlotName(slotKey)}</span>`;
            html += `<span class="result-step-icon">${matched ? '✓' : '✗'}</span>`;
            html += '<span class="result-step-detail">';

            if (!answer) {
                html += `未填写，正确图案是 ${getPatternLabel(actual)}`;
            } else if (answer === RECONSTRUCTION_UNKNOWN) {
                html += `你填了 ?，这个位置其实可以确定为 ${getPatternLabel(actual)}`;
            } else if (matched) {
                html += `放置正确：${getPatternLabel(actual)}`;
            } else {
                html += `你放的是 ${getPatternLabel(answer)}，正确应为 ${getPatternLabel(actual)}`;
            }

            html += '</span></div>';
        });

        html += '</div>';
        html += `<div class="reference-path">滚动序列：${this.formatDirectionSequence(this.reconstructionData.directions)}</div>`;
        html += `<div class="reference-path">完整答案：${this.buildReconstructionSolutionSummary()}</div>`;
        return html;
    }

    buildReconstructionSolutionSummary() {
        return RECONSTRUCTION_NET_SLOTS
            .map((slot) => `${this.getSlotName(slot.key)}=${getPatternLabel(this.reconstructionData.actualPatterns[slot.key])}`)
            .join(' · ');
    }

    goNextLevel() {
        if (this.levelIndex < LEVELS.length - 1) {
            this.startLevel(this.levelIndex + 1);
        }
    }

    updateStepUI() {
        if (this.gameMode === 'reconstruct') {
            this.updateReconstructionUI();
            return;
        }

        if (this.gameMode === 'forward') {
            this.updateForwardUI();
            return;
        }

        this.updateReverseUI();
    }

    updateAnswerPreview() {
        if (this.gameMode === 'reconstruct') {
            if (!this.selectedPattern) {
                this.el.reconstructionSelectedInfo.textContent = '先选图案，再选方向，然后点击左侧对应的面进行填写';
            } else if (this.selectedPattern === RECONSTRUCTION_UNKNOWN) {
                this.el.reconstructionSelectedInfo.textContent = '当前选择：?，暂时无法确定的面可以先标成问号';
            } else {
                this.el.reconstructionSelectedInfo.textContent = `当前选择：${getPatternLabel(this.selectedPattern)} · ${this.selectedRotation}°`;
            }
            return;
        }

        const canvas = this.el.answerPreview;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (this.selectedPattern) {
            drawPattern(ctx, this.selectedPattern, this.selectedRotation, 0, 0, canvas.width, '#1e1e3a');
            ctx.strokeStyle = '#64c8ff';
            ctx.lineWidth = 2;
            ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
            this.el.selectedInfo.textContent = `${getPatternLabel(this.selectedPattern)} · 旋转 ${this.selectedRotation}°`;
        } else {
            ctx.fillStyle = '#1e1e3a';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = 'rgba(255,255,255,0.3)';
            ctx.font = '14px "Outfit", sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('选择图案', canvas.width / 2, canvas.height / 2);
            ctx.strokeStyle = 'rgba(255,255,255,0.2)';
            ctx.lineWidth = 1;
            ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
            this.el.selectedInfo.textContent = '请先选择一个图案';
        }
    }

    updateForwardUI() {
        {
        const allAnswered = this.currentStep >= this.totalSteps;

        this.el.stepIndicator.textContent = allAnswered
            ? `已完成 ${this.totalSteps} 步猜测`
            : `第 ${this.currentStep} 步 / 共 ${this.totalSteps} 步`;

        this.el.submitBtn.classList.toggle('hidden', allAnswered || this.isRevealed);
        this.el.revealBtn.classList.toggle('hidden', !allAnswered || this.isRevealed);

        this.el.patternPalette.querySelectorAll('.pattern-btn').forEach((btn) => {
            btn.disabled = allAnswered || this.isRevealed;
        });

        this.el.rotationControl.querySelectorAll('.rot-btn').forEach((btn) => {
            btn.disabled = allAnswered || this.isRevealed;
        });

        if (this.currentStep === 0) {
            this.el.stepHint.textContent = '初始位置：先观察展开图与立方体，猜测起点底面的图案和朝向。';
        } else if (this.currentStep < this.totalSteps) {
            const dir = this.currentLevel.path[this.currentStep - 1];
            this.el.stepHint.textContent = `立方体刚刚${DIR_META[dir].long}，现在请继续预测新的底面图案与朝向。`;
        } else {
            this.el.stepHint.textContent = '所有步骤都已作答，点击“查看结果”揭晓答案。';
        }

        return;
        }
        const allAnswered = this.currentStep >= this.totalSteps;

        this.el.stepIndicator.textContent = allAnswered
            ? `已完成 ${this.totalSteps} 步猜测`
            : `第 ${this.currentStep} 步 / 共 ${this.totalSteps} 步`;

        this.el.submitBtn.classList.toggle('hidden', allAnswered || this.isRevealed);
        this.el.revealBtn.classList.toggle('hidden', !allAnswered || this.isRevealed);

        document.querySelectorAll('.pattern-btn').forEach((btn) => {
            btn.disabled = allAnswered || this.isRevealed;
        });

        document.querySelectorAll('.rot-btn').forEach((btn) => {
            btn.disabled = allAnswered || this.isRevealed;
        });

        if (this.currentStep === 0) {
            this.el.stepHint.textContent = '初始位置：先观察展开图与立方体，猜测起点的底面。';
        } else if (this.currentStep < this.totalSteps) {
            const dir = this.currentLevel.path[this.currentStep - 1];
            this.el.stepHint.textContent = `立方体刚刚${DIR_META[dir].long}，现在请猜测新的底面图案与朝向。`;
        } else {
            this.el.stepHint.textContent = '所有步骤都已作答，点击“查看结果”揭晓答案。';
        }
    }

    updateReverseUI() {
        {
        const allPlanned = this.playerMoves.length >= this.totalSteps;

        this.el.submitBtn.classList.add('hidden');
        this.el.revealBtn.classList.toggle('hidden', !allPlanned || this.isRevealed);
        this.el.stepIndicator.textContent = allPlanned
            ? `已设计完 ${this.totalSteps} 步路径`
            : `已设计 ${this.playerMoves.length} / ${this.totalSteps} 步`;

        document.querySelectorAll('.move-btn').forEach((btn) => {
            btn.disabled = allPlanned || this.isRevealed;
        });

        this.el.undoMoveBtn.disabled = !this.playerMoves.length || this.isRevealed;
        this.el.resetMovesBtn.disabled = !this.playerMoves.length || this.isRevealed;

        if (this.isRevealed) {
            this.el.stepHint.textContent = '结果已揭晓。你可以重来、下一关，或切换模式继续挑战。';
        } else if (!allPlanned) {
            const nextTarget = this.pathResults[this.playerMoves.length + 1];
            this.el.stepHint.textContent = `下一步目标：让底面出现 ${this.formatPattern(nextTarget)}。逆向模式只看图案，不看朝向，也不需要考虑棋盘位置。`;
        } else {
            this.el.stepHint.textContent = '路径已经设计完成，点击“检查路径”看看是否达成目标序列。';
        }

        return;
        }
        const allPlanned = this.playerMoves.length >= this.totalSteps;

        this.el.submitBtn.classList.add('hidden');
        this.el.revealBtn.classList.toggle('hidden', !allPlanned || this.isRevealed);
        this.el.stepIndicator.textContent = allPlanned
            ? `已设计完 ${this.totalSteps} 步路径`
            : `已设计 ${this.playerMoves.length} / ${this.totalSteps} 步`;

        document.querySelectorAll('.move-btn').forEach((btn) => {
            btn.disabled = allPlanned || this.isRevealed;
        });

        this.el.undoMoveBtn.disabled = !this.playerMoves.length || this.isRevealed;
        this.el.resetMovesBtn.disabled = !this.playerMoves.length || this.isRevealed;

        if (this.isRevealed) {
            this.el.stepHint.textContent = '结果已揭晓。你可以重来、下一关，或切换模式继续挑战。';
        } else if (!allPlanned) {
            const nextTarget = this.pathResults[this.playerMoves.length + 1];
            this.el.stepHint.textContent = `下一步目标：让底面出现 ${this.formatPattern(nextTarget)}。逆向模式只看图案，不看朝向，也不需要考虑棋盘位置。`;
        } else {
            this.el.stepHint.textContent = '路径已经设计完成，点击“检查路径”看看是否达成目标图案序列。';
        }
    }

    updateReconstructionUI() {
        const filled = this.countReconstructionFilledSlots();
        const resolvedRequired = this.reconstructionData.requiredSlots.filter((slotKey) => {
            const answer = this.reconstructionAnswers[slotKey];
            return answer && answer !== RECONSTRUCTION_UNKNOWN;
        }).length;

        this.el.submitBtn.classList.toggle('hidden', this.isRevealed);
        this.el.revealBtn.classList.toggle('hidden', this.isRevealed);
        this.el.stepIndicator.textContent = this.isRevealed
            ? `还原得分 ${this.score} / ${this.totalSteps}`
            : `已填 ${filled} / 6 面 · 可确定 ${this.totalSteps} 面`;

        this.el.reconstructionPalette.querySelectorAll('.pattern-btn').forEach((btn) => {
            btn.disabled = this.isRevealed;
        });

        if (this.isRevealed) {
            this.el.stepHint.textContent = '答案已揭晓。绿色表示还原正确，红色表示这个位置其实可以由观测序列确定，但你的放置不对。';
        } else if (!this.selectedPattern) {
            this.el.stepHint.textContent = `先从右侧选择一个观测到的图案或 ?，再点击左侧展开图填入。本题至少可以确定 ${this.totalSteps} 个面。`;
        } else if (this.selectedPattern === RECONSTRUCTION_UNKNOWN) {
            this.el.stepHint.textContent = `当前选择的是 ?。暂时无法判断的面可以先标问号；真正会计分的是那 ${this.totalSteps} 个可确定面。`;
        } else {
            this.el.stepHint.textContent = `当前选择 ${getPatternLabel(this.selectedPattern)}。你已经填出了 ${resolvedRequired} / ${this.totalSteps} 个可确定面。`;
        }
    }

    getPositionsForDirections(directions) {
        let x = this.currentLevel.startX;
        let y = this.currentLevel.startY;
        const positions = [{ x, y }];

        directions.forEach((dir) => {
            ({ x, y } = this.getNextPosition(x, y, dir));
            positions.push({ x, y });
        });

        return positions;
    }

    getNextPosition(x, y, direction) {
        switch (direction) {
            case 'N': return { x, y: y - 1 };
            case 'S': return { x, y: y + 1 };
            case 'E': return { x: x + 1, y };
            case 'W': return { x: x - 1, y };
            default: return { x, y };
        }
    }

    isInsideBoard(x, y) {
        return x >= 0 &&
            x < this.currentLevel.gridWidth &&
            y >= 0 &&
            y < this.currentLevel.gridHeight;
    }

    getReverseResults() {
        return this.cubeStates.map((cube) => ({
            patternId: cube.bottom.patternId,
            rotation: cube.bottom.rotation,
            x: cube.x,
            y: cube.y
        }));
    }

    countReconstructionFilledSlots() {
        return Object.values(this.reconstructionAnswers).filter((value) => value !== null).length;
    }

    getSlotName(slotKey) {
        return RECONSTRUCTION_SLOT_LABELS[slotKey] || slotKey;
    }

    facesEqual(a, b) {
        return !!a &&
            !!b &&
            a.patternId === b.patternId &&
            (a.rotation ?? 0) === (b.rotation ?? 0) &&
            Boolean(a.flipHorizontal) === Boolean(b.flipHorizontal) &&
            Boolean(a.flipVertical) === Boolean(b.flipVertical);
    }

    patternsEqual(a, b) {
        return !!a && !!b && a.patternId === b.patternId;
    }

    updateForwardUI() {
        const allAnswered = this.currentStep >= this.totalSteps;

        this.el.stepIndicator.textContent = allAnswered
            ? `已完成 ${this.totalSteps} 步猜测`
            : `第 ${this.currentStep} 步 / 共 ${this.totalSteps} 步`;

        this.el.submitBtn.classList.toggle('hidden', allAnswered || this.isRevealed);
        this.el.revealBtn.classList.toggle('hidden', !allAnswered || this.isRevealed);

        this.el.patternPalette.querySelectorAll('.pattern-btn').forEach((btn) => {
            btn.disabled = allAnswered || this.isRevealed;
        });

        this.el.rotationControl.querySelectorAll('.rot-btn').forEach((btn) => {
            btn.disabled = allAnswered || this.isRevealed;
        });

        if (this.currentStep === 0) {
            this.el.stepHint.textContent = '初始位置：先观察展开图与立方体，猜测起点底面的图案和朝向。';
        } else if (this.currentStep < this.totalSteps) {
            const dir = this.currentLevel.path[this.currentStep - 1];
            this.el.stepHint.textContent = `立方体刚刚${DIR_META[dir].long}，现在请继续预测新的底面图案与朝向。`;
        } else {
            this.el.stepHint.textContent = '所有步骤都已作答，点击“查看结果”揭晓答案。';
        }
    }

    updateReverseUI() {
        const allPlanned = this.playerMoves.length >= this.totalSteps;

        this.el.submitBtn.classList.add('hidden');
        this.el.revealBtn.classList.toggle('hidden', !allPlanned || this.isRevealed);
        this.el.stepIndicator.textContent = allPlanned
            ? `已设计完 ${this.totalSteps} 步路径`
            : `已设计 ${this.playerMoves.length} / ${this.totalSteps} 步`;

        document.querySelectorAll('.move-btn').forEach((btn) => {
            btn.disabled = allPlanned || this.isRevealed;
        });

        this.el.undoMoveBtn.disabled = !this.playerMoves.length || this.isRevealed;
        this.el.resetMovesBtn.disabled = !this.playerMoves.length || this.isRevealed;

        if (this.isRevealed) {
            this.el.stepHint.textContent = '结果已揭晓。你可以重来、下一关，或切换模式继续挑战。';
        } else if (!allPlanned) {
            const nextTarget = this.pathResults[this.playerMoves.length + 1];
            this.el.stepHint.textContent = `下一步目标：让底面出现 ${this.formatPattern(nextTarget)}。逆向模式只看图案，不看朝向，也不需要考虑棋盘位置。`;
        } else {
            this.el.stepHint.textContent = '路径已经设计完成，点击“检查路径”看看是否达成目标序列。';
        }
    }

    showResults() {
        this.el.resultPanel.classList.remove('hidden');

        const maxScore = this.totalSteps;
        const pct = maxScore ? Math.round((this.score / maxScore) * 100) : 100;

        let emoji = '🎯';
        if (pct < 30) emoji = '😄';
        else if (pct < 60) emoji = '🤔';
        else if (pct < 90) emoji = '😎';

        let subtitle = '图案和朝向都对才算完全正确。';
        let scoreText = `${this.score} / ${maxScore} 步正确`;

        if (this.gameMode === 'reverse') {
            subtitle = '逆向模式允许多解，只要得到的底面图案序列一致就算正确，不看图案朝向。';
            scoreText = `${this.score} / ${maxScore} 步达成目标`;
        } else if (this.gameMode === 'reconstruct') {
            subtitle = '还原模式只统计能从观测序列中确定出来的那些面，其他面填 ? 不扣分。';
            scoreText = `${this.score} / ${maxScore} 个可确定面正确`;
        }

        this.el.scoreDisplay.innerHTML = `
            <div class="score-emoji">${emoji}</div>
            <div class="score-text">${scoreText}</div>
            <div class="score-pct">${pct}%</div>
            <div class="score-subtitle">${subtitle}</div>
            <div class="score-detail">${this.buildResultDetail()}</div>
        `;

        if (this.levelIndex < LEVELS.length - 1) {
            this.el.nextLevelBtn.classList.remove('hidden');
        } else {
            this.el.nextLevelBtn.classList.add('hidden');
        }
    }

    formatFace(face) {
        if (!face) return '空';
        return `${getPatternLabel(face.patternId)} ${face.rotation}°`;
    }

    formatPattern(face) {
        if (!face) return '空';
        return getPatternLabel(face.patternId);
    }

    formatDirectionSequence(directions) {
        return directions.map((dir, index) => `${index + 1}.${DIR_META[dir].short}`).join(' · ');
    }

    formatFace(face) {
        if (!face) return '空';
        return `${getPatternLabel(face.patternId)} ${face.rotation}°`;
    }

    formatPattern(face) {
        if (!face) return '空';
        return getPatternLabel(face.patternId);
    }

    formatDirectionSequence(directions) {
        return directions.map((dir, index) => `${index + 1}.${DIR_META[dir].short}`).join(' → ');
    }

    renderReconstructionNet() {
        const container = this.el.reconstructionNet;
        container.innerHTML = '';

        RECONSTRUCTION_NET_SLOTS.forEach((slot) => {
            const cell = document.createElement('button');
            cell.type = 'button';
            cell.className = 'reconstruction-face-slot';
            cell.dataset.slotKey = slot.key;
            cell.style.gridColumn = `${slot.col}`;
            cell.style.gridRow = `${slot.row}`;
            cell.title = RECONSTRUCTION_SLOT_LABELS[slot.key];
            cell.disabled = this.isRevealed;

            const label = document.createElement('div');
            label.className = 'reconstruction-face-label';
            label.textContent = RECONSTRUCTION_SLOT_LABELS[slot.key];
            cell.appendChild(label);

            const answerPattern = this.reconstructionAnswers[slot.key];
            const answerRotation = this.reconstructionRotations[slot.key] ?? 0;
            const actualFace = this.reconstructionData.actualFaces[slot.key];
            const displayPattern = this.isRevealed ? actualFace.patternId : answerPattern;
            const displayRotation = this.isRevealed ? actualFace.rotation : answerRotation;

            if (!this.isRevealed && answerPattern) {
                cell.classList.add('filled');
            }

            if (this.isRevealed) {
                if (this.reconstructionData.requiredSlotSet.has(slot.key)) {
                    const exact = !!answerPattern &&
                        answerPattern !== RECONSTRUCTION_UNKNOWN &&
                        answerPattern === actualFace.patternId &&
                        answerRotation === actualFace.rotation;
                    cell.classList.add(exact ? 'correct' : 'wrong');
                } else {
                    cell.classList.add('neutral');
                }
            }

            if (!displayPattern) {
                const placeholder = document.createElement('div');
                placeholder.className = 'reconstruction-face-placeholder';
                cell.appendChild(placeholder);
            } else {
                const canvas = document.createElement('canvas');
                canvas.width = 64;
                canvas.height = 64;
                const ctx = canvas.getContext('2d');
                drawPattern(ctx, displayPattern, displayRotation, 0, 0, 64, '#1e1e3a');
                cell.appendChild(canvas);

                const angle = document.createElement('div');
                angle.className = 'reconstruction-face-angle';
                angle.textContent = `${displayRotation}°`;
                cell.appendChild(angle);
            }

            container.appendChild(cell);
        });
    }

    renderReconstructionChallenge() {
        if (this.gameMode !== 'reconstruct') return;

        const directions = this.el.reconstructionDirections;
        directions.innerHTML = '';
        this.reconstructionData.directions.forEach((dir, index) => {
            const chip = document.createElement('div');
            chip.className = 'direction-chip';
            chip.textContent = `${index + 1}. ${DIR_META[dir].arrow} ${DIR_META[dir].short}`;
            directions.appendChild(chip);
        });

        const observed = this.el.reconstructionObservedSequence;
        observed.innerHTML = '';
        this.reconstructionData.observedFaces.forEach((face, index) => {
            const card = document.createElement('div');
            card.className = 'target-card observed-card';

            const tag = document.createElement('div');
            tag.className = 'target-step';
            tag.textContent = `观测 ${index + 1}`;

            const canvas = document.createElement('canvas');
            canvas.width = 52;
            canvas.height = 52;
            const ctx = canvas.getContext('2d');
            drawPattern(ctx, face.patternId, face.rotation, 0, 0, 52, '#1e1e3a', face);

            const label = document.createElement('div');
            label.className = 'target-label';
            label.textContent = getPatternLabel(face.patternId);

            const rotation = document.createElement('div');
            rotation.className = 'target-rotation';
            rotation.textContent = `${face.rotation}°`;

            card.appendChild(tag);
            card.appendChild(canvas);
            observed.appendChild(card);
        });
    }

    revealReconstructionAnswers() {
        this.isRevealed = true;
        this.score = 0;

        this.reconstructionData.requiredSlots.forEach((slotKey) => {
            const answerPattern = this.reconstructionAnswers[slotKey];
            const answerRotation = this.reconstructionRotations[slotKey] ?? 0;
            const actualFace = this.reconstructionData.actualFaces[slotKey];

            if (
                answerPattern &&
                answerPattern !== RECONSTRUCTION_UNKNOWN &&
                answerPattern === actualFace.patternId &&
                answerRotation === actualFace.rotation
            ) {
                this.score += 1;
            }
        });

        this.renderReconstructionNet();
        this.updateCubeRendererState();
        this.updateStepUI();
        this.showResults();
    }

    buildReconstructionResultDetail() {
        let html = `<div class="result-note">这道还原题一共提供了 ${this.totalSteps} 次底面观测。只有能够从线索中确定的面会计分，而且图案和方向都要完全正确。</div>`;
        html += '<div class="result-steps">';

        this.reconstructionData.requiredSlots.forEach((slotKey) => {
            const answerPattern = this.reconstructionAnswers[slotKey];
            const answerRotation = this.reconstructionRotations[slotKey] ?? 0;
            const actualFace = this.reconstructionData.actualFaces[slotKey];
            const patternMatched = answerPattern === actualFace.patternId;
            const rotationMatched = answerRotation === actualFace.rotation;
            const matched = !!answerPattern &&
                answerPattern !== RECONSTRUCTION_UNKNOWN &&
                patternMatched &&
                rotationMatched;

            html += `<div class="result-step ${matched ? 'correct' : 'wrong'}">`;
            html += `<span class="result-step-num">${this.getSlotName(slotKey)}</span>`;
            html += `<span class="result-step-icon">${matched ? '✓' : '✕'}</span>`;
            html += '<span class="result-step-detail">';

            if (!answerPattern) {
                html += `未填写，正确答案是 ${this.formatFace(actualFace)}`;
            } else if (answerPattern === RECONSTRUCTION_UNKNOWN) {
                html += `你填了 ?，但这个位置其实可以确定为 ${this.formatFace(actualFace)}`;
            } else if (matched) {
                html += `图案和方向都正确：${this.formatFace(actualFace)}`;
            } else if (patternMatched) {
                html += `图案正确，但方向不对。你填的是 ${getPatternLabel(answerPattern)} ${answerRotation}°，正确应为 ${this.formatFace(actualFace)}`;
            } else {
                html += `你填的是 ${getPatternLabel(answerPattern)} ${answerRotation}°，正确应为 ${this.formatFace(actualFace)}`;
            }

            html += '</span></div>';
        });

        html += '</div>';
        html += `<div class="reference-path">滚动序列：${this.formatDirectionSequence(this.reconstructionData.directions)}</div>`;
        html += `<div class="reference-path">完整答案：${this.buildReconstructionSolutionSummary()}</div>`;
        return html;
    }

    buildReconstructionSolutionSummary() {
        return RECONSTRUCTION_NET_SLOTS
            .map((slot) => `${this.getSlotName(slot.key)}=${this.formatFace(this.reconstructionData.actualFaces[slot.key])}`)
            .join(' | ');
    }

    updateReconstructionUI() {
        const filled = this.countReconstructionFilledSlots();
        const resolvedRequired = this.reconstructionData.requiredSlots.filter((slotKey) => {
            const answer = this.reconstructionAnswers[slotKey];
            return answer && answer !== RECONSTRUCTION_UNKNOWN;
        }).length;

        this.el.submitBtn.classList.toggle('hidden', this.isRevealed);
        this.el.revealBtn.classList.toggle('hidden', this.isRevealed);
        this.el.stepIndicator.textContent = this.isRevealed
            ? `还原得分 ${this.score} / ${this.totalSteps}`
            : `已填写 ${filled} / 6 面，至少可确定 ${this.totalSteps} 面`;

        this.el.reconstructionPalette.querySelectorAll('.pattern-btn').forEach((btn) => {
            btn.disabled = this.isRevealed;
        });

        this.el.reconstructionRotationControl.querySelectorAll('.reconstruction-rot-btn').forEach((btn) => {
            btn.disabled = this.isRevealed || !this.selectedPattern || this.selectedPattern === RECONSTRUCTION_UNKNOWN;
        });

        if (this.isRevealed) {
            this.el.stepHint.textContent = '结果已经揭晓。绿色表示图案和方向都正确，红色表示还有偏差。';
        } else if (!this.selectedPattern) {
            this.el.stepHint.textContent = `先从右侧选择图案，再选择 0° / 90° / 180° / 270°，然后点击左侧对应的面进行填写。当前题目至少可以确定 ${this.totalSteps} 个面。`;
        } else if (this.selectedPattern === RECONSTRUCTION_UNKNOWN) {
            this.el.stepHint.textContent = '当前选择的是 ?。暂时无法确定的面可以先留问号；等你拿到更多线索后再回来补图案和方向。';
        } else {
            this.el.stepHint.textContent = `当前选择 ${getPatternLabel(this.selectedPattern)} ${this.selectedRotation}°。你已经填写了 ${filled} / 6 个面，其中 ${resolvedRequired} / ${this.totalSteps} 个可确定面已给出具体图案。`;
        }
    }

    updateAnswerPreview() {
        if (this.gameMode === 'reconstruct') {
            if (!this.selectedPattern) {
                this.el.reconstructionSelectedInfo.textContent = '先选图案，再选方向，然后点击左侧展开图对应的面进行填写。';
            } else if (this.selectedPattern === RECONSTRUCTION_UNKNOWN) {
                this.el.reconstructionSelectedInfo.textContent = '当前选择：?。这个面暂时无法确定时，可以先留问号。';
            } else {
                this.el.reconstructionSelectedInfo.textContent = `当前选择：${getPatternLabel(this.selectedPattern)} · ${this.selectedRotation}°`;
            }
            return;
        }

        const canvas = this.el.answerPreview;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (this.selectedPattern) {
            drawPattern(ctx, this.selectedPattern, this.selectedRotation, 0, 0, canvas.width, '#1e1e3a');
            ctx.strokeStyle = '#64c8ff';
            ctx.lineWidth = 2;
            ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
            this.el.selectedInfo.textContent = `${getPatternLabel(this.selectedPattern)} · 旋转 ${this.selectedRotation}°`;
        } else {
            ctx.fillStyle = '#1e1e3a';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = 'rgba(255,255,255,0.3)';
            ctx.font = '14px "Outfit", sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('选择图案', canvas.width / 2, canvas.height / 2);
            ctx.strokeStyle = 'rgba(255,255,255,0.2)';
            ctx.lineWidth = 1;
            ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
            this.el.selectedInfo.textContent = '请选择一个图案与方向';
        }
    }

    showResults() {
        this.el.resultPanel.classList.remove('hidden');

        const maxScore = this.totalSteps;
        const pct = maxScore ? Math.round((this.score / maxScore) * 100) : 100;

        let emoji = '👏';
        if (pct < 30) emoji = '🌱';
        else if (pct < 60) emoji = '🧭';
        else if (pct < 90) emoji = '✨';

        let subtitle = '请对照答案回看每一步底面图案与方向。';
        let scoreText = `${this.score} / ${maxScore} 面完全正确`;

        if (this.gameMode === 'reverse') {
            subtitle = '逆向模式只比较你实际滚出来的底面图案序列，不要求和参考路径完全一致。';
            scoreText = `${this.score} / ${maxScore} 步图案匹配`;
        } else if (this.gameMode === 'reconstruct') {
            subtitle = '还原模式要求可确定的面同时答对图案和方向，3D 立方体现在展示的是完整正确答案。';
            scoreText = `${this.score} / ${maxScore} 个可确定面完全正确`;
        }

        this.el.scoreDisplay.innerHTML = `
            <div class="score-emoji">${emoji}</div>
            <div class="score-text">${scoreText}</div>
            <div class="score-pct">${pct}%</div>
            <div class="score-subtitle">${subtitle}</div>
            <div class="score-detail">${this.buildResultDetail()}</div>
        `;

        if (this.levelIndex < LEVELS.length - 1) {
            this.el.nextLevelBtn.classList.remove('hidden');
        } else {
            this.el.nextLevelBtn.classList.add('hidden');
        }
    }

    formatFace(face) {
        if (!face) return '?';
        return `${getPatternLabel(face.patternId)} ${face.rotation}°`;
    }

    formatPattern(face) {
        if (!face) return '?';
        return getPatternLabel(face.patternId);
    }

    formatDirectionSequence(directions) {
        return directions.map((dir, index) => `${index + 1}.${DIR_META[dir].short}`).join(' -> ');
    }

    renderReconstructionNet() {
        const container = this.el.reconstructionNet;
        container.innerHTML = '';

        RECONSTRUCTION_NET_SLOTS.forEach((slot) => {
            const cell = document.createElement('button');
            cell.type = 'button';
            cell.className = 'reconstruction-face-slot';
            cell.dataset.slotKey = slot.key;
            cell.style.gridColumn = `${slot.col}`;
            cell.style.gridRow = `${slot.row}`;
            cell.title = RECONSTRUCTION_SLOT_LABELS[slot.key];
            cell.disabled = this.isRevealed;

            const label = document.createElement('div');
            label.className = 'reconstruction-face-label';
            label.textContent = RECONSTRUCTION_SLOT_LABELS[slot.key];
            cell.appendChild(label);

            const answerPattern = this.reconstructionAnswers[slot.key];
            const answerRotation = this.reconstructionRotations[slot.key] ?? 0;
            const actualFace = this.reconstructionData.actualFaces[slot.key];
            const displayPattern = this.isRevealed ? actualFace.patternId : answerPattern;
            const displayRotation = this.isRevealed ? actualFace.rotation : answerRotation;

            if (!this.isRevealed && answerPattern) {
                cell.classList.add('filled');
            }

            if (this.isRevealed) {
                if (this.reconstructionData.requiredSlotSet.has(slot.key)) {
                    const exact = !!answerPattern &&
                        answerPattern !== RECONSTRUCTION_UNKNOWN &&
                        answerPattern === actualFace.patternId &&
                        answerRotation === actualFace.rotation;
                    cell.classList.add(exact ? 'correct' : 'wrong');
                } else {
                    cell.classList.add('neutral');
                }
            }

            if (!displayPattern) {
                const placeholder = document.createElement('div');
                placeholder.className = 'reconstruction-face-placeholder';
                cell.appendChild(placeholder);
            } else {
                const canvas = document.createElement('canvas');
                canvas.width = 64;
                canvas.height = 64;
                const ctx = canvas.getContext('2d');
                drawPattern(ctx, displayPattern, displayRotation, 0, 0, 64, '#1e1e3a');
                cell.appendChild(canvas);

                const angle = document.createElement('div');
                angle.className = 'reconstruction-face-angle';
                angle.textContent = displayPattern === RECONSTRUCTION_UNKNOWN ? '?' : `${displayRotation}\u00B0`;
                cell.appendChild(angle);
            }

            container.appendChild(cell);
        });
    }

    renderReconstructionChallenge() {
        if (this.gameMode !== 'reconstruct') return;

        const directions = this.el.reconstructionDirections;
        directions.innerHTML = '';
        this.reconstructionData.directions.forEach((dir, index) => {
            const chip = document.createElement('div');
            chip.className = 'direction-chip';
            chip.textContent = `${index + 1}. ${DIR_META[dir].arrow} ${DIR_META[dir].short}`;
            directions.appendChild(chip);
        });

        const observed = this.el.reconstructionObservedSequence;
        observed.innerHTML = '';
        this.reconstructionData.observedFaces.forEach((face, index) => {
            const card = document.createElement('div');
            card.className = 'target-card observed-card';

            const tag = document.createElement('div');
            tag.className = 'target-step';
            tag.textContent = `\u89c2\u6d4b ${index + 1}`;

            const canvas = document.createElement('canvas');
            canvas.width = 52;
            canvas.height = 52;
            const ctx = canvas.getContext('2d');
            drawPattern(ctx, face.patternId, face.rotation, 0, 0, 52, '#1e1e3a', face);

            const label = document.createElement('div');
            label.className = 'target-label';
            label.textContent = getPatternLabel(face.patternId);

            const rotation = document.createElement('div');
            rotation.className = 'target-rotation';
            rotation.textContent = `${face.rotation}\u00B0`;

            card.appendChild(tag);
            card.appendChild(canvas);
            observed.appendChild(card);
        });
    }

    updateAnswerPreview() {
        if (this.gameMode === 'reconstruct') {
            if (!this.selectedPattern) {
                this.el.reconstructionSelectedInfo.textContent = '\u5148\u9009\u56fe\u6848\uff0c\u518d\u9009\u65b9\u5411\uff0c\u7136\u540e\u70b9\u51fb\u5de6\u4fa7\u5bf9\u5e94\u7684\u9762\u8fdb\u884c\u586b\u5199\u3002';
            } else if (this.selectedPattern === RECONSTRUCTION_UNKNOWN) {
                this.el.reconstructionSelectedInfo.textContent = '\u5f53\u524d\u9009\u62e9\uff1a?\u3002\u8fd9\u4e2a\u9762\u6682\u65f6\u65e0\u6cd5\u786e\u5b9a\u65f6\uff0c\u53ef\u4ee5\u5148\u7559\u95ee\u53f7\u3002';
            } else {
                this.el.reconstructionSelectedInfo.textContent = `\u5f53\u524d\u9009\u62e9\uff1a${getPatternLabel(this.selectedPattern)} \u00b7 ${this.selectedRotation}\u00B0`;
            }
            return;
        }

        const canvas = this.el.answerPreview;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (this.selectedPattern) {
            drawPattern(ctx, this.selectedPattern, this.selectedRotation, 0, 0, canvas.width, '#1e1e3a');
            ctx.strokeStyle = '#64c8ff';
            ctx.lineWidth = 2;
            ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
            this.el.selectedInfo.textContent = `${getPatternLabel(this.selectedPattern)} \u00b7 \u65cb\u8f6c ${this.selectedRotation}\u00B0`;
        } else {
            ctx.fillStyle = '#1e1e3a';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = 'rgba(255,255,255,0.3)';
            ctx.font = '14px "Outfit", sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('\u9009\u62e9\u56fe\u6848', canvas.width / 2, canvas.height / 2);
            ctx.strokeStyle = 'rgba(255,255,255,0.2)';
            ctx.lineWidth = 1;
            ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
            this.el.selectedInfo.textContent = '\u8bf7\u9009\u62e9\u4e00\u4e2a\u56fe\u6848\u4e0e\u65b9\u5411';
        }
    }

    formatFace(face) {
        if (!face) return '?';
        return `${getPatternLabel(face.patternId)} ${face.rotation}\u00B0`;
    }

    formatPattern(face) {
        if (!face) return '?';
        return getPatternLabel(face.patternId);
    }

    formatDirectionSequence(directions) {
        return directions.map((dir, index) => `${index + 1}.${DIR_META[dir].short}`).join(' -> ');
    }

    buildReconstructionData() {
        const prompt = this.currentLevel.prompt || {};
        const slotCube = this.createSlotTrackingCube();
        const fallbackSlotSequence = simulatePath(slotCube, this.currentLevel.path)
            .slice(1)
            .map((face) => face.patternId);
        const slotSequence = Array.isArray(prompt.slotSequence) && prompt.slotSequence.length
            ? [...prompt.slotSequence]
            : fallbackSlotSequence;
        const observedSource = Array.isArray(prompt.observedPathFaces) && prompt.observedPathFaces.length
            ? prompt.observedPathFaces
            : (Array.isArray(prompt.observedStampFaces) && prompt.observedStampFaces.length
                ? prompt.observedStampFaces
                : []);
        const observedPathFaces = observedSource.map((face) => ({
            patternId: face.patternId,
            rotation: face.rotation,
            flipHorizontal: Boolean(face.flipHorizontal),
            flipVertical: Boolean(face.flipVertical)
        }));
        const requiredSlots = Array.isArray(prompt.requiredSlots) && prompt.requiredSlots.length
            ? [...prompt.requiredSlots]
            : [...new Set(slotSequence)];

        return {
            directions: Array.isArray(prompt.directions) && prompt.directions.length
                ? [...prompt.directions]
                : [...this.currentLevel.path],
            observedFaces: observedPathFaces,
            observedPathFaces,
            observedStampFaces: observedPathFaces,
            slotSequence,
            requiredSlots,
            requiredSlotSet: new Set(requiredSlots),
            actualFaces: this.getSlotFaceMap(),
            actualPatterns: this.getSlotPatternMap(),
            palettePatterns: [...new Set(observedPathFaces.map((face) => face.patternId))]
        };
    }

    getPlayerReconstructionFaceMap() {
        const result = {};

        RECONSTRUCTION_NET_SLOTS.forEach((slot) => {
            const patternId = this.reconstructionAnswers[slot.key] || RECONSTRUCTION_UNKNOWN;
            result[slot.key] = {
                patternId,
                rotation: patternId === RECONSTRUCTION_UNKNOWN
                    ? 0
                    : (this.reconstructionRotations[slot.key] ?? 0),
                flipHorizontal: false,
                flipVertical: false
            };
        });

        return result;
    }

    buildReconstructionCubeFromFaceMap(faceMap) {
        if (!this.initialCube) {
            return this.getMaskedCubeState(new CubeState([
                { patternId: RECONSTRUCTION_UNKNOWN, rotation: 0 },
                { patternId: RECONSTRUCTION_UNKNOWN, rotation: 0 },
                { patternId: RECONSTRUCTION_UNKNOWN, rotation: 0 },
                { patternId: RECONSTRUCTION_UNKNOWN, rotation: 0 },
                { patternId: RECONSTRUCTION_UNKNOWN, rotation: 0 },
                { patternId: RECONSTRUCTION_UNKNOWN, rotation: 0 }
            ]));
        }

        const cube = this.initialCube.clone();
        const faceIndexMap = {
            TOP: 0,
            BOTTOM: 1,
            FRONT: 2,
            BACK: 3,
            LEFT: 4,
            RIGHT: 5
        };

        Object.entries(faceIndexMap).forEach(([slotKey, faceIndex]) => {
            const sourceFace = faceMap[slotKey] || { patternId: RECONSTRUCTION_UNKNOWN, rotation: 0 };
            const cubeFace = typeof netFaceToCubeFace === 'function'
                ? netFaceToCubeFace(slotKey, sourceFace)
                : sourceFace;

            cube.faces[faceIndex] = {
                patternId: cubeFace.patternId,
                rotation: cubeFace.patternId === RECONSTRUCTION_UNKNOWN ? 0 : cubeFace.rotation,
                flipHorizontal: Boolean(cubeFace.flipHorizontal),
                flipVertical: Boolean(cubeFace.flipVertical)
            };
        });

        return cube;
    }

    rebuildReconstructionValidationTrace() {
        const playerCube = this.buildReconstructionCubeFromFaceMap(this.getPlayerReconstructionFaceMap());

        this.reconstructionValidationStates = typeof simulatePathStates === 'function'
            ? simulatePathStates(playerCube, this.currentLevel.path)
            : [playerCube.clone()];

        const validationFaces = typeof simulatePathViewFaces === 'function'
            ? simulatePathViewFaces(playerCube, this.currentLevel.path)
            : (typeof simulateStampPath === 'function'
                ? simulateStampPath(playerCube, this.currentLevel.path)
                : []);
        this.reconstructionValidationStampFaces = typeof flipFaceSequenceVertically === 'function'
            ? flipFaceSequenceVertically(validationFaces)
            : validationFaces;

        if (this.validationStepIndex >= this.reconstructionValidationStates.length) {
            this.validationStepIndex = Math.max(0, this.reconstructionValidationStates.length - 1);
        }
    }

    getDisplayCubeState() {
        if (this.gameMode === 'reconstruct') {
            if (this.isRevealed && this.reconstructionValidationStates.length) {
                const current = this.reconstructionValidationStates[this.validationStepIndex] || this.reconstructionValidationStates[0];
                return current.clone();
            }
            return this.getReconstructionCubeState();
        }

        if (this.gameMode === 'forward') {
            const index = Math.min(this.currentStep, this.cubeStates.length - 1);
            return this.cubeStates[index];
        }

        return this.cubeStates[this.cubeStates.length - 1];
    }

    renderReconstructionChallenge() {
        if (this.gameMode !== 'reconstruct') return;

        const directions = this.el.reconstructionDirections;
        directions.innerHTML = '';
        this.reconstructionData.directions.forEach((dir, index) => {
            const chip = document.createElement('div');
            chip.className = 'direction-chip';
            chip.textContent = `${index + 1}. ${DIR_META[dir].arrow} ${DIR_META[dir].short}`;
            directions.appendChild(chip);
        });

        const observed = this.el.reconstructionObservedSequence;
        observed.innerHTML = '';
        this.reconstructionData.observedPathFaces.forEach((face, index) => {
            const card = document.createElement('div');
            card.className = 'target-card observed-card';
            const replayFace = this.isRevealed ? this.reconstructionValidationStampFaces[index + 1] : null;

            if (this.isRevealed && this.validationStepIndex === index + 1) {
                card.classList.add('current');
            }
            if (this.isRevealed && replayFace) {
                card.classList.add(this.facesEqual(replayFace, face) ? 'matched' : 'wrong');
            }

            const tag = document.createElement('div');
            tag.className = 'target-step';
            tag.textContent = `\u89c2\u6d4b ${index + 1}`;

            const canvas = document.createElement('canvas');
            canvas.width = 52;
            canvas.height = 52;
            const ctx = canvas.getContext('2d');
            drawPattern(ctx, face.patternId, face.rotation, 0, 0, 52, '#1e1e3a', face);

            const label = document.createElement('div');
            label.className = 'target-label';
            label.textContent = getPatternLabel(face.patternId);

            const rotation = document.createElement('div');
            rotation.className = 'target-rotation';
            rotation.textContent = `${face.rotation}\u00B0`;

            card.appendChild(tag);
            card.appendChild(canvas);
            observed.appendChild(card);
        });
    }

    stepReconstructionValidator(delta) {
        if (this.gameMode !== 'reconstruct' || !this.isRevealed || !this.reconstructionValidationStates.length) {
            return;
        }

        const maxIndex = this.reconstructionValidationStates.length - 1;
        this.validationStepIndex = Math.max(0, Math.min(maxIndex, this.validationStepIndex + delta));
        this.updateCubeRendererState();
        this.renderReconstructionChallenge();
        this.refreshReconstructionValidator();
    }

    resetReconstructionValidatorView() {
        if (!this.cubeRenderer) return;
        if (typeof this.cubeRenderer.resetView === 'function') {
            this.cubeRenderer.resetView();
        } else {
            this.cubeRenderer.resetTransform();
        }
        this.cubeRenderer.updateTextures(this.getDisplayCubeState());
    }

    isReconstructionValidatorOpen() {
        return this.gameMode === 'reconstruct' &&
            this.isRevealed &&
            this.reconstructionValidationStates.length > 0 &&
            this.el.resultPanel.classList.contains('hidden');
    }

    refreshReconstructionValidator() {
        if (!this.el.reconstructionValidatorPanel) return;

        const visible = this.isReconstructionValidatorOpen();
        this.el.reconstructionValidatorPanel.classList.toggle('hidden', !visible);
        if (!visible) return;

        const totalMoves = this.currentLevel.path.length;
        const currentStamp = this.reconstructionValidationStampFaces[this.validationStepIndex];

        if (this.validationStepIndex === 0) {
            this.el.validatorStepInfo.textContent = '\u5f53\u524d\u662f\u8d77\u59cb\u59ff\u6001\uff0c\u8fd8\u672a\u5f00\u59cb\u6309\u9898\u76ee\u8def\u5f84\u6eda\u52a8\u3002';
            this.el.validatorStepFace.textContent = currentStamp
                ? `\u8d77\u59cb\u7acb\u65b9\u4f53\u662f\u6309\u4f60\u7684\u5df2\u63d0\u4ea4\u7b54\u6848\u6e32\u67d3\u7684\uff0c\u6b64\u65f6\u8def\u5f84\u8d77\u70b9\u56fe\u6848\uff08\u4ece\u6b63\u4e0a\u65b9\u5411\u4e0b\u770b\uff09\u4e3a\uff1a${this.formatFace(currentStamp)}`
                : '\u8d77\u59cb\u6b65\u6ca1\u6709\u53ef\u663e\u793a\u7684\u8def\u5f84\u56fe\u6848\u3002';
        } else {
            const dir = this.currentLevel.path[this.validationStepIndex - 1];
            const targetFace = this.reconstructionData.observedPathFaces[this.validationStepIndex - 1];
            const matched = this.facesEqual(currentStamp, targetFace);
            this.el.validatorStepInfo.textContent =
                `\u7b2c ${this.validationStepIndex} / ${totalMoves} \u6b65\uff1a\u6309\u4f60\u586b\u5199\u51fa\u7684\u7acb\u65b9\u4f53\u6267\u884c ${DIR_META[dir].short}\uff0c\u5f97\u5230\u8fd9\u4e00\u6b65\u7684 3D \u72b6\u6001\u3002`;
            this.el.validatorStepFace.textContent = currentStamp && targetFace
                ? `\u4f60\u6eda\u51fa\u7684\u8def\u5f84\u56fe\u6848\uff1a${this.formatFace(currentStamp)}\uff1b\u9898\u76ee\u89c2\u6d4b ${this.validationStepIndex} \u5e94\u4e3a\uff1a${this.formatFace(targetFace)}\u3002${matched ? '\u672c\u6b65\u4e00\u81f4\u3002' : '\u672c\u6b65\u4e0d\u4e00\u81f4\u3002'}`
                : '\u65e0\u5bf9\u5e94\u7684\u8def\u5f84\u89c2\u6d4b\u6570\u636e\u3002';
        }

        this.el.validatorPrevBtn.disabled = this.validationStepIndex <= 0;
        this.el.validatorNextBtn.disabled = this.validationStepIndex >= totalMoves;
    }

    updateReconstructionUI() {
        const filled = this.countReconstructionFilledSlots();
        const resolvedRequired = this.reconstructionData.requiredSlots.filter((slotKey) => {
            const answer = this.reconstructionAnswers[slotKey];
            return answer && answer !== RECONSTRUCTION_UNKNOWN;
        }).length;

        this.el.submitBtn.classList.toggle('hidden', this.isRevealed);
        this.el.revealBtn.classList.toggle('hidden', this.isRevealed);
        this.el.stepIndicator.textContent = this.isRevealed
            ? `\u8fd8\u539f\u5f97\u5206 ${this.score} / ${this.totalSteps}`
            : `\u5df2\u586b\u5199 ${filled} / 6 \u9762\uff0c\u81f3\u5c11\u53ef\u786e\u5b9a ${this.totalSteps} \u9762`;

        this.el.reconstructionPalette.querySelectorAll('.pattern-btn').forEach((btn) => {
            btn.disabled = this.isRevealed;
        });

        this.el.reconstructionRotationControl.querySelectorAll('.reconstruction-rot-btn').forEach((btn) => {
            btn.disabled = this.isRevealed || !this.selectedPattern || this.selectedPattern === RECONSTRUCTION_UNKNOWN;
        });

        if (this.isRevealed) {
            this.el.stepHint.textContent = '\u9898\u9762\u4e2d\u7684\u89c2\u6d4b\u5e8f\u5217\u8868\u793a\u7684\u662f\u4f60\u4ece\u7acb\u65b9\u4f53\u6b63\u4e0a\u65b9\u5411\u4e0b\u770b\u5230\u7684\u8def\u5f84\u56fe\u6848\u4e0e\u65b9\u5411\uff1b\u5de6\u4fa7\u9a8c\u8bc1\u5668\u56de\u653e\u53ef\u4ee5\u9010\u6b65\u68c0\u67e5\u6bcf\u4e00\u6b65\u3002';
        } else if (!this.selectedPattern) {
            this.el.stepHint.textContent = `\u5148\u4ece\u53f3\u4fa7\u9009\u62e9\u56fe\u6848\uff0c\u518d\u9009\u62e9 0\u00b0 / 90\u00b0 / 180\u00b0 / 270\u00b0\uff0c\u7136\u540e\u70b9\u51fb\u5de6\u4fa7\u5bf9\u5e94\u7684\u9762\u8fdb\u884c\u586b\u5199\u3002\u9898\u9762\u89c2\u6d4b\u7684\u662f\u4f60\u4ece\u7acb\u65b9\u4f53\u6b63\u4e0a\u65b9\u5411\u4e0b\u770b\u5230\u7684\u8def\u5f84\u56fe\u6848\uff0c\u800c\u4f60\u586b\u5199\u7684\u662f\u7acb\u65b9\u4f53\u5916\u8868\u9762\u7684\u56fe\u6848\u4e0e\u65b9\u5411\u3002`;
        } else if (this.selectedPattern === RECONSTRUCTION_UNKNOWN) {
            this.el.stepHint.textContent = '\u5f53\u524d\u9009\u62e9\u7684\u662f ?\u3002\u6682\u65f6\u65e0\u6cd5\u786e\u5b9a\u7684\u9762\u53ef\u4ee5\u5148\u7559\u95ee\u53f7\uff1b\u7b49\u7ebf\u7d22\u66f4\u591a\u65f6\u518d\u56de\u6765\u8865\u56fe\u6848\u548c\u65b9\u5411\u3002';
        } else {
            this.el.stepHint.textContent = `\u5f53\u524d\u9009\u62e9 ${getPatternLabel(this.selectedPattern)} ${this.selectedRotation}\u00B0\u3002\u4f60\u5df2\u7ecf\u586b\u5199\u4e86 ${filled} / 6 \u4e2a\u9762\uff0c\u5176\u4e2d ${resolvedRequired} / ${this.totalSteps} \u4e2a\u53ef\u786e\u5b9a\u9762\u5df2\u7ed9\u51fa\u5177\u4f53\u56fe\u6848\u3002`;
        }

        this.refreshReconstructionValidator();
    }

    showResults() {
        if (this.gameMode === 'reconstruct') {
            this.el.resultPanel.classList.add('hidden');
            this.validationStepIndex = 0;
            this.updateCubeRendererState();
            this.renderReconstructionChallenge();
            this.refreshReconstructionValidator();
            return;
        }

        this.el.resultPanel.classList.remove('hidden');

        const maxScore = this.totalSteps;
        const pct = maxScore ? Math.round((this.score / maxScore) * 100) : 100;

        let emoji = '👏';
        if (pct < 30) emoji = '🌱';
        else if (pct < 60) emoji = '🧭';
        else if (pct < 90) emoji = '✨';

        let subtitle = '请对照答案回看每一步底面图案与方向。';
        let scoreText = `${this.score} / ${maxScore} 面完全正确`;

        if (this.gameMode === 'reverse') {
            subtitle = '逆向模式只比较你实际滚出来的底面图案序列，不要求和参考路径完全一致。';
            scoreText = `${this.score} / ${maxScore} 步图案匹配`;
        }

        this.el.scoreDisplay.innerHTML = `
            <div class="score-emoji">${emoji}</div>
            <div class="score-text">${scoreText}</div>
            <div class="score-pct">${pct}%</div>
            <div class="score-subtitle">${subtitle}</div>
            <div class="score-detail">${this.buildResultDetail()}</div>
        `;

        if (this.levelIndex < LEVELS.length - 1) {
            this.el.nextLevelBtn.classList.remove('hidden');
        } else {
            this.el.nextLevelBtn.classList.add('hidden');
        }
    }

    formatFace(face) {
        if (!face || face.patternId === RECONSTRUCTION_UNKNOWN) return '?';
        const transforms = [];
        if (face.flipHorizontal) transforms.push('\u5de6\u53f3\u7ffb\u8f6c');
        if (face.flipVertical) transforms.push('\u4e0a\u4e0b\u7ffb\u8f6c');
        return `${getPatternLabel(face.patternId)} ${face.rotation}\u00B0${transforms.length ? ` ${transforms.join(' / ')}` : ''}`;
    }

    getReconstructionTemplateFaceMap() {
        const templateFaces = this.currentLevel?.answers?.solutionFaces || this.currentLevel?.solutionFaces;
        if (templateFaces) {
            return {
                TOP: { ...templateFaces.TOP, flipHorizontal: Boolean(templateFaces.TOP?.flipHorizontal), flipVertical: Boolean(templateFaces.TOP?.flipVertical) },
                BOTTOM: { ...templateFaces.BOTTOM, flipHorizontal: Boolean(templateFaces.BOTTOM?.flipHorizontal), flipVertical: Boolean(templateFaces.BOTTOM?.flipVertical) },
                FRONT: { ...templateFaces.FRONT, flipHorizontal: Boolean(templateFaces.FRONT?.flipHorizontal), flipVertical: Boolean(templateFaces.FRONT?.flipVertical) },
                BACK: { ...templateFaces.BACK, flipHorizontal: Boolean(templateFaces.BACK?.flipHorizontal), flipVertical: Boolean(templateFaces.BACK?.flipVertical) },
                LEFT: { ...templateFaces.LEFT, flipHorizontal: Boolean(templateFaces.LEFT?.flipHorizontal), flipVertical: Boolean(templateFaces.LEFT?.flipVertical) },
                RIGHT: { ...templateFaces.RIGHT, flipHorizontal: Boolean(templateFaces.RIGHT?.flipHorizontal), flipVertical: Boolean(templateFaces.RIGHT?.flipVertical) }
            };
        }

        const requiredSet = new Set(this.currentLevel?.prompt?.requiredSlots || []);
        const netFaces = this.currentLevel?.netFaces || [];
        const result = {};

        RECONSTRUCTION_NET_SLOTS.forEach((slot) => {
            result[slot.key] = requiredSet.has(slot.key)
                ? {
                    patternId: netFaces[slot.netIndex]?.patternId,
                    rotation: netFaces[slot.netIndex]?.rotation ?? 0,
                    flipHorizontal: Boolean(netFaces[slot.netIndex]?.flipHorizontal),
                    flipVertical: Boolean(netFaces[slot.netIndex]?.flipVertical)
                }
                : {
                    patternId: RECONSTRUCTION_UNKNOWN,
                    rotation: 0,
                    flipHorizontal: false,
                    flipVertical: false
                };
        });

        return result;
    }

    getReconstructionTrueFaceMap() {
        const trueFaces = this.currentLevel?.answers?.trueSolutionFaces || this.currentLevel?.trueSolutionFaces;
        if (trueFaces) {
            return {
                TOP: { ...trueFaces.TOP, flipHorizontal: Boolean(trueFaces.TOP?.flipHorizontal), flipVertical: Boolean(trueFaces.TOP?.flipVertical) },
                BOTTOM: { ...trueFaces.BOTTOM, flipHorizontal: Boolean(trueFaces.BOTTOM?.flipHorizontal), flipVertical: Boolean(trueFaces.BOTTOM?.flipVertical) },
                FRONT: { ...trueFaces.FRONT, flipHorizontal: Boolean(trueFaces.FRONT?.flipHorizontal), flipVertical: Boolean(trueFaces.FRONT?.flipVertical) },
                BACK: { ...trueFaces.BACK, flipHorizontal: Boolean(trueFaces.BACK?.flipHorizontal), flipVertical: Boolean(trueFaces.BACK?.flipVertical) },
                LEFT: { ...trueFaces.LEFT, flipHorizontal: Boolean(trueFaces.LEFT?.flipHorizontal), flipVertical: Boolean(trueFaces.LEFT?.flipVertical) },
                RIGHT: { ...trueFaces.RIGHT, flipHorizontal: Boolean(trueFaces.RIGHT?.flipHorizontal), flipVertical: Boolean(trueFaces.RIGHT?.flipVertical) }
            };
        }

        return {
            TOP: {
                patternId: this.initialCube.top.patternId,
                rotation: this.initialCube.top.rotation,
                flipHorizontal: Boolean(this.initialCube.top.flipHorizontal),
                flipVertical: Boolean(this.initialCube.top.flipVertical)
            },
            BOTTOM: {
                patternId: this.initialCube.bottom.patternId,
                rotation: this.initialCube.bottom.rotation,
                flipHorizontal: Boolean(this.initialCube.bottom.flipHorizontal),
                flipVertical: Boolean(this.initialCube.bottom.flipVertical)
            },
            FRONT: {
                patternId: this.initialCube.front.patternId,
                rotation: this.initialCube.front.rotation,
                flipHorizontal: Boolean(this.initialCube.front.flipHorizontal),
                flipVertical: Boolean(this.initialCube.front.flipVertical)
            },
            BACK: {
                patternId: this.initialCube.back.patternId,
                rotation: this.initialCube.back.rotation,
                flipHorizontal: Boolean(this.initialCube.back.flipHorizontal),
                flipVertical: Boolean(this.initialCube.back.flipVertical)
            },
            LEFT: {
                patternId: this.initialCube.left.patternId,
                rotation: this.initialCube.left.rotation,
                flipHorizontal: Boolean(this.initialCube.left.flipHorizontal),
                flipVertical: Boolean(this.initialCube.left.flipVertical)
            },
            RIGHT: {
                patternId: this.initialCube.right.patternId,
                rotation: this.initialCube.right.rotation,
                flipHorizontal: Boolean(this.initialCube.right.flipHorizontal),
                flipVertical: Boolean(this.initialCube.right.flipVertical)
            }
        };
    }

    buildReconstructionData() {
        const prompt = this.currentLevel.prompt || {};
        const slotCube = this.createSlotTrackingCube();
        const fallbackSlotSequence = simulatePath(slotCube, this.currentLevel.path)
            .slice(1)
            .map((face) => face.patternId);
        const slotSequence = Array.isArray(prompt.slotSequence) && prompt.slotSequence.length
            ? [...prompt.slotSequence]
            : fallbackSlotSequence;
        const observedSource = Array.isArray(prompt.observedPathFaces) && prompt.observedPathFaces.length
            ? prompt.observedPathFaces
            : (Array.isArray(prompt.observedStampFaces) && prompt.observedStampFaces.length
                ? prompt.observedStampFaces
                : []);
        const observedPathFaces = observedSource.map((face) => ({
            patternId: face.patternId,
            rotation: face.rotation,
            flipHorizontal: Boolean(face.flipHorizontal),
            flipVertical: Boolean(face.flipVertical)
        }));
        const requiredSlots = Array.isArray(prompt.requiredSlots) && prompt.requiredSlots.length
            ? [...prompt.requiredSlots]
            : [...new Set(slotSequence)];
        const requiredSlotSet = new Set(requiredSlots);
        const actualFaces = this.getReconstructionTemplateFaceMap();
        const trueFaces = this.getReconstructionTrueFaceMap();

        return {
            directions: Array.isArray(prompt.directions) && prompt.directions.length
                ? [...prompt.directions]
                : [...this.currentLevel.path],
            observedFaces: observedPathFaces,
            observedPathFaces,
            observedStampFaces: observedPathFaces,
            slotSequence,
            requiredSlots,
            requiredSlotSet,
            undeterminedSlots: RECONSTRUCTION_NET_SLOTS
                .map((slot) => slot.key)
                .filter((slotKey) => !requiredSlotSet.has(slotKey)),
            determinedCount: requiredSlots.length,
            actualFaces,
            trueFaces,
            actualPatterns: Object.fromEntries(
                Object.entries(actualFaces).map(([slotKey, face]) => [slotKey, face.patternId])
            ),
            palettePatterns: [...new Set(observedPathFaces.map((face) => face.patternId))]
        };
    }

    getReconstructionCubeState() {
        return this.buildReconstructionCubeFromFaceMap(this.getPlayerReconstructionFaceMap());
    }

    renderReconstructionNet() {
        const container = this.el.reconstructionNet;
        container.innerHTML = '';

        RECONSTRUCTION_NET_SLOTS.forEach((slot) => {
            const cell = document.createElement('button');
            cell.type = 'button';
            cell.className = 'reconstruction-face-slot';
            cell.dataset.slotKey = slot.key;
            cell.style.gridColumn = `${slot.col}`;
            cell.style.gridRow = `${slot.row}`;
            cell.title = RECONSTRUCTION_SLOT_LABELS[slot.key];
            cell.disabled = this.isRevealed;

            const label = document.createElement('div');
            label.className = 'reconstruction-face-label';
            label.textContent = RECONSTRUCTION_SLOT_LABELS[slot.key];
            cell.appendChild(label);

            const answerPattern = this.reconstructionAnswers[slot.key];
            const answerRotation = this.reconstructionRotations[slot.key] ?? 0;
            const targetFace = this.reconstructionData.actualFaces[slot.key];
            const displayPattern = this.isRevealed ? targetFace.patternId : answerPattern;
            const displayRotation = this.isRevealed ? targetFace.rotation : answerRotation;

            if (!this.isRevealed && answerPattern) {
                cell.classList.add('filled');
            }

            if (this.isRevealed) {
                const exact = targetFace.patternId === RECONSTRUCTION_UNKNOWN
                    ? answerPattern === RECONSTRUCTION_UNKNOWN
                    : !!answerPattern &&
                        answerPattern !== RECONSTRUCTION_UNKNOWN &&
                        answerPattern === targetFace.patternId &&
                        answerRotation === targetFace.rotation;
                cell.classList.add(exact ? 'correct' : 'wrong');
            }

            if (!displayPattern) {
                const placeholder = document.createElement('div');
                placeholder.className = 'reconstruction-face-placeholder';
                cell.appendChild(placeholder);
            } else {
                const canvas = document.createElement('canvas');
                canvas.width = 64;
                canvas.height = 64;
                const ctx = canvas.getContext('2d');
                drawPattern(
                    ctx,
                    displayPattern,
                    displayPattern === RECONSTRUCTION_UNKNOWN ? 0 : displayRotation,
                    0,
                    0,
                    64,
                    '#1e1e3a',
                    this.isRevealed ? targetFace : { patternId: displayPattern, rotation: displayRotation }
                );
                cell.appendChild(canvas);

                const angle = document.createElement('div');
                angle.className = 'reconstruction-face-angle';
                angle.textContent = displayPattern === RECONSTRUCTION_UNKNOWN ? '?' : `${displayRotation}\u00B0`;
                cell.appendChild(angle);
            }

            container.appendChild(cell);
        });
    }

    revealReconstructionAnswers() {
        this.isRevealed = true;
        this.score = 0;

        RECONSTRUCTION_NET_SLOTS.forEach((slot) => {
            const slotKey = slot.key;
            const answerPattern = this.reconstructionAnswers[slotKey];
            const answerRotation = this.reconstructionRotations[slotKey] ?? 0;
            const targetFace = this.reconstructionData.actualFaces[slotKey];

            const matched = targetFace.patternId === RECONSTRUCTION_UNKNOWN
                ? answerPattern === RECONSTRUCTION_UNKNOWN
                : !!answerPattern &&
                    answerPattern !== RECONSTRUCTION_UNKNOWN &&
                    answerPattern === targetFace.patternId &&
                    answerRotation === targetFace.rotation;

            if (matched) {
                this.score += 1;
            }
        });

        this.rebuildReconstructionValidationTrace();
        this.renderReconstructionNet();
        this.updateCubeRendererState();
        this.updateStepUI();
        this.showResults();
    }

    buildReconstructionResultDetail() {
        const determinedCount = this.reconstructionData.determinedCount;
        const unknownCount = RECONSTRUCTION_NET_SLOTS.length - determinedCount;
        let html = `<div class="result-note">本题共有 6 个面需要填写。其中 ${determinedCount} 个面可以从题面推出，其余 ${unknownCount} 个面标准答案为 ?。当答案是 ? 时，不需要填写方向。</div>`;
        html += '<div class="result-steps">';

        RECONSTRUCTION_NET_SLOTS.forEach((slot) => {
            const slotKey = slot.key;
            const answerPattern = this.reconstructionAnswers[slotKey];
            const answerRotation = this.reconstructionRotations[slotKey] ?? 0;
            const targetFace = this.reconstructionData.actualFaces[slotKey];

            const matched = targetFace.patternId === RECONSTRUCTION_UNKNOWN
                ? answerPattern === RECONSTRUCTION_UNKNOWN
                : !!answerPattern &&
                    answerPattern !== RECONSTRUCTION_UNKNOWN &&
                    answerPattern === targetFace.patternId &&
                    answerRotation === targetFace.rotation;

            html += `<div class="result-step ${matched ? 'correct' : 'wrong'}">`;
            html += `<span class="result-step-num">${this.getSlotName(slotKey)}</span>`;
            html += `<span class="result-step-icon">${matched ? '✓' : '✗'}</span>`;
            html += '<span class="result-step-detail">';

            if (targetFace.patternId === RECONSTRUCTION_UNKNOWN) {
                if (answerPattern === RECONSTRUCTION_UNKNOWN) {
                    html += '这个面无法由题面唯一推出，标准填写为 ?，你的填写正确。';
                } else if (!answerPattern) {
                    html += '这个面无法由题面唯一推出，标准填写为 ?。';
                } else {
                    html += `这个面无法由题面唯一推出，标准填写应为 ?，而不是 ${getPatternLabel(answerPattern)}${answerPattern === RECONSTRUCTION_UNKNOWN ? '' : ` ${answerRotation}°`}。`;
                }
            } else if (!answerPattern) {
                html += `未填写，标准答案是 ${this.formatFace(targetFace)}。`;
            } else if (answerPattern === RECONSTRUCTION_UNKNOWN) {
                html += `这里其实可以推出，标准答案是 ${this.formatFace(targetFace)}，不能填 ?。`;
            } else if (matched) {
                html += `图案和方向都正确：${this.formatFace(targetFace)}。`;
            } else if (answerPattern === targetFace.patternId) {
                html += `图案正确，但方向不对。你填写的是 ${getPatternLabel(answerPattern)} ${answerRotation}°，标准答案是 ${this.formatFace(targetFace)}。`;
            } else {
                html += `你填写的是 ${getPatternLabel(answerPattern)} ${answerRotation}°，标准答案是 ${this.formatFace(targetFace)}。`;
            }

            html += '</span></div>';
        });

        html += '</div>';
        html += `<div class="reference-path">滚动序列：${this.formatDirectionSequence(this.reconstructionData.directions)}</div>`;
        html += `<div class="reference-path">标准填写：${this.buildReconstructionSolutionSummary()}</div>`;
        return html;
    }

    buildReconstructionSolutionSummary() {
        return RECONSTRUCTION_NET_SLOTS
            .map((slot) => `${this.getSlotName(slot.key)}=${this.formatFace(this.reconstructionData.actualFaces[slot.key])}`)
            .join(' | ');
    }

    updateReconstructionUI() {
        const filled = this.countReconstructionFilledSlots();
        const determinedCount = this.reconstructionData.determinedCount;
        const unknownCount = RECONSTRUCTION_NET_SLOTS.length - determinedCount;

        this.el.submitBtn.classList.toggle('hidden', this.isRevealed);
        this.el.revealBtn.classList.toggle('hidden', this.isRevealed);
        this.el.stepIndicator.textContent = this.isRevealed
            ? `还原得分 ${this.score} / ${RECONSTRUCTION_NET_SLOTS.length}`
            : `已填写 ${filled} / 6 面，可推出 ${determinedCount} 面，其余 ${unknownCount} 面应填 ?`;

        this.el.reconstructionPalette.querySelectorAll('.pattern-btn').forEach((btn) => {
            btn.disabled = this.isRevealed;
        });

        this.el.reconstructionRotationControl.querySelectorAll('.reconstruction-rot-btn').forEach((btn) => {
            btn.disabled = this.isRevealed;
        });

        if (this.isRevealed) {
            this.el.stepHint.textContent = `结果已揭晓。绿色表示该面的标准填写正确；若某个面本来无法唯一推出，它的标准答案就是 ?。左侧验证器仍会用真实立方体逐步回放。`;
        } else if (!this.selectedPattern) {
            this.el.stepHint.textContent = `先从右侧选择图案，再选择 0° / 90° / 180° / 270°，然后点击左侧对应的面进行填写。本题可推出 ${determinedCount} 个面，其余 ${unknownCount} 个面的标准填写为 ?。`;
        } else if (this.selectedPattern === RECONSTRUCTION_UNKNOWN) {
            this.el.stepHint.textContent = '当前选择的是 ?。如果某个面无法从题面唯一推出，标准答案就是 ?，此时不需要填写方向。';
        } else {
            this.el.stepHint.textContent = `当前选择 ${getPatternLabel(this.selectedPattern)} ${this.selectedRotation}°。你已经填写了 ${filled} / 6 个面；别忘了无法推出的面应填写 ?。`;
        }

        this.refreshReconstructionValidator();
    }

    openReconstructionValidator() {
        if (this.gameMode !== 'reconstruct' || !this.isRevealed) return;

        this.el.resultPanel.classList.add('hidden');
        this.rebuildReconstructionValidationTrace();
        this.validationStepIndex = 0;
        this.updateCubeRendererState();
        this.renderReconstructionChallenge();
        this.refreshReconstructionValidator();
        this.resetReconstructionValidatorView();
    }

    showResults() {
        this.el.resultPanel.classList.remove('hidden');

        const maxScore = this.totalSteps;
        const pct = maxScore ? Math.round((this.score / maxScore) * 100) : 100;

        let emoji = '\uD83C\uDF89';
        if (pct < 30) emoji = '\uD83D\uDE35';
        else if (pct < 60) emoji = '\uD83D\uDE15';
        else if (pct < 90) emoji = '\uD83D\uDE42';

        let subtitle = '';
        let scoreText = '';

        if (this.gameMode === 'forward') {
            subtitle = '\u672c\u5173\u6309\u6bcf\u4e00\u6b65\u7684\u5e95\u9762\u56fe\u6848\u548c\u65b9\u5411\u8fdb\u884c\u5224\u5206\u3002';
            scoreText = `${this.score} / ${maxScore} \u6b65\u9884\u6d4b\u6b63\u786e`;
        } else if (this.gameMode === 'reverse') {
            subtitle = '\u672c\u5173\u6309\u4f60\u8bbe\u8ba1\u51fa\u7684\u5e95\u9762\u56fe\u6848\u5e8f\u5217\u4e0e\u76ee\u6807\u5e8f\u5217\u662f\u5426\u4e00\u81f4\u8fdb\u884c\u5224\u5206\u3002';
            scoreText = `${this.score} / ${maxScore} \u4e2a\u76ee\u6807\u6b65\u9aa4\u547d\u4e2d`;
        } else {
            const determinedCount = this.reconstructionData?.determinedCount ?? this.reconstructionData?.requiredSlots?.length ?? 0;
            const unknownCount = RECONSTRUCTION_NET_SLOTS.length - determinedCount;
            subtitle = `\u672c\u5173\u9700\u8981\u586b\u5199 6 \u4e2a\u9762\uff0c\u5176\u4e2d ${determinedCount} \u4e2a\u9762\u53ef\u4ee5\u63a8\u51fa\uff0c\u53e6\u5916 ${unknownCount} \u4e2a\u9762\u7684\u6807\u51c6\u7b54\u6848\u662f ?\u3002\u70b9\u51fb Debug \u53ef\u8fdb\u5165\u9a8c\u8bc1\u5668\u9010\u6b65\u56de\u653e\u3002`;
            scoreText = `${this.score} / ${maxScore} \u4e2a\u5c55\u5f00\u56fe\u683c\u5b50\u586b\u5199\u6b63\u786e`;
        }

        this.el.scoreDisplay.innerHTML = `
            <div class="score-emoji">${emoji}</div>
            <div class="score-text">${scoreText}</div>
            <div class="score-pct">${pct}%</div>
            <div class="score-subtitle">${subtitle}</div>
            <div class="score-detail">${this.buildResultDetail()}</div>
        `;

        if (this.el.validatorOpenBtn) {
            this.el.validatorOpenBtn.classList.toggle('hidden', this.gameMode !== 'reconstruct');
        }

        if (this.gameMode === 'reconstruct') {
            this.validationStepIndex = 0;
            this.updateCubeRendererState();
            this.renderReconstructionChallenge();
            this.refreshReconstructionValidator();
        }

        if (this.levelIndex < LEVELS.length - 1) {
            this.el.nextLevelBtn.classList.remove('hidden');
        } else {
            this.el.nextLevelBtn.classList.add('hidden');
        }
    }

    showToast(message) {
        let toast = document.getElementById('toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'toast';
            document.body.appendChild(toast);
        }

        toast.textContent = message;
        toast.classList.add('show');

        clearTimeout(this.toastTimer);
        this.toastTimer = setTimeout(() => {
            toast.classList.remove('show');
        }, 2000);
    }
}

window.addEventListener('DOMContentLoaded', async () => {
    try {
        if (typeof loadLevelsBundle === 'function') {
            await loadLevelsBundle();
        }
    } catch (error) {
        console.error('[game] Failed to load levels bundle:', error);
    }

    window.game = new Game();
});
