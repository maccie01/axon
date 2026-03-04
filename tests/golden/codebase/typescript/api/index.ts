// Barrel export -- edge case: export * from, re-exports
export { handler, AuthenticatedHandler } from "./routes";
export { authMiddleware } from "./middleware";
export type { MiddlewareContext } from "./middleware";
