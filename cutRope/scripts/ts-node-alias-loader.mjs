import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { resolve as tsResolve, load, getFormat, transformSource } from "ts-node/esm";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");
const srcRoot = path.join(projectRoot, "src");

const resolveWithExtensions = (basePath) => {
    if (path.extname(basePath)) {
        return basePath;
    }

    const candidates = [
        `${basePath}.ts`,
        `${basePath}.tsx`,
        `${basePath}.js`,
        `${basePath}.mjs`,
        path.join(basePath, "index.ts"),
        path.join(basePath, "index.tsx"),
        path.join(basePath, "index.js"),
        path.join(basePath, "index.mjs"),
    ];

    for (const candidate of candidates) {
        if (fs.existsSync(candidate)) {
            return candidate;
        }
    }

    return basePath;
};

export async function resolve(specifier, context, defaultResolve) {
    if (specifier.startsWith("@/")) {
        const subPath = specifier.slice(2);
        const resolvedPath = resolveWithExtensions(path.join(srcRoot, subPath));
        const url = pathToFileURL(resolvedPath).href;
        return { url, shortCircuit: true };
    }

    if (specifier.startsWith(".") || specifier.startsWith("/")) {
        const parentPath = context.parentURL
            ? fileURLToPath(context.parentURL)
            : process.cwd();
        const basePath = specifier.startsWith("/")
            ? specifier
            : path.resolve(path.dirname(parentPath), specifier);
        const resolvedPath = resolveWithExtensions(basePath);
        if (fs.existsSync(resolvedPath)) {
            const url = pathToFileURL(resolvedPath).href;
            return { url, shortCircuit: true };
        }
    }

    return tsResolve(specifier, context, defaultResolve);
}

export { load, getFormat, transformSource };
