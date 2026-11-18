/** The demo account's business is generated sample data and is always labelled as such. */
export function isDemoBusiness(b: { name: string; description: string | null } | null): boolean {
  return !!b && (b.description?.startsWith("Synthetic demonstration") === true || /\(demo\)/i.test(b.name));
}
