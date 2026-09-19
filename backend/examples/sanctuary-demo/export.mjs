// Export the accepted books through Vite's TypeScript loader, without mounting a UI.
import { createServer } from '../../../frontend/demo/node_modules/vite/dist/node/index.js';
import { writeFile, mkdir } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../../frontend/demo');
const output = resolve(process.argv[2]);
const server = await createServer({ root, server: { middlewareMode: true }, appType: 'custom' });
try {
  const { createStudyFixtures } = await server.ssrLoadModule('/prototypes/tree-of-wisdom/text/studyFixtures.ts');
  const fixtures = Object.values(createStudyFixtures()).filter(fixture => ['analysis', 'symmetry', 'light'].includes(fixture.sample.id));
  await mkdir(dirname(output), { recursive: true });
  await writeFile(output, JSON.stringify(fixtures, null, 2));
  console.log(`Exported ${fixtures.length} accepted books`);
} finally { await server.close(); }
