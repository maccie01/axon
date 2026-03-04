// Constants -- edge case: dead export (exported but never imported)

export const API_VERSION = "v1";
export const MAX_RETRIES = 3;

// Dead export: declared and exported but never imported anywhere
export const LEGACY_API_KEY = "deprecated-key-12345";

// Used internally within this module only
const _INTERNAL_TIMEOUT = 5000;

export function getTimeout(): number {
  return _INTERNAL_TIMEOUT;
}

// Dead function: exported but never called from outside
export function deprecatedHelper(): string {
  return LEGACY_API_KEY;
}
