// Shared types -- edge case: type-only imports, generics, declaration merging

export interface User {
  id: string;
  email: string;
  scopes: string[];
}

export interface ApiResponse<T> {
  data: T;
  error?: string;
  status: number;
}

export type UserId = string;
export type TokenString = string;

// Declaration merging edge case
export interface Config {
  baseUrl: string;
}

export interface Config {
  timeout: number;
}

// Enum
export enum HttpStatus {
  Ok = 200,
  Unauthorized = 401,
  NotFound = 404,
}
