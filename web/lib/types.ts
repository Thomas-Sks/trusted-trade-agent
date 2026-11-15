export interface Candidate {
  product_id: string; name: string; qty_sales_units: string; sales_unit: string; unit_net: string;
  line_total_net: string; comparison_net: string; stock: string; delivery_date: string; origins: string[];
  origin: string; changes_vs_request: string[]; partial: boolean; is_substitute: boolean;
  reliability: string | null; carbon_kg_per_kg: string | null; missing_qty: string; stale: boolean;
}
export interface OfferLine {
  line_id: string; tiers: Record<string, Candidate>; excluded: { product_id: string; reason: string }[];
  exceptions: string[]; split: Candidate[]; backorder_qty: string;
}
export interface Offer {
  offer_id: string; request_id: string; valid_until: string; lines: OfferLine[]; simulated: string[];
  signature: string; ui_signature_verified?: boolean;
}
export interface Decision { outcome: string; rules_fired: string[]; context: Record<string, unknown> }
export interface Order {
  order_id: string; org_id: string; state: string; version: number; total_net: string; decision: Decision | null;
  order_response: { code: string; lines: { status: number; product_id: string; quantity: string; substituted_for: string | null; backorder_qty: string }[] } | null;
  lock_until: string | null; approved_by: string | null; rejection_reason: string | null;
}
export interface AuditEvent { id: string; type: string; subject: string; time: string; step: string; actor: string; outcome: string; explanation: string; hash: string }
export interface CardLine { name: string; qty_sales_units: string; sales_unit: string; unit_net: string; line_total_net: string; stock: string; changes: string[]; vs_usual: string | null; partial: boolean; is_substitute: boolean }
export interface ApprovalCard {
  order_id: string; org_id: string; version: number; offer_hash_short: string; total_net: string; total_gross: string;
  reasons: string[]; lines: CardLine[]; warnings: string[]; delivery_date: string | null; minutes_to_cutoff: number | null; step_up_required: boolean;
}
export interface Draft { lines: unknown[]; delivery: { requested_date: string; latest_acceptable_date: string }; assumptions: string[]; questions: string[] }
