/** Lineage tracker — records parent/child hop ids under one trace */
export class LineageTracker {
  private hops: { from: string; to: string; reasonCode: string }[] = [];

  record(from: string, to: string, reasonCode: string): void {
    this.hops.push({ from, to, reasonCode });
  }

  snapshot(): { hops: { from: string; to: string; reasonCode: string }[] } {
    return { hops: [...this.hops] };
  }
}
