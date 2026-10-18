/** Existing root hash bookmarks still open the resident application. */
export function isLandingRoute(pathname: string, hash: string) {
  return pathname === "/" && !hash.startsWith("#/");
}
