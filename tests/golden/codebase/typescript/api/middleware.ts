// Middleware -- edge cases: type-only import, optional chaining, generic return
import type { User, ApiResponse } from "../shared/types";
import { HttpStatus } from "../shared/types";
import { API_VERSION } from "../shared/constants";

export interface MiddlewareContext {
  user?: User;
  token: string;
}

export function authMiddleware(token: string): MiddlewareContext {
  const user = validateToken(token);
  return {
    user: user ?? undefined,
    token,
  };
}

function validateToken(token: string): User | null {
  // Optional chaining edge case
  const parts = token?.split(".");
  if (!parts || parts.length !== 3) {
    return null;
  }
  return {
    id: parts[0],
    email: `${parts[0]}@example.com`,
    scopes: [],
  };
}

// Uses HttpStatus enum (USES_TYPE edge)
function buildErrorResponse<T>(status: HttpStatus, message: string): ApiResponse<T> {
  return {
    data: null as unknown as T,
    error: message,
    status,
  };
}

// Dead function -- never called from outside this module or within it after init
function _unusedMiddlewareHelper(): string {
  return API_VERSION;
}
