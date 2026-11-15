@id("mandate_not_active")
forbid (principal, action, resource)
when { !context.mandate_active };

@id("base_permit")
permit (principal, action in [Action::"submit_order", Action::"auto_approve"], resource);

@id("total_over_order_limit")
forbid (principal, action == Action::"auto_approve", resource)
when { context.total_net.greaterThan(context.limit_per_order_net) };

@id("unverified_stock_over_limit")
forbid (principal, action == Action::"auto_approve", resource)
when { context.unverified_value_net.greaterThan(context.max_unverified_value_net) };

@id("origin_conflict")
forbid (principal, action == Action::"auto_approve", resource)
when { context.has_origin_conflict };

@id("deviates_from_request")
forbid (principal, action == Action::"auto_approve", resource)
when { context.has_changes_vs_request };

@id("partial_fulfilment")
forbid (principal, action == Action::"auto_approve", resource)
when { context.has_partial };
