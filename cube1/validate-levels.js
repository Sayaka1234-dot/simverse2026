const {
    MODE_KEYS,
    collectCatalogFromDisk,
    writeCatalogAssets
} = require('./level-catalog');

function main() {
    const catalog = collectCatalogFromDisk();
    writeCatalogAssets(catalog);

    const parts = MODE_KEYS.map((mode) => {
        const count = catalog.modes[mode]?.levels?.length ?? 0;
        return `${mode}: ${count}`;
    });

    console.log(`Validated level catalog successfully. ${parts.join(', ')}`);
    console.log('Wrote levels/index.json and levels/catalog.generated.js');
}

if (require.main === module) {
    main();
}
