import { createApiClient } from "@scoutglobe/core";
import { API_BASE_URL } from "./env";

/** Single shared API client instance for the web app. */
export const api = createApiClient({ baseUrl: API_BASE_URL });
