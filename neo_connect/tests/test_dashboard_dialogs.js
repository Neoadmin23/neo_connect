/* Run with node: verifies rejected setup requests do not escape the dialog callback. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let dialog;
const context = {
    __: value => value,
    frappe: {pages: {'magento-dashboard': {}}, ui: {Dialog: class {
        constructor(options) { this.options = options; dialog = this; }
        show() {} hide() { this.hidden = true; }
        disable_primary_action() { this.disabled = true; }
        enable_primary_action() { this.disabled = false; }
    }}}
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,
    '../neo_connect/page/magento_dashboard/magento_dashboard.js'), 'utf8') +
    '\nthis.Dashboard = MagentoDashboard;', context);
(async () => {
    for (const method of ['setup', 'edit_client']) {
        const page = Object.create(context.Dashboard.prototype);
        page.current = {company: 'Test', defaults: {}, security: {}, name: 'Client'};
        page.business_fields = () => []; page.security_fields = () => [];
        page.api = async () => { throw new Error('Server validation already displayed by frappe.call'); };
        page[method]();
        await assert.doesNotReject(() => dialog.options.primary_action({custom_defaults: '{}'}));
        assert.equal(dialog.disabled, false, method + ' must allow correction and retry');
        assert.equal(dialog.hidden, undefined, method + ' must retain the dialog and entered values');
    }
    console.log('2 dialog rejection/retry cases passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
