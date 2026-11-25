import { dashboardMock } from "../data/dashboardMock";

export async function getDashboardData({ signal } = {}) {
  if (signal?.aborted) {
    throw new DOMException("Chargement annulé.", "AbortError");
  }

  return dashboardMock;
}
