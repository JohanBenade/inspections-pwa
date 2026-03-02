const { defineConfig, devices } = require('@playwright/test');
module.exports = defineConfig({
    testDir: './tests',
    timeout: 60000,
    retries: 0,
    reporter: [['html', { open: 'never' }], ['list']],
    use: {
        baseURL: 'https://inspections.archpractice.co.za',
        trace: 'on-first-retry',
        screenshot: 'only-on-failure',
        video: 'retain-on-failure',
    },
    projects: [
        { name: 'iPhone 14', use: { ...devices['iPhone 14'], hasTouch: true } },
        { name: 'Desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 720 } } },
    ],
});
