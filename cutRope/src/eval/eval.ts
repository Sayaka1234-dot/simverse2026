import { ensureEvalReady, evaluateLevel } from "@/eval/LevelEvaluator";

const levelInput = document.getElementById("evalLevel") as HTMLInputElement | null;
const cmdInput = document.getElementById("evalCommands") as HTMLTextAreaElement | null;
const runButton = document.getElementById("evalRun") as HTMLButtonElement | null;
const output = document.getElementById("evalOutput") as HTMLPreElement | null;

const setOutput = (text: string) => {
    if (output) {
        output.textContent = text;
    }
};

const runEval = async (
    levelFile: string,
    commands: string,
    options: { maxSeconds?: number; stepSeconds?: number } = {}
) => {
    setOutput("Running evaluation...");
    try {
        await ensureEvalReady();
        const result = await evaluateLevel({ levelFile, commands, ...options });
        setOutput(JSON.stringify(result, null, 2));
        return result;
    } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        setOutput(`Error: ${msg}`);
        throw error;
    }
};

if (runButton) {
    runButton.addEventListener("click", () => {
        const levelFile = levelInput?.value?.trim() || "";
        const commands = cmdInput?.value ?? "";
        void runEval(levelFile, commands);
    });
}

const params = new URLSearchParams(window.location.search);
const paramLevel = params.get("level");
const paramCmd = params.get("cmd");
if (paramLevel && paramCmd) {
    const decodedCmd = paramCmd.replace(/\\n/g, "\n");
    if (levelInput) {
        levelInput.value = paramLevel;
    }
    if (cmdInput) {
        cmdInput.value = decodedCmd;
    }
    void runEval(paramLevel, decodedCmd);
}

declare global {
    interface Window {
        evalLevel?: (
            levelFile: string,
            commands: string,
            options?: { maxSeconds?: number; stepSeconds?: number }
        ) => Promise<unknown>;
    }
}

window.evalLevel = (
    levelFile: string,
    commands: string,
    options?: { maxSeconds?: number; stepSeconds?: number }
) => runEval(levelFile, commands, options);
