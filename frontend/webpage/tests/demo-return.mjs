import assert from 'node:assert/strict';
import { demoReturnUrl } from '../../shared/composables/desktopEntry.js';

for (const destination of ['/demo', '/demo/']) {
  assert.equal(demoReturnUrl(destination, 'https://theumst.com/'), '/demo/');
  assert.equal(demoReturnUrl(destination, 'https://theumst.cn/'), '/demo/');
  assert.equal(demoReturnUrl(destination, 'http://127.0.0.1:5173/'), 'http://127.0.0.1:5175/demo/');
}
for (const destination of ['//evil.invalid/demo/', 'https://evil.invalid/demo/', '/demo/../other', '/demo/?next=https://evil.invalid', '/dashboard/']) {
  assert.equal(demoReturnUrl(destination, 'https://theumst.com/'), null);
}
console.log('Demo login returns stay on the selected host and reject unapproved destinations.');
