module.exports = {
  root: true,
  env: { browser: true, es2021: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
  ],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: { jsx: true },
  },
  plugins: ["@typescript-eslint", "react-refresh"],
  // vite.config.js / .d.ts are emitted by `tsc -b` from vite.config.ts —
  // generated output, not source, so it is not linted.
  ignorePatterns: [
    "dist",
    "node_modules",
    ".eslintrc.cjs",
    "vite.config.js",
    "vite.config.d.ts",
  ],
  rules: {
    "react-refresh/only-export-components": [
      "warn",
      { allowConstantExport: true },
    ],
  },
};
