// HTTP handlers -- edge cases: function overloads, class with methods, generics
import type { User, ApiResponse } from "../shared/types";
import { HttpStatus } from "../shared/types";
import { authMiddleware } from "./middleware";
import { MAX_RETRIES, getTimeout } from "../shared/constants";

// Function overload declarations -- edge case: overloads
export function handler(req: Request): Response;
export function handler(req: Request, options: { timeout?: number }): Response;
export function handler(req: Request, options?: { timeout?: number }): Response {
  const ctx = authMiddleware(req.headers.get("authorization") ?? "");
  if (!ctx.user) {
    return new Response(JSON.stringify({ error: "Unauthorized", status: 401 }), {
      status: HttpStatus.Unauthorized,
    });
  }
  return processRequest(req, ctx.user);
}

function processRequest(req: Request, user: User): Response {
  const timeout = getTimeout();
  return new Response(
    JSON.stringify(buildResponse(user, timeout)),
    { status: HttpStatus.Ok }
  );
}

function buildResponse<T extends User>(user: T, _timeout: number): ApiResponse<T> {
  return { data: user, status: HttpStatus.Ok };
}

// Class with methods -- edge case: class inheritance
export class AuthenticatedHandler {
  private retries: number;

  constructor() {
    this.retries = MAX_RETRIES;
  }

  handle(req: Request): Response {
    return handler(req);
  }

  retry(req: Request): Response {
    for (let i = 0; i < this.retries; i++) {
      try {
        return this.handle(req);
      } catch {
        continue;
      }
    }
    return new Response("", { status: 503 });
  }
}
