// Entry point -- edge cases: namespace import, optional chaining calls
import { handler, AuthenticatedHandler } from "./api/index";
import * as Constants from "./shared/constants";  // namespace import

export function startServer(port: number = 3000): void {
  const version = Constants.API_VERSION;
  const h = new AuthenticatedHandler();

  // Optional chaining call edge case
  const result = h?.handle(new Request(`http://localhost:${port}`));
  console.log(`Server started on port ${port}, version ${version}`, result);
}

// Re-export for consumers
export { handler };

// Dead export: never used by anything that imports this module
export const APP_NAME = "golden-ts-app";
