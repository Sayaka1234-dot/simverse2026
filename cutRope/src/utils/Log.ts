const VITE_ENV = (import.meta as ImportMeta & { env?: { DEV?: boolean } }).env;
const IS_DEV = Boolean(VITE_ENV?.DEV);

class Log {
    /**
     * Logs a debug message when running in development mode.
     */
    static debug(message: string) {
        if (IS_DEV) {
            console.log(`CTR debug: ${message}`);
        }
    }

    /**
     * Logs an error message when running in development mode.
     */
    static alert(message: string) {
        if (IS_DEV) {
            console.error(`CTR encountered an error: ${message}`);
            Log.debug(message);
        }
    }
}

export default Log;
