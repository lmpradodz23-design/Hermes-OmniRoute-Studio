import type { TestProjectConfiguration } from 'vitest/config'
import { defineConfig } from 'vitest/config'

const reactUi: TestProjectConfiguration = {
  extends: './vite.config.ts',
  test: {
    name: 'ui',
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    globals: true,
    // The first test in each file pays jsdom env init + full module transform,
    // which can exceed Vitest's default under CI/load. Windows cold starts on
    // the full Capabilities and messaging views routinely need 18–26s, so use
    // the same finite ceiling as the native integration project. This keeps
    // slow startup from cascading into overlapping act() failures without
    // turning a genuinely hung test into an unbounded wait.
    testTimeout: 30_000
  }
}

const electronNative: TestProjectConfiguration = {
  test: {
    name: 'electron',
    environment: 'node',
    include: ['electron/**/*.test.ts', 'scripts/**.test.{ts,mjs}'],
    exclude: ['scripts/run-short-session-hang-repro.test.mjs'],
    // Git for Windows, PowerShell startup, and real ACL reads regularly need
    // more than Vitest's 5s default on a cold or loaded desktop. Keep a finite
    // ceiling so hangs still fail, while functional integration tests do not
    // become timing tests by accident.
    testTimeout: 30_000
  }
}

export default defineConfig({
  test: {
    projects: [reactUi, electronNative]
  }
})
